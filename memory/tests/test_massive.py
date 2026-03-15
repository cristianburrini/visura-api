import pytest
import asyncio
from unittest.mock import MagicMock, patch
from memory.database import ScheduledVisura, QueryCache, CatalogComune, CatalogParcel, Immobile, Soggetto, Titolarita
from memory.main import app, get_params_hash
from memory.worker import process_queue, submit_item, check_item_status

# Standard test comuni/parcels are now seeded globally in conftest.py via seed_test_catalog.

def test_schedule_massive_success(client, db):
    payload = {
        "scenario": 1,
        "provincia": "RM",
        "comune": "ROMA",
        "targets": [
            {"foglio": "10", "particella": "100"},
            {"foglio": "10", "particella": "101"} # This will fail validation but for now we only check scheduling
        ]
    }
    
    # We need to add the second parcel to catalog to pass the is_already_done validation 
    # which uses validate_and_canonicalize_params internally (wait, it doesn't anymore, 
    # I changed it to simple check).
    # Ah, is_already_done in main.py doesn't validate against catalog, just checks cache/scheduled.
    
    resp = client.post("/massive/schedule", json=payload)
    assert resp.status_code == 200
    assert resp.json()["scheduled"] == 4
    
    scheduled = db.query(ScheduledVisura).all()
    assert len(scheduled) == 4
    assert scheduled[0].provincia == "RM"
    assert scheduled[0].target_type == "PARTICELLA"

def test_schedule_massive_skip_duplicates(client, db):
    # First schedule
    payload = {
        "scenario": 1, "provincia": "RM", "comune": "ROMA",
        "targets": [{"foglio": "10", "particella": "100"}]
    }
    client.post("/massive/schedule", json=payload)
    
    # Second schedule with same target
    resp = client.post("/massive/schedule", json=payload)
    assert resp.json()["scheduled"] == 0
    assert resp.json()["skipped"] == 2

@pytest.mark.asyncio
async def test_worker_process_queue(db, respx_mock):
    # Create a pending item
    item = ScheduledVisura(
        target_type="PARTICELLA", scenario=1,
        provincia="RM", comune="ROMA", foglio="10", particella="100",
        status="pending"
    )
    db.add(item)
    db.commit()
    
    # Mock upstream submission
    respx_mock.post("http://visure-api:8000/visura").respond(
        json={"request_ids": ["upstream_1"], "status": "queued"}
    )
    
    # Run process_queue
    await process_queue(db)
    
    db.refresh(item)
    if item.status == "error":
        print(f"DEBUG: Error message: {item.error_message}")
        
    assert item.status == "submitted"
    assert item.upstream_id == "upstream_1"

@pytest.mark.asyncio
async def test_scenario3_flow(db, respx_mock):
    # Scenario 3: Property search completes -> schedule owners
    item = ScheduledVisura(
        target_type="PARTICELLA", scenario=3,
        provincia="RM", comune="ROMA", foglio="10", particella="100",
        status="submitted", upstream_id="up_3"
    )
    db.add(item)
    db.commit()
    
    # Mock upstream result with multiple subalterns
    mock_data = {
        "status": "completed",
        "data": {
            "results": [
                {"immobile": {"Foglio": "10", "Particella": "100", "Sub": "1"}},
                {"immobile": {"Foglio": "10", "Particella": "100", "Subalterno": "2"}}
            ]
        }
    }
    respx_mock.get("http://visure-api:8000/visura/up_3").respond(json=mock_data)
    
    await check_item_status(db, item)
    
    db.refresh(item)
    assert item.status == "done"
    
    # Check if owners were scheduled
    owners = db.query(ScheduledVisura).filter(ScheduledVisura.target_type == "SUBALTERNO").all()
    assert len(owners) == 2
    assert owners[0].subalterno == "1"
    assert owners[1].subalterno == "2"
    assert owners[0].scenario == 3

@pytest.mark.asyncio
async def test_worker_persistence_fabbricati(db, respx_mock):
    # 1. Create a pending item for Fabbricati
    item = ScheduledVisura(
        target_type="PARTICELLA", scenario=1,
        provincia="RM", comune="ROMA", foglio="10", particella="100",
        tipo_catasto="F", status="submitted", upstream_id="up_f"
    )
    db.add(item)
    db.commit()
    
    # 2. Mock upstream result
    mock_data = {
        "status": "completed",
        "data": {
            "immobili": [
                {"immobile": {"Foglio": "10", "Particella": "100", "Sub": "501", "Categoria": "A/2"}}
            ]
        }
    }
    respx_mock.get("http://visure-api:8000/visura/up_f").respond(json=mock_data)
    
    # 3. Process
    await check_item_status(db, item)
    
    # 4. Verify DB
    immobile = db.query(Immobile).filter(Immobile.subalterno == "501").first()
    assert immobile is not None
    assert immobile.tipo_catasto == "F"
    assert immobile.categoria == "A/2"

@pytest.mark.asyncio
async def test_worker_persistence_terreni(db, respx_mock):
    # 1. Create a pending item for Terreni
    item = ScheduledVisura(
        target_type="PARTICELLA", scenario=1,
        provincia="RM", comune="ROMA", foglio="10", particella="200",
        tipo_catasto="T", status="submitted", upstream_id="up_t"
    )
    db.add(item)
    db.commit()
    
    # 2. Mock upstream result (Terreni often don't have subaltern but have owners in same visura)
    mock_data = {
        "status": "completed",
        "data": {
            "results": [
                {
                    "immobile": {"Foglio": "10", "Particella": "200", "Qualità": "ULIVETO"},
                    "intestati": [{"Soggetto": "ROSSI MARIO", "Quota": "1/1"}]
                }
            ]
        }
    }
    respx_mock.get("http://visure-api:8000/visura/up_t").respond(json=mock_data)
    
    # 3. Process
    await check_item_status(db, item)
    
    # 4. Verify DB
    immobile = db.query(Immobile).filter(Immobile.particella == "200", Immobile.tipo_catasto == "T").first()
    assert immobile is not None
    
    titolarita = db.query(Titolarita).filter(Titolarita.immobile_id == immobile.id).first()
    assert titolarita is not None
    
    soggetto = db.query(Soggetto).filter(Soggetto.id == titolarita.soggetto_id).first()
    assert soggetto.nominativo == "ROSSI MARIO"

