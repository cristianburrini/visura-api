import pytest
from memory.database import QueryCache, Immobile, Soggetto, Titolarita
from memory.main import get_params_hash

def test_normalization_persistence_details(client, db, respx_mock):
    """
    Verifies that when a visura is completed, all related entities 
    are correctly created and linked in the database.
    """
    payload = {
        "provincia": "ROMA",
        "comune": "ROMA",
        "foglio": "100",
        "particella": "200",
        "tipo_catasto": "F"
    }
    phash = get_params_hash(payload)
    
    # 1. Setup Upstream Mock for a successful completion
    # We simulate the exact structure returned by visure-api
    raw_results = {
        "results": [
            {
                "immobile": {
                    "Foglio": "10",
                    "Particella": "20",
                    "Subalterno": "1",
                    "Categoria": "A/2"
                },
                "intestati": [
                    {
                        "Soggetto": "PERSI STENCE",
                        "Codice fiscale": "PRSSTN12A34B567C",
                        "Diritto o Titolarità": "Proprietà",
                        "Quota": "1/1"
                    }
                ]
            }
        ]
    }
    
    params = {
        "provincia": "MILANO",
        "comune": "MILANO",
        "foglio": "10",
        "particella": "20",
        "sezione": None,
        "tipo_catasto": "F"
    }
    
    phash = get_params_hash(params)
    
    # Mock UPSTREAM
    respx_mock.post("http://visure-api:8000/visura").respond(
        json={"request_ids": ["upstream_p1"], "status": "queued"}
    )
    respx_mock.get("http://visure-api:8000/visura/upstream_p1").respond(
        json={"status": "completed", "data": raw_results}
    )
    
    # 1. Trigger Initial
    resp = client.post("/visura", json=params)
    proxy_id = resp.json()["request_ids"][0]
    
    # 2. Poll to trigger normalization
    client.get(f"/visura/{proxy_id}")
    
    # 3. Verify normalization
    db.expire_all()
    imm = db.query(Immobile).filter(Immobile.subalterno == "1").first()
    assert imm is not None, "Immobile should be persisted"
    assert imm.categoria == "A/2"
    
    sog = db.query(Soggetto).filter(Soggetto.codice_fiscale == "PRSSTN12A34B567C").first()
    assert sog is not None, "Soggetto should be persisted"
    
    tit = db.query(Titolarita).filter(Titolarita.immobile_id == imm.id).first()
    assert tit is not None, "Titolarita link should exist"
    assert tit.soggetto_id == sog.id

def test_params_persistence_context(client, db, respx_mock):
    payload = {
        "provincia": "MILANO",
        "comune": "MILANO",
        "foglio": "10",
        "particella": "20",
        "sezione": "A",
        "tipo_catasto": "T"
    }
    phash = get_params_hash(payload)
    
    respx_mock.post("http://visure-api:8000/visura").respond(
        json={"request_ids": ["ctx_1"], "status": "queued"}
    )
    
    resp = client.post("/visura", json=payload)
    assert resp.status_code == 200
    proxy_id = resp.json()["request_ids"][0]
    
    # Verify params are in QueryCache by hash
    db.expire_all()
    cached = db.query(QueryCache).filter(QueryCache.params_hash == phash).first()
    assert cached is not None, f"Cache entry should exist for hash {phash}"
    assert cached.params["provincia"] == "MILANO"
    assert cached.params["sezione"] == "A"
    
    # Simula completamento
    raw_results = {"results": []} 
    respx_mock.get("http://visure-api:8000/visura/ctx_1").respond(
        json={"status": "completed", "data": raw_results}
    )
    
    # Polling triggers normalization
    client.get(f"/visura/{proxy_id}")
    
    # Final check: updated_at was refreshed
    db.refresh(cached)
    assert cached.status == "completed"

def test_multi_subaltern_isolation(client, db, respx_mock):
    """
    Verifies that multiple subalterns from the same parcel 
    are persisted as separate Immobilie rows and not merged.
    """
    params = {
        "provincia": "ROMA",
        "comune": "ROMA",
        "foglio": "100",
        "particella": "200",
        "sezione": None,
        "tipo_catasto": "F"
    }
    
    # Mock data with Varying Headers (Sub and Subalterno)
    results_list = [
        {
            "immobile": {
                "Foglio": "100", "Particella": "200", "Sub": "10", 
                "Categoria": "A/2", "Rendita": "500,00"
            },
            "intestati": [{"Soggetto": "OWNER 10", "Titolarità": "Proprietà"}]
        },
        {
            "immobile": {
                "Foglio": "100", "Particella": "200", "Subalterno": "20", 
                "Categoria": "A/3", "Rendita": "600,00"
            },
            "intestati": [{"Soggetto": "OWNER 20", "Titolarità": "Proprietà"}]
        }
    ]
    
    # Mock upstream
    respx_mock.post("http://visure-api:8000/visura").respond(
        json={"request_ids": ["multi_p1"], "status": "queued"}
    )
    respx_mock.get("http://visure-api:8000/visura/multi_p1").respond(
        json={"status": "completed", "data": {"results": results_list}}
    )
    
    # Trigger proxy flow
    resp = client.post("/visura", json=params)
    proxy_id = resp.json()["request_ids"][0]
    client.get(f"/visura/{proxy_id}")
    
    # Verification
    db.commit()
    db.expire_all()
    
    immobili = db.query(Immobile).filter(
        Immobile.foglio == "100", 
        Immobile.particella == "200"
    ).all()
    
    assert len(immobili) == 2, f"Expected 2 immobili, found {len(immobili)}"
    subs = {imm.subalterno for imm in immobili}
    assert "10" in subs
    assert "20" in subs
