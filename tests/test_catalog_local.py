import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory.database import CatalogComune, CatalogParcel, init_db
from memory.catalog_manager import reload_catalog

# Configuration for local testing
DATABASE_URL = "postgresql://appuser:apppass@localhost:5433/visura_cache"
COMUNI_CSV = "catastoAssistant/staticData/comuniANPR_ISTAT.csv"
PARCELS_CSV = "catastoAssistant/staticData/parcelIndex.csv"
PROVINCE_CSV = "catastoAssistant/staticData/province_mapping.csv"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-catalog")

def test_search(db):
    print("\n--- Testing Search ---")
    # Test Comune Search
    res = db.query(CatalogComune).filter(CatalogComune.denominazione == "TERNI").first()
    if res:
        print(f"✅ Found Terni: {res.codice_catastale}, {res.sigla_provincia}")
        print(f"✅ Upstream Province: {res.provincia_upstream}")
        assert res.provincia_upstream == "TERNI"
        
        # Test Parcel Listing for Terni (L117)
        sheets_raw = db.query(CatalogParcel.foglio).filter(CatalogParcel.codice_comune == 'L117').distinct().limit(5).all()
        sheets = [s[0] for s in sheets_raw]
        print(f"✅ Found sheets for L117: {sheets}")
        for s in sheets:
            assert not s.startswith('0') or s == '0', f"Foglio {s} has leading zeros!"
    else:
        print("❌ Terni not found in catalog")

def run_reload():
    engine = create_engine(DATABASE_URL)
    init_db() # Ensure tables exist
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        print("--- Triggering Reload ---")
        result = reload_catalog(db, COMUNI_CSV, PARCELS_CSV, PROVINCE_CSV)
        print(f"Result: {result}")
        
        test_search(db)
    finally:
        db.close()

if __name__ == "__main__":
    run_reload()
