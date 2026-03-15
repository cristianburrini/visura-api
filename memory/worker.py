import asyncio
import logging
import os
from datetime import datetime
from sqlalchemy.orm import Session
import httpx

from memory.database import SessionLocal, ScheduledVisura, QueryCache, Immobile
from memory.main import UPSTREAM_API_URL, MAX_PARALLEL_VISURE, QUEUE_POLLING_INTERVAL, validate_and_canonicalize_params
from memory.scheduler import get_params_hash, schedule_scenario3_owners
from memory.transformer import normalize_visura_data

logger = logging.getLogger("memory-worker")

async def start_background_job():
    logger.info(f"Background job started. Max parallel: {MAX_PARALLEL_VISURE}, Polling: {QUEUE_POLLING_INTERVAL}s")
    while True:
        try:
            db = SessionLocal()
            try:
                await process_queue(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
        
        await asyncio.sleep(QUEUE_POLLING_INTERVAL)

async def process_queue(db: Session):
    # 1. Get currently processing items
    processing_count = db.query(ScheduledVisura).filter(ScheduledVisura.status == "submitted").count()
    
    if processing_count >= MAX_PARALLEL_VISURE:
        # Check status of submitted items
        submitted_items = db.query(ScheduledVisura).filter(ScheduledVisura.status == "submitted").all()
        for item in submitted_items:
            await check_item_status(db, item)
        return

    # 2. Re-submit items that are marked 'submitted' but might have been lost (on startup)
    # Actually, check_item_status will handle them if they have an upstream_id.
    
    # 3. Fetch pending items to fill slots
    slots_available = MAX_PARALLEL_VISURE - processing_count
    if slots_available > 0:
        pending_items = db.query(ScheduledVisura).filter(ScheduledVisura.status == "pending").order_by(ScheduledVisura.created_at.asc()).limit(slots_available).all()
        for item in pending_items:
            await submit_item(db, item)

async def submit_item(db: Session, item: ScheduledVisura):
    logger.info(f"Submitting item {item.id} (Scenario {item.scenario})")
    item.status = "submitted"
    item.started_at = datetime.utcnow()
    db.commit()

    params = {
        "provincia": item.provincia,
        "comune": item.comune,
        "foglio": item.foglio,
        "particella": item.particella,
        "sezione": item.sezione,
        "tipo_catasto": item.tipo_catasto
    }
    
    if item.target_type == "SUBALTERNO":
        params["subalterno"] = item.subalterno
        endpoint = "/visura/intestati"
    else:
        endpoint = "/visura"

    try:
        # We call the local proxy logic by simulating what proxy_ricerca does
        # but we use the upstream API directly or the internal logic.
        # Let's use httpx to call the upstream since that's what main.py does.
        _, upstream_params = validate_and_canonicalize_params(db, params)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{UPSTREAM_API_URL}{endpoint}", json=upstream_params)
            response.raise_for_status()
            data = response.json()
            
            if endpoint == "/visura":
                item.upstream_id = data["request_ids"][0]
            else:
                item.upstream_id = data["request_id"]
            
            db.commit()
    except Exception as e:
        logger.error(f"Failed to submit item {item.id}: {e}")
        item.status = "error"
        item.error_message = str(e)
        db.commit()

async def check_item_status(db: Session, item: ScheduledVisura):
    if not item.upstream_id:
        item.status = "error"
        item.error_message = "Missing upstream_id"
        db.commit()
        return

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{UPSTREAM_API_URL}/visura/{item.upstream_id}")
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "completed":
                raw_results = data.get("data", {})
                logger.info(f"Item {item.id} completed successfully. Persisting data...")
                
                # Persistence logic
                try:
                    # Determine which key holds the results
                    results_list = raw_results.get("results", []) or raw_results.get("immobili", [])
                    if not results_list:
                        # Fallback for single result objects (common for individual subaltern searches)
                        if "immobile" in raw_results:
                            results_list = [raw_results]
                        elif raw_results.get("foglio") or raw_results.get("subalterno"):
                            # Older fallback
                            results_list = [raw_results]
                        else:
                            results_list = []
                    
                    params = {
                        "provincia": item.provincia,
                        "comune": item.comune,
                        "foglio": item.foglio,
                        "particella": item.particella,
                        "sezione": item.sezione,
                        "subalterno": item.subalterno,
                        "tipo_catasto": item.tipo_catasto
                    }
                    
                    normalize_visura_data(db, results_list, params)
                    db.commit()
                except Exception as e:
                    logger.error(f"Persistence failed for item {item.id}: {e}")
                    # We continue to mark as done if we want, or error. 
                    # Let's mark as done but log the error for now as the upstream was successful.

                item.status = "done"
                item.completed_at = datetime.utcnow()
                
                # If Scenario 3 and it was a property search, schedule owner searches for results
                if item.scenario == 3 and item.target_type == "PARTICELLA" and item.tipo_catasto != "T":
                    await schedule_scenario3_owners(
                        db, 
                        item.provincia, 
                        item.comune, 
                        item.foglio, 
                        item.particella, 
                        item.sezione, 
                        raw_results,
                        tipo_catasto=item.tipo_catasto
                    )
                
                db.commit()
            elif data.get("status") == "error":
                logger.error(f"Item {item.id} failed upstream: {data.get('error')}")
                item.status = "error"
                item.error_message = data.get("error")
                db.commit()
    except Exception as e:
        logger.warning(f"Error checking status for item {item.id}: {e}")

# schedule_scenario3_owners moved to memory.scheduler
