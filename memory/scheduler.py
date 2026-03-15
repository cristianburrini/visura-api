import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from memory.database import QueryCache, ScheduledVisura, Immobile, Titolarita

logger = logging.getLogger("memory-scheduler")

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
    
    # Check for persistent data (Owners)
    # If the target specifies a subalterno, we can skip if we already have owners for it
    sub = target.get("subalterno")
    if sub is not None:
        existing_immobile = db.query(Immobile).filter(
            Immobile.provincia == target.get("provincia"),
            Immobile.comune == target.get("comune"),
            Immobile.foglio == str(target.get("foglio")),
            Immobile.particella == str(target.get("particella")),
            Immobile.subalterno == str(sub),
            Immobile.tipo_catasto == target.get("tipo_catasto", "F")
        ).first()
        
        if existing_immobile:
            # Check if it has any associated owners (Titolarita)
            has_owners = db.query(Titolarita).filter(Titolarita.immobile_id == existing_immobile.id).first()
            if has_owners:
                logger.info(f"Smart Skip: Found existing owners for {target.get('foglio')}/{target.get('particella')} sub {sub}")
                return True

    # Check if it's already in the massive submission queue
    query = db.query(ScheduledVisura).filter(
        ScheduledVisura.provincia == target.get("provincia"),
        ScheduledVisura.comune == target.get("comune"),
        ScheduledVisura.foglio == str(target.get("foglio")),
        ScheduledVisura.particella == str(target.get("particella")),
        ScheduledVisura.sezione == target.get("sezione"),
        ScheduledVisura.subalterno == target.get("subalterno"),
        ScheduledVisura.tipo_catasto == target.get("tipo_catasto"),
        ScheduledVisura.status.in_(["pending", "submitted", "done"])
    )
    if query.first():
        return True
        
    return False

async def schedule_scenario3_owners(db: Session, provincia: str, comune: str, foglio: str, particella: str, sezione: Optional[str], results: dict, tipo_catasto: Optional[str] = None):
    """
    Extracts subalterns from property search results and schedules owner searches (Scenario 3).
    Skips subalterns that are already processed or pending.
    """
    # Extract results list
    immobili = results.get("results", []) or results.get("immobili", [])
    if not immobili and "results" not in results and "immobili" not in results:
        # Maybe it's a single result
        immobili = [results] if results.get("subalterno") or results.get("Particella") else []

    scheduled_count = 0
    skipped_count = 0

    for res in immobili:
        imm = res.get("immobile") if "immobile" in res else res
        sub = imm.get("Subalterno") or imm.get("subalterno") or imm.get("Sub")
        
        # If no subaltern is present, we might still want to schedule the owner search 
        # (some properties don't have subalterns but still need owner search in Phase 2)
        # However, SISTER usually allows owner search for Fabbricati ONLY if you select a result.
        # If there's only one result and no subaltern, 'sub' will be None or empty.
        
        # Construct target data for duplicate check
        target_data = {
            "provincia": provincia,
            "comune": comune,
            "foglio": str(foglio),
            "particella": str(particella),
            "sezione": sezione,
            "subalterno": sub,
            "tipo_catasto": tipo_catasto or parent_tipo_catasto_logic(imm) 
        }
        
        # We need a way to determine tipo_catasto if it's not provided.
        # Usually Scenario 3 targets Fabbricati.
        tc = tipo_catasto or "F" 
        target_data["tipo_catasto"] = tc

        if is_already_done(db, target_data, scenario=3):
            skipped_count += 1
            continue
        
        new_item = ScheduledVisura(
            target_type="SUBALTERNO",
            scenario=3,
            provincia=provincia,
            comune=comune,
            foglio=str(foglio),
            particella=str(particella),
            subalterno=sub,
            sezione=sezione,
            tipo_catasto=tc,
            status="pending"
        )
        db.add(new_item)
        scheduled_count += 1
    
    db.commit()
    logger.info(f"Scenario 3 owner scheduling completed: {scheduled_count} scheduled, {skipped_count} skipped.")
    return scheduled_count

def parent_tipo_catasto_logic(imm: dict) -> str:
    # Simple heuristic if needed
    return "F"
