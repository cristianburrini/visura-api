import pytest
import asyncio
from unittest.mock import MagicMock, patch
from memory.database import ScheduledVisura, QueryCache, CatalogComune, CatalogParcel
from memory.main import app, get_params_hash
from memory.worker import process_queue, submit_item, check_item_status

@pytest.fixture
def mock_catalog(db):
    # Setup a mock comune and parcel in the DB
    comune = CatalogComune(
        codice_catastale="H501",
        denominazione="ROMA",
        sigla_provincia="RM",
        regione="Lazio"
    )
    db.add(comune)
    db.commit()
    
    parcel = CatalogParcel(
        codice_comune="H501",
        foglio="10",
        particella="100"
    )
    db.add(parcel)
    db.commit()
    return comune, parcel

def test_schedule_massive_success(client, db, mock_catalog):
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
    assert resp.json()["scheduled"] == 2
    
    scheduled = db.query(ScheduledVisura).all()
    assert len(scheduled) == 2
    assert scheduled[0].provincia == "RM"
    assert scheduled[0].target_type == "PARTICELLA"

def test_schedule_massive_skip_duplicates(client, db, mock_catalog):
    # First schedule
    payload = {
        "scenario": 1, "provincia": "RM", "comune": "ROMA",
        "targets": [{"foglio": "10", "particella": "100"}]
    }
    client.post("/massive/schedule", json=payload)
    
    # Second schedule with same target
    resp = client.post("/massive/schedule", json=payload)
    assert resp.json()["scheduled"] == 0
    assert resp.json()["skipped"] == 1

@pytest.mark.asyncio
async def test_worker_process_queue(db, respx_mock, mock_catalog):
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
