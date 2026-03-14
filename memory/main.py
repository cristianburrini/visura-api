import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from memory.database import (
    QueryCache, get_db, init_db, 
    Immobile, Soggetto, Titolarita, 
    CatalogComune, CatalogParcel, ScheduledVisura
)
from memory.transformer import normalize_visura_data
from memory.catalog_manager import reload_catalog

# Configuration
UPSTREAM_API_URL = os.getenv("UPSTREAM_API_URL", "http://visure-api:8000")
CACHE_EXPIRATION_DAYS = int(os.getenv("CACHE_EXPIRATION_DAYS", "30"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Massive Submission Configuration
MAX_PARALLEL_VISURE = int(os.getenv("MAX_PARALLEL_VISURE", "2"))
QUEUE_POLLING_INTERVAL = int(os.getenv("QUEUE_POLLING_INTERVAL", "5"))

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("memory-proxy")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management: DB initialization and background job startup."""
    logger.info("Initializing database...")
    init_db()
    
    # Start background job for massive submissions
    import asyncio
    from memory.worker import start_background_job
    background_task = asyncio.create_task(start_background_job())
    
    yield
    # Cleanup background task on shutdown
    background_task.cancel()
    try:
        await background_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Visura Memory Proxy", lifespan=lifespan)



class VisuraInput(BaseModel):
    """Input for standard property search (Phase 1)."""
    provincia: str
    comune: str
    foglio: str
    particella: str
    sezione: Optional[str] = None
    tipo_catasto: Optional[str] = None

class MassiveScheduleInput(BaseModel):
    """Input for massive batch submission via background job."""
    scenario: int = Field(..., ge=1, le=3)
    provincia: str
    comune: str
    targets: List[Dict[str, Any]]
    tipo_catasto: Optional[str] = None

class VisuraIntestatiInput(BaseModel):
    """Input for owner search (Phase 2)."""
    provincia: str
    comune: str
    foglio: str
    particella: str
    tipo_catasto: str
    subalterno: Optional[str] = None
    sezione: Optional[str] = None


class ComuneSearchResponse(BaseModel):
    codice_catastale: str
    denominazione: str
    sigla_provincia: str
    regione: str
    codice_istat: str
    denominazione_upstream: Optional[str] = None
    provincia_upstream: Optional[str] = None
    regione_upstream: Optional[str] = None

class ParcelResponse(BaseModel):
    sezione: Optional[str]
    foglio: str
    particella: str



def get_params_hash(params: Dict[str, Any]) -> str:
    """Creates a stable hash of the request parameters to use as cache key."""
    # Ensure keys are sorted for stability
    encoded = json.dumps(params, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()

def is_already_done(db: Session, target: Dict[str, Any], scenario: int) -> bool:
    """
    Checks if a target is already processed or scheduled.
    Prevents redundant processing by checking both QueryCache and ScheduledVisura.
    """
    phash = get_params_hash(target)
    # Check if we already have it in completed cache
    cached = db.query(QueryCache).filter(QueryCache.params_hash == phash, QueryCache.status == "completed").first()
    if cached:
        return True
    
    # Check if it's already in the massive submission queue
    query = db.query(ScheduledVisura).filter(
        ScheduledVisura.provincia == target.get("provincia"),
        ScheduledVisura.comune == target.get("comune"),
        ScheduledVisura.foglio == str(target.get("foglio")),
        ScheduledVisura.particella == str(target.get("particella")),
        ScheduledVisura.sezione == target.get("sezione"),
        ScheduledVisura.subalterno == target.get("subalterno"),
        ScheduledVisura.status.in_(["pending", "submitted", "done"])
    )
    if query.first():
        return True
        
    return False

async def get_upstream_health():
    """Checks the health of the upstream visure-api."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{UPSTREAM_API_URL}/health", timeout=2.0)
            return response.status_code == 200, response.json()
    except Exception:
        return False, None

def get_levenshtein_suggestions(db: Session, table, column, value, limit=3):
    """Simple suggestion helper using ILIKE prefix match as a fallback."""
    query = db.query(column).filter(column.ilike(f"%{value}%")).distinct().limit(limit)
    return [r[0] for r in query.all()]

def validate_and_canonicalize_params(db: Session, params: Dict[str, Any]):
    """
    Validates visura parameters against the catalog.
    If valid, returns (canonical_params, upstream_params).
    If invalid, raises HTTPException 400 with details.
    """
    # 1. Resolve Comune
    comune_name = params.get("comune", "").strip().upper()
    prov_code = params.get("provincia", "").strip().upper()
    
    cat_comune = db.query(CatalogComune).filter(
        CatalogComune.denominazione == comune_name,
        CatalogComune.sigla_provincia == prov_code
    ).first()
    
    if not cat_comune:
        # Check if maybe they used a 4-letter code instead of name
        cat_comune = db.query(CatalogComune).filter(CatalogComune.codice_catastale == comune_name).first()

    if not cat_comune:
        suggestions = get_levenshtein_suggestions(db, CatalogComune, CatalogComune.denominazione, comune_name)
        raise HTTPException(status_code=400, detail={
            "error": "Comune non trovato nel catalogo",
            "invalid_fields": ["comune", "provincia"],
            "suggestions": suggestions
        })

    # 2. Check Parcel availability
    foglio = params.get("foglio", "").strip().lstrip('0') or "0"
    particella = params.get("particella", "").strip().lstrip('0') or "0"
    sezione = params.get("sezione")
    if sezione == "" or sezione == "_":
        sezione = None
        
    # Query parcel catalog - no more zfill(4)
    exists = db.query(CatalogParcel).filter(
        CatalogParcel.codice_comune == cat_comune.codice_catastale,
        CatalogParcel.foglio == foglio,
        CatalogParcel.particella == particella
    )
    if sezione:
        exists = exists.filter(CatalogParcel.sezione == sezione)
    else:
        exists = exists.filter(CatalogParcel.sezione.is_(None))
        
    if not exists.first():
        raise HTTPException(status_code=400, detail={
            "error": "Foglio o Particella non validi per questo comune",
            "invalid_fields": ["foglio", "particella"],
            "hints": f"Verificato per comune {cat_comune.denominazione} ({cat_comune.codice_catastale})"
        })

    # 3. Construct Upstream Params (with Overrides)
    upstream_params = params.copy()
    upstream_params["comune"] = cat_comune.denominazione_upstream or cat_comune.denominazione
    upstream_params["provincia"] = cat_comune.provincia_upstream or cat_comune.sigla_provincia
    
    if cat_comune.regione_upstream:
        upstream_params["regione"] = cat_comune.regione_upstream

    return params, upstream_params



@app.post("/visura")
async def proxy_ricerca(request: VisuraInput, db: Session = Depends(get_db)):
    """Proxies visura search for properties (Phase 1) with caching."""
    params = request.model_dump()
    # Validate against catalog
    _, upstream_params = validate_and_canonicalize_params(db, params)
    phash = get_params_hash(params)
    
    # Check cache
    cached = db.query(QueryCache).filter(QueryCache.params_hash == phash).first()
    if cached:
        # Check expiration
        is_expired = datetime.utcnow() > (cached.updated_at + timedelta(days=CACHE_EXPIRATION_DAYS))
        if not is_expired or cached.status == 'processing':
            return JSONResponse({
                "request_ids": [f"proxy_{cached.id}"],
                "status": "cached" if cached.status == 'completed' else cached.status,
                "message": "Request served from memory proxy"
            })

    # Miss or Expired: Call Upstream
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{UPSTREAM_API_URL}/visura", json=upstream_params)
            response.raise_for_status()
            upstream_data = response.json()
            # visure-api returns a list of IDs. We take the first one for simplicity.
            upstream_id = upstream_data["request_ids"][0]
            
            if not cached:
                cached = QueryCache(params_hash=phash, status='processing', upstream_id=upstream_id, params=params)
                db.add(cached)
            else:
                cached.status = 'processing'
                cached.upstream_id = upstream_id
                cached.params = params
                cached.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(cached)
            return JSONResponse({
                "request_ids": [f"proxy_{cached.id}"],
                "status": "queued",
                "message": "Request proxied to upstream"
            })
    except Exception as e:
        logger.error(f"Upstream error: {e}")
        # If we have an expired but completed version, return that in degraded mode
        if cached and cached.status == 'completed':
            return JSONResponse({
                "request_ids": [f"proxy_{cached.id}"],
                "status": "completed",
                "message": "Serving expired data due to upstream unavailability (degraded mode)"
            })
        raise HTTPException(status_code=503, detail="Upstream Visure API is unavailable")

@app.post("/visura/intestati")
async def proxy_intestati(request: VisuraIntestatiInput, db: Session = Depends(get_db)):
    """Proxies search for property owners (Phase 2) with caching."""
    params = request.model_dump()
    # Validate against catalog
    _, upstream_params = validate_and_canonicalize_params(db, params)
    phash = get_params_hash(params)
    
    cached = db.query(QueryCache).filter(QueryCache.params_hash == phash).first()
    if cached and (cached.status == 'processing' or (datetime.utcnow() - cached.updated_at).days < CACHE_EXPIRATION_DAYS):
        return JSONResponse({
            "request_id": f"proxy_{cached.id}",
            "status": "cached" if cached.status == 'completed' else cached.status,
            "message": "Request served from memory proxy"
        })

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{UPSTREAM_API_URL}/visura/intestati", json=upstream_params)
            response.raise_for_status()
            upstream_data = response.json()
            upstream_id = upstream_data["request_id"]
            
            if not cached:
                cached = QueryCache(params_hash=phash, status='processing', upstream_id=upstream_id, params=params)
                db.add(cached)
            else:
                cached.status = 'processing'
                cached.upstream_id = upstream_id
                cached.params = params
                cached.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(cached)
            return JSONResponse({
                "request_id": f"proxy_{cached.id}",
                "status": "queued",
                "message": "Request proxied to upstream"
            })
    except Exception as e:
        logger.error(f"Upstream error: {e}")
        if cached and cached.status == 'completed':
            return JSONResponse({
                "request_id": f"proxy_{cached.id}",
                "status": "completed",
                "message": "Serving expired data due to upstream unavailability (degraded mode)"
            })
        raise HTTPException(status_code=503, detail="Upstream Visure API is unavailable")

@app.get("/visura/{proxy_id}")
async def get_proxy_status(proxy_id: str, db: Session = Depends(get_db)):
    """Retrieves status and data for a proxied request."""
    if not proxy_id.startswith("proxy_"):
        raise HTTPException(status_code=400, detail="Invalid proxy ID format")
    db_id = int(proxy_id.split('_')[1])
    cached = db.get(QueryCache, db_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Request ID not found")
        
    if cached.status == 'completed':
        return JSONResponse({
            "request_id": proxy_id,
            "status": "completed",
            "data": cached.results_json,
            "timestamp": cached.updated_at.isoformat()
        })
        
    if cached.status == 'processing' and cached.upstream_id:
        # Poll upstream visure-api
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{UPSTREAM_API_URL}/visura/{cached.upstream_id}", timeout=5.0)
                response.raise_for_status()
                upstream_data = response.json()
                
                if upstream_data.get("status") == "completed":
                    # Upstream finished! Normalize and cache.
                    raw_results = upstream_data.get("data")
                    # Store raw JSON as backup
                    cached.results_json = raw_results
                    cached.status = 'completed'
                    cached.updated_at = datetime.utcnow()
                    
                    # Normalize into relational tables for advanced queries
                    try:
                        raw_data = upstream_data.get("data")
                        if isinstance(raw_data, dict):
                            if "results" in raw_data:
                                results_list = raw_data.get("results", [])
                            elif "immobile" in raw_data or "intestati" in raw_data:
                                # Single result case (e.g. from visura/intestati)
                                results_list = [raw_data]
                            else:
                                results_list = []
                        elif isinstance(raw_data, list):
                            results_list = raw_data
                        else:
                            results_list = []
                        
                        normalize_visura_data(db, results_list, cached.params or {})
                    except Exception as normalize_err:
                        logger.error(f"Normalization failed: {normalize_err}")
                        # If normalization fails, we consider the whole operation failed to ensure consistency
                        cached.status = 'error'
                        cached.error_message = f"Normalization failed: {normalize_err}"
                        db.commit()
                        return JSONResponse({
                            "request_id": proxy_id,
                            "status": "error",
                            "error": f"Normalization failed: {normalize_err}"
                        })
                    
                    db.commit()
                    return JSONResponse({
                        "request_id": proxy_id,
                        "status": "completed",
                        "data": raw_results,
                        "timestamp": cached.updated_at.isoformat()
                    })
                elif upstream_data.get("status") == "error":
                    cached.status = "error"
                    cached.error_message = upstream_data.get("error")
                    db.commit()
                    return JSONResponse(upstream_data)
                
                return JSONResponse({
                    "request_id": proxy_id,
                    "status": "processing",
                    "message": "Upstream still working..."
                })
        except Exception as e:
            logger.warning(f"Upstream polling failed: {e}")
            return JSONResponse({"request_id": proxy_id, "status": "processing", "message": "Upstream unavailable, retrying later"})

    return JSONResponse({"request_id": proxy_id, "status": cached.status, "error": cached.error_message})

@app.post("/massive/schedule")
async def schedule_massive(request: MassiveScheduleInput, db: Session = Depends(get_db)):
    """Schedules a massive batch of targets for visure submission."""
    res_counts: Dict[str, int] = {"scheduled": 0, "skipped": 0}
    for target in request.targets:
        # Construct full target data for validation and duplicate check
        target_data = {
            "provincia": request.provincia,
            "comune": request.comune,
            "foglio": str(target.get("foglio")),
            "particella": str(target.get("particella")),
            "sezione": target.get("sezione"),
            "subalterno": target.get("subalterno"),
            "tipo_catasto": request.tipo_catasto
        }
        # Scenario mapping: 1 and 3 are property searches (PARTICELLA), 2 is owner search (SUBALTERNO)
        target_type = "PARTICELLA" if request.scenario in [1, 3] else "SUBALTERNO"
        
        # Prevent redundant processing
        if is_already_done(db, target_data, request.scenario):
            res_counts["skipped"] += 1
            continue
            
        new_item = ScheduledVisura(
            target_type=target_type, scenario=request.scenario,
            provincia=target_data["provincia"], comune=target_data["comune"],
            foglio=target_data["foglio"], particella=target_data["particella"],
            subalterno=target_data["subalterno"], sezione=target_data["sezione"],
            tipo_catasto=target_data["tipo_catasto"], status="pending"
        )
        db.add(new_item)
        res_counts["scheduled"] += 1
        
    db.commit()
    return {
        "status": "success", 
        "scheduled": res_counts["scheduled"], 
        "skipped": res_counts["skipped"], 
        "message": f"Successfully scheduled {res_counts['scheduled']} items. {res_counts['skipped']} items skipped (already cached or queued)."
    }

@app.get("/massive/status")
async def get_massive_status(db: Session = Depends(get_db)):
    """Returns overall statistics for the massive submission queue."""
    counts = db.query(ScheduledVisura.status, func.count(ScheduledVisura.id)).group_by(ScheduledVisura.status).all()
    stats = {status: count for status, count in counts}
    
    # Recent completions for monitoring
    last_done = db.query(ScheduledVisura).filter(ScheduledVisura.status == "done").order_by(ScheduledVisura.completed_at.desc()).limit(10).all()
    return {
        "queue_stats": stats,
        "last_completed": [{"id": item.id, "target": f"{item.foglio}/{item.particella}", "time": item.completed_at} for item in last_done]
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """System health check including DB and Upstream status."""
    db_status = "healthy"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"DB Health check failed: {e}")
        db_status = "unhealthy"
        
    upstream_ok, upstream_info = await get_upstream_health()
    return JSONResponse({
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "upstream": {"status": "reachable" if upstream_ok else "unreachable", "info": upstream_info}
    })

@app.post("/catalog/reload")
async def trigger_reload(db: Session = Depends(get_db)):
    """Trigger a manual reload of the static catalog data from CSV files."""
    comuni_path = "/app/staticData/comuniANPR_ISTAT.csv"
    parcels_path = "/app/staticData/parcelIndex.csv"
    mapping_path = "/app/staticData/province_mapping.csv"
    
    if not os.path.exists(comuni_path) or not os.path.exists(parcels_path):
        raise HTTPException(status_code=500, detail="Static data files not found in /app/staticData")
        
    result = reload_catalog(db, comuni_path, parcels_path, mapping_path)
    return JSONResponse(result)

@app.get("/catalog/comuni", response_model=List[ComuneSearchResponse])
async def search_comuni(
    q: Optional[str] = None, 
    provincia: Optional[str] = None, 
    regione: Optional[str] = None, 
    istat: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    """Fuzzy search for comuni in the catalog."""
    query = db.query(CatalogComune)
    if q:
        q_clean = q.strip()
        query = query.filter(or_(CatalogComune.denominazione.ilike(f"%{q_clean}%"), CatalogComune.codice_catastale.ilike(f"%{q_clean}%")))
    if provincia:
        query = query.filter(CatalogComune.sigla_provincia == provincia.strip().upper())
    if regione:
        query = query.filter(CatalogComune.regione.ilike(f"%{regione.strip()}%"))
    if istat:
        query = query.filter(CatalogComune.codice_istat == istat.strip())
    results = query.limit(50).all()
    return results

@app.get("/catalog/comuni/{cod_cat}/sheets")
async def list_sheets(cod_cat: str, db: Session = Depends(get_db)):
    """Lists available sheets (fogli) for a specific comune."""
    results = db.query(CatalogParcel.foglio).filter(CatalogParcel.codice_comune == cod_cat.strip().upper()).distinct().order_by(CatalogParcel.foglio).all()
    return [r[0] for r in results]

@app.get("/catalog/comuni/{cod_cat}/sheets/{foglio}/parcels")
async def list_parcels(cod_cat: str, foglio: str, sezione: Optional[str] = None, db: Session = Depends(get_db)):
    """Lists available parcels for a specific sheet and comune."""
    fog_norm = foglio.strip().lstrip('0') or "0"
    query = db.query(CatalogParcel.particella).filter(CatalogParcel.codice_comune == cod_cat.upper(), CatalogParcel.foglio == fog_norm)
    if sezione:
        query = query.filter(CatalogParcel.sezione == sezione)
    else:
        query = query.filter(CatalogParcel.sezione.is_(None))
    results = query.distinct().order_by(CatalogParcel.particella).all()
    return [r[0] for r in results]

@app.delete("/cache/{proxy_id}")
async def delete_cache(proxy_id: str, db: Session = Depends(get_db)):
    """Deletes a specific cache entry from the database."""
    if not proxy_id.startswith("proxy_"):
        raise HTTPException(status_code=400, detail="Invalid proxy ID format")
    try:
        db_id = int(proxy_id.split("_")[1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proxy ID format")
    cached = db.query(QueryCache).filter(QueryCache.id == db_id).first()
    if cached:
        db.delete(cached)
        db.commit()
        return {"status": "success", "message": f"Cache entry {proxy_id} deleted"}
    raise HTTPException(status_code=404, detail="Entry not found")

@app.post("/sezioni/extract")
async def extract_sezioni():
    """Extraction of sezioni is not supported via proxy."""
    return JSONResponse(status_code=501, content={"status": "not_implemented", "message": "Sezioni extraction is not supported through the proxy."})
