import os
import sys
import asyncio
import httpx
import pytest
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment variables for testing before importing app
os.environ["DATABASE_URL"] = "postgresql://appuser:apppass@localhost:5433/visura_cache"
os.environ["UPSTREAM_API_URL"] = "http://localhost:8000" # Dummy since we won't call it if validation fails

from memory.main import app

client = TestClient(app)

def test_catalog_search():
    print("\n--- Testing Catalog Search Endpoints ---")
    
    # 1. Fuzzy search for Terni
    response = client.get("/catalog/comuni?q=terni")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["codice_catastale"] == "L117"
    print(f"✅ Fuzzy search 'terni' found: {data[0]['denominazione']}")

    # 2. List sheets for Terni
    response = client.get("/catalog/comuni/L117/sheets")
    assert response.status_code == 200
    sheets = response.json()
    assert "1" in sheets
    print(f"✅ Sheets for L117: {sheets[:5]}...")

def test_visura_validation():
    print("\n--- Testing Visura Validation ---")
    
    # 1. Invalid Comune
    payload = {
        "provincia": "TR",
        "comune": "CITTÀ INESISTENTE",
        "foglio": "1",
        "particella": "1"
    }
    response = client.post("/visura", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "invalid_fields" in data["detail"]
    assert "comune" in data["detail"]["invalid_fields"]
    print(f"✅ Blocked invalid comune as expected. Error: {data['detail']['error']}")

    # 2. Invalid Foglio for valid Comune
    payload = {
        "provincia": "TR",
        "comune": "TERNI",
        "foglio": "9999",
        "particella": "1"
    }
    response = client.post("/visura", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "foglio" in data["detail"]["invalid_fields"]
    print(f"✅ Blocked invalid foglio as expected. Error: {data['detail']['error']}")

def test_upstream_overrides():
    print("\n--- Testing Upstream Overrides ---")
    from memory.database import SessionLocal, CatalogComune
    
    db = SessionLocal()
    try:
        # 1. Inject an override for Terni
        comune = db.query(CatalogComune).filter(CatalogComune.codice_catastale == "L117").first()
        comune.denominazione_upstream = "TERNI_UPSTREAM"
        comune.provincia_upstream = "TR_UPSTREAM"
        db.commit()
        
        # 2. Call validation function (internal check since /visura calls it)
        from memory.main import validate_and_canonicalize_params
        params = {
            "provincia": "TR",
            "comune": "TERNI",
            "foglio": "0001", # Input with leading zeros should be normalized
            "particella": "1"
        }
        canonical, upstream = validate_and_canonicalize_params(db, params)
        
        assert upstream["comune"] == "TERNI_UPSTREAM"
        assert upstream["provincia"] == "TR_UPSTREAM"
        print("✅ Upstream overrides applied correctly")
        
        # Cleanup
        comune.denominazione_upstream = None
        comune.provincia_upstream = None
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    test_catalog_search()
    test_visura_validation()
    test_upstream_overrides()
