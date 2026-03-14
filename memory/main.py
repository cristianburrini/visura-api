import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from memory.database import QueryCache, get_db, init_db, Immobile, Soggetto, Titolarita
from memory.transformer import normalize_visura_data

# Configuration
UPSTREAM_API_URL = os.getenv("UPSTREAM_API_URL", "http://visure-api:8000")
CACHE_EXPIRATION_DAYS = int(os.getenv("CACHE_EXPIRATION_DAYS", "30"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("memory-proxy")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    yield

app = FastAPI(title="Visura Memory Proxy", lifespan=lifespan)

# --- Models ---

class VisuraInput(BaseModel):
    provincia: str
    comune: str
    foglio: str
    particella: str
    sezione: Optional[str] = None
    tipo_catasto: Optional[str] = None

class VisuraIntestatiInput(BaseModel):
    provincia: str
    comune: str
    foglio: str
    particella: str
    tipo_catasto: str
    subalterno: Optional[str] = None
    sezione: Optional[str] = None

# --- Helpers ---

def get_params_hash(params: Dict[str, Any]) -> str:
    """Creates a stable hash of the request parameters."""
    # Ensure keys are sorted for stability
    encoded = json.dumps(params, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()

async def get_upstream_health():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{UPSTREAM_API_URL}/health", timeout=2.0)
            return response.status_code == 200, response.json()
    except Exception:
        return False, None

# --- Endpoints ---

@app.post("/visura")
async def proxy_ricerca(request: VisuraInput, db: Session = Depends(get_db)):
    params = request.model_dump()
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
            response = await client.post(f"{UPSTREAM_API_URL}/visura", json=params)
            response.raise_for_status()
            upstream_data = response.json()
            # visure-api returns a list of IDs. We take the first one for simplicity if multiple.
            upstream_id = upstream_data["request_ids"][0]
            
            if not cached:
                cached = QueryCache(
                    params_hash=phash, 
                    status='processing', 
                    upstream_id=upstream_id,
                    params=params  # Store original params
                )
                db.add(cached)
            else:
                cached.status = 'processing'
                cached.upstream_id = upstream_id
                cached.params = params  # Update params
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
    # Same logic as /visura but different upstream endpoint
    params = request.model_dump()
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
            response = await client.post(f"{UPSTREAM_API_URL}/visura/intestati", json=params)
            response.raise_for_status()
            upstream_data = response.json()
            upstream_id = upstream_data["request_id"]
            
            if not cached:
                cached = QueryCache(
                    params_hash=phash, 
                    status='processing', 
                    upstream_id=upstream_id,
                    params=params  # Store original params
                )
                db.add(cached)
            else:
                cached.status = 'processing'
                cached.upstream_id = upstream_id
                cached.params = params  # Update params
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
    if not proxy_id.startswith("proxy_"):
        raise HTTPException(status_code=400, detail="Invalid proxy ID format")
    
    try:
        db_id = int(proxy_id.split("_")[1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proxy ID format")
        
    cached = db.query(QueryCache).filter(QueryCache.id == db_id).first()
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
        # Poll upstream
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
                    
                    # Normalize into relational tables
                    # We need the original params to normalize properly (for fields not in raw response)
                    # We can reconstruct them or store them. Let's assume we need them.
                    # For simplicity, we'll try to normalize with what we have.
                    # We might need to store params in QueryCache too.
                    try:
                        # Extract results list from upstream data
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
                        # We still have the JSON, so we count this as a success for the proxy
                    
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
            return JSONResponse({
                "request_id": proxy_id,
                "status": "processing",
                "message": "Upstream unavailable, retrying later"
            })

    return JSONResponse({
        "request_id": proxy_id,
        "status": cached.status,
        "error": cached.error_message
    })

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    # Check DB
    db_status = "healthy"
    try:
        db.execute("SELECT 1")
    except Exception:
        db_status = "unhealthy"
        
    # Check Upstream
    upstream_ok, upstream_info = await get_upstream_health()
    
    return JSONResponse({
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "upstream": {
            "status": "reachable" if upstream_ok else "unreachable",
            "info": upstream_info
        }
    })

@app.delete("/cache/{proxy_id}")
async def delete_cache(proxy_id: str, db: Session = Depends(get_db)):
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
    return JSONResponse(
        status_code=501, 
        content={"status": "not_implemented", "message": "Sezioni extraction is not supported through the proxy."}
    )
