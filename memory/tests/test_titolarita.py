import pytest
from memory.database import QueryCache, Immobile, Soggetto, Titolarita
from memory.main import get_params_hash

def test_titolarita_persistence_and_reuse(client, db, respx_mock):
    """
    Verifies that titolarita and soggetti are correctly persisted 
    and not duplicated on subsequent calls.
    """
    params = {
        "provincia": "ROMA",
        "comune": "ROMA",
        "foglio": "123",
        "particella": "456",
        "sezione": None,
        "tipo_catasto": "F",
        "subalterno": "1"
    }
    phash = get_params_hash(params)
    
    # Mock data with owners
    raw_results = {
        "results": [
            {
                "immobile": {
                    "Foglio": "123",
                    "Particella": "456",
                    "Subalterno": "1",
                    "Categoria": "A/1"
                },
                "intestati": [
                    {
                        "Soggetto": "MARIO ROSSI",
                        "Codice fiscale": "RSSMRA80A01H501Z",
                        "Titolarità": "Proprietà",
                        "Quota": "1/2"
                    },
                    {
                        "Soggetto": "LUIGI BIANCHI",
                        "Codice fiscale": "BNCLGU70B02L219X",
                        "Titolarità": "Proprietà",
                        "Quota": "1/2"
                    }
                ]
            }
        ]
    }
    
    # 1. First Call
    respx_mock.post("http://visure-api:8000/visura/intestati").respond(
        json={"request_id": "up_int_1", "status": "queued"}
    )
    respx_mock.get("http://visure-api:8000/visura/up_int_1").respond(
        json={"status": "completed", "data": raw_results}
    )
    
    resp = client.post("/visura/intestati", json=params)
    proxy_id = resp.json()["request_id"]
    
    # Polling triggers normalization
    client.get(f"/visura/{proxy_id}")
    
    # Verify DB
    db.expire_all()
    imm = db.query(Immobile).filter(Immobile.subalterno == "1").first()
    assert imm is not None
    
    soggetti = db.query(Soggetto).all()
    assert len(soggetti) == 2, f"Expected 2 soggetti, found {len(soggetti)}"
    
    titolarita = db.query(Titolarita).filter(Titolarita.immobile_id == imm.id).all()
    assert len(titolarita) == 2, f"Expected 2 ownership links, found {len(titolarita)}"
    
    # 2. Second Call (Same Data)
    # The proxy should return cached immediately
    # But let's assume we force another normalization somehow or just check that it doesn't double-persist
    # In this test, we can manually call normalize_visura_data again to be sure
    from memory.transformer import normalize_visura_data
    normalize_visura_data(db, raw_results["results"], params)
    db.commit()
    
    db.expire_all()
    soggetti_after = db.query(Soggetto).all()
    assert len(soggetti_after) == 2, "Soggetti should not be duplicated"
    
    tit_after = db.query(Titolarita).filter(Titolarita.immobile_id == imm.id).all()
    assert len(tit_after) == 2, "Titolarita should not be duplicated"

def test_titolarita_structure_variations(client, db, respx_mock):
    """
    Tests persistence with different key naming in intestati.
    """
    params = {
        "provincia": "MILANO",
        "comune": "MILANO",
        "foglio": "10",
        "particella": "20",
        "tipo_catasto": "T"
    }
    
    results = [
        {
            "immobile": {"Foglio": "10", "Particella": "20"},
            "intestati": [
                {
                    "Nominativo o denominazione": "AZIENDA AGRICOLA",
                    "Codice fiscale": "12345678901",
                    "Diritto o Titolarità": "Proprietà superficiaria",
                    "Quota": "1000/1000"
                }
            ]
        }
    ]
    
    from memory.transformer import normalize_visura_data
    normalize_visura_data(db, results, params)
    db.commit()
    
    db.expire_all()
    sog = db.query(Soggetto).filter(Soggetto.nominativo == "AZIENDA AGRICOLA").first()
    assert sog is not None
    
    tit = db.query(Titolarita).filter(Titolarita.soggetto_id == sog.id).first()
    assert tit is not None
    assert tit.tipo_titolarita == "Proprietà superficiaria"

def test_titolarita_single_result_wrap(client, db, respx_mock):
    """
    Tests that a single-dict response (common for visura/intestati)
    is correctly wrapped and persisted.
    """
    params = {
        "provincia": "ROMA",
        "comune": "ROMA",
        "foglio": "100",
        "particella": "200",
        "tipo_catasto": "F",
        "subalterno": "5"
    }
    
    # Structure returned by run_visura_immobile in core API
    raw_single_result = {
        "immobile": {"Foglio": "100", "Particella": "200", "Subalterno": "5", "Categoria": "C/2"},
        "intestati": [{"Soggetto": "SINGLE OWNER", "Titolarità": "Proprietà"}],
        "total_intestati": 1
    }
    
    respx_mock.post("http://visure-api:8000/visura/intestati").respond(
        json={"request_id": "up_single_1", "status": "queued"}
    )
    respx_mock.get("http://visure-api:8000/visura/up_single_1").respond(
        json={"status": "completed", "data": raw_single_result}
    )
    
    resp = client.post("/visura/intestati", json=params)
    proxy_id = resp.json()["request_id"]
    client.get(f"/visura/{proxy_id}")
    
    db.expire_all()
    imm = db.query(Immobile).filter(Immobile.subalterno == "5", Immobile.categoria == "C/2").first()
    assert imm is not None, "Single result immobile should be persisted"
    
    sog = db.query(Soggetto).filter(Soggetto.nominativo == "SINGLE OWNER").first()
    assert sog is not None, "Single result owner should be persisted"
    
    tit = db.query(Titolarita).filter(Titolarita.immobile_id == imm.id, Titolarita.soggetto_id == sog.id).first()
    assert tit is not None, "Titolarita link should exist for single result"

def test_shared_owner_separation(client, db, respx_mock):
    """
    Verfies that two different immobili with the same owner
    share the Soggetto record but have separate Titolarita links.
    """
    params = {"provincia": "ROMA", "comune": "ROMA"}
    
    # 2 different immobili, same owner
    results = [
        {
            "immobile": {"Foglio": "1", "Particella": "1", "Sub": "1"},
            "intestati": [{"Soggetto": "COMMON OWNER", "Codice fiscale": "CMNOWN12A34B567C"}]
        },
        {
            "immobile": {"Foglio": "1", "Particella": "1", "Sub": "2"},
            "intestati": [{"Soggetto": "COMMON OWNER", "Codice fiscale": "CMNOWN12A34B567C"}]
        }
    ]
    
    from memory.transformer import normalize_visura_data
    normalize_visura_data(db, results, params)
    db.commit()
    
    db.expire_all()
    soggetti = db.query(Soggetto).filter(Soggetto.codice_fiscale == "CMNOWN12A34B567C").all()
    assert len(soggetti) == 1, "Should only have ONE Soggetto even if they own multiple things"
    
    immobili = db.query(Immobile).all()
    assert len(immobili) == 2, "Should have two separate immobili"
    
    titolari = db.query(Titolarita).all()
    assert len(titolari) == 2, "Should have two separate Titolarita links"
    assert titolari[0].immobile_id != titolari[1].immobile_id
    assert titolari[0].soggetto_id == titolari[1].soggetto_id
