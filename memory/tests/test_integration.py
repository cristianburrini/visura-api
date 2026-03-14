import pytest
from memory.database import QueryCache, Immobile
from memory.main import get_params_hash

def test_full_visura_flow(client, db, respx_mock):
    payload = {
        "provincia": "Trieste",
        "comune": "Trieste",
        "foglio": "1",
        "particella": "1",
        "sezione": None,
        "tipo_catasto": "F"
    }
    phash = get_params_hash(payload)
    
    # 1. Initial Request (Miss)
    upstream_post_route = respx_mock.post("http://visure-api:8000/visura").respond(
        json={"request_ids": ["upstream_123"], "status": "queued"}
    )
    
    response = client.post("/visura", json=payload)
    assert response.status_code == 200
    proxy_id = response.json()["request_ids"][0]
    assert proxy_id.startswith("proxy_")
    assert upstream_post_route.called
    
    # Verify processing status in DB
    cached = db.query(QueryCache).filter(QueryCache.params_hash == phash).first()
    assert cached is not None
    assert cached.status == "processing"
    
    # 2. Polling (Still processing)
    respx_mock.get("http://visure-api:8000/visura/upstream_123").respond(
        json={"status": "processing"}
    )
    response = client.get(f"/visura/{proxy_id}")
    assert response.json()["status"] == "processing"
    
    # 3. Polling (Completed upstream)
    raw_data = {
        "results": [{
            "immobile": {"Foglio": "1", "Particella": "1", "Partita": "OK"},
            "intestati": [{"Soggetto": "Test User"}]
        }]
    }
    respx_mock.get("http://visure-api:8000/visura/upstream_123").respond(
        json={"status": "completed", "data": raw_data}
    )
    
    response = client.get(f"/visura/{proxy_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    
    # 4. Verify DB normalization happened
    db.expire_all()
    imm = db.query(Immobile).filter(Immobile.partita == "OK").first()
    assert imm is not None
    
    # 5. Second Request (Cache Hit)
    # Reset mock to ensure it's NOT called
    respx_mock.reset()
    response = client.post("/visura", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "cached"
    assert response.json()["request_ids"][0] == proxy_id
