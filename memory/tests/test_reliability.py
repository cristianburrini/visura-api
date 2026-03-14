import pytest
import httpx
from memory.database import QueryCache
from datetime import datetime, timedelta
from memory.main import get_params_hash

def test_degraded_mode_serving_expired_cache(client, db):
    payload = {
        "provincia": "any",
        "comune": "any",
        "foglio": "any",
        "particella": "any",
        "sezione": None,
        "tipo_catasto": "F"
    }
    phash = get_params_hash(payload)
    
    # 1. Setup an expired but completed cache entry
    # Ensure it's expired by using a very old date
    old_date = datetime.utcnow() - timedelta(days=999)
    cached = QueryCache(
        params_hash=phash, 
        status='completed', 
        results_json={"foo": "bar"},
        updated_at=old_date
    )
    db.add(cached)
    db.commit()
    db.refresh(cached)
    
    # 2. Call the proxy - it should return the expired data in degraded mode
    # instead of a 503 from the failed upstream call
    response = client.post("/visura", json=payload)
    assert response.status_code == 200
    # The message comes from the exception handler in main.py
    assert response.json()["status"] == "completed"

def test_upstream_unavailable_no_cache(client, db, respx_mock):
    # Simulating no cache entry and upstream down
    respx_mock.post(f"http://visure-api:8000/visura").side_effect = httpx.ConnectError("Failed")
    
    payload = {
        "provincia": "new",
        "comune": "new",
        "foglio": "new",
        "particella": "new",
        "sezione": None,
        "tipo_catasto": "F"
    }
    
    response = client.post("/visura", json=payload)
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]
