import csv
import logging
import os
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from memory.database import CatalogComune, CatalogParcel

logger = logging.getLogger(__name__)

def normalize_comune_data(row):
    return {
        "codice_catastale": row.get("CODCATASTALE", "").strip().upper(),
        "denominazione": row.get("DENOMINAZIONE_IT", "").strip().upper(),
        "sigla_provincia": row.get("SIGLAPROVINCIA", "").strip().upper(),
        "regione": row.get("Denominazione Regione", "").strip().upper(),
        "codice_istat": row.get("CODISTAT", "").strip()
    }

def normalize_parcel_data(row):
    sezione = row.get("Codice Sezione", "").strip()
    if sezione == "" or sezione == "_":
        sezione = None
        
    foglio = row.get("Numero Foglio", "").strip().lstrip('0')
    if not foglio:
        foglio = "0"
        
    return {
        "codice_comune": row.get("Codice Comune", "").strip().upper(),
        "sezione": sezione,
        "foglio": foglio,
        "particella": row.get("Particella", "").strip().lstrip('0') or "0"
    }

def reload_catalog(db: Session, comuni_csv_path: str, parcels_csv_path: str, province_mapping_csv_path: Optional[str] = None):
    """
    Transactional reload of the catalog.
    Uses UPSERT to avoid breaking foreign keys.
    """
    logger.info(f"Starting catalog reload from {comuni_csv_path} and {parcels_csv_path}")
    
    try:
        # 0. Load Province Mapping if provided
        province_map = {}
        if province_mapping_csv_path and os.path.exists(province_mapping_csv_path):
            with open(province_mapping_csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    province_map[row["sigla"].strip().upper()] = row["nome"].strip().upper()
            logger.info(f"Loaded {len(province_map)} province mappings")

        # 1. Load Comuni
        with open(comuni_csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Log headers to debug
            headers = reader.fieldnames
            logger.info(f"CSV Headers detected: {headers}")
            
            comuni = []
            for i, row in enumerate(reader):
                if i < 3:
                    logger.info(f"Sample row {i}: {row}")
                c = normalize_comune_data(row)
                if c["codice_catastale"]:
                    # Apply province name override if in mapping
                    if c["sigla_provincia"] in province_map:
                        c["provincia_upstream"] = province_map[c["sigla_provincia"]]
                    comuni.append(c)
        
        logger.info(f"Normalized {len(comuni)} comuni from CSV")
        for c in comuni:
            db.execute(
                text("""
                    INSERT INTO catalog_comuni (codice_catastale, denominazione, sigla_provincia, regione, codice_istat, provincia_upstream)
                    VALUES (:codice_catastale, :denominazione, :sigla_provincia, :regione, :codice_istat, :provincia_upstream)
                    ON CONFLICT (codice_catastale) DO UPDATE SET
                        denominazione = EXCLUDED.denominazione,
                        sigla_provincia = EXCLUDED.sigla_provincia,
                        regione = EXCLUDED.regione,
                        codice_istat = EXCLUDED.codice_istat,
                        provincia_upstream = COALESCE(EXCLUDED.provincia_upstream, catalog_comuni.provincia_upstream)
                """),
                {
                    "codice_catastale": c["codice_catastale"],
                    "denominazione": c["denominazione"],
                    "sigla_provincia": c["sigla_provincia"],
                    "regione": c["regione"],
                    "codice_istat": c["codice_istat"],
                    "provincia_upstream": c.get("provincia_upstream")
                }
            )
        
        # 3. Load Parcels with Batching to handle large files
        with open(parcels_csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            batch_size = 1000
            batch = []
            
            # Create a temporary staging table for parcels to handle deletions (Merge)
            db.execute(text("CREATE TEMP TABLE staging_parcels (LIKE catalog_parcels INCLUDING ALL) ON COMMIT DROP"))
            # Primary PK in catalog_parcels has ID auto-increment, let's remove it from staging to simplify batch insert
            db.execute(text("ALTER TABLE staging_parcels DROP COLUMN id"))
            
            for row in reader:
                p = normalize_parcel_data(row)
                if p["codice_comune"]:
                    batch.append(p)
                
                if len(batch) >= batch_size:
                    db.execute(
                        text("INSERT INTO staging_parcels (codice_comune, sezione, foglio, particella) VALUES (:codice_comune, :sezione, :foglio, :particella)"),
                        batch
                    )
                    batch = []
            
            if batch:
                db.execute(
                    text("INSERT INTO staging_parcels (codice_comune, sezione, foglio, particella) VALUES (:codice_comune, :sezione, :foglio, :particella)"),
                    batch
                )

            # Perform MERGE from staging to production
            
            # 0. Deduplicate production table first to ensure a clean state
            db.execute(text("""
                DELETE FROM catalog_parcels a USING (
                    SELECT MIN(id) as keep_id, codice_comune, sezione, foglio, particella
                    FROM catalog_parcels
                    GROUP BY codice_comune, sezione, foglio, particella
                    HAVING COUNT(*) > 1
                ) b
                WHERE a.codice_comune = b.codice_comune
                  AND (a.sezione IS NOT DISTINCT FROM b.sezione)
                  AND a.foglio = b.foglio
                  AND a.particella = b.particella
                  AND a.id > b.keep_id
            """))

            # A) UPSERT: Insert new rows only if they don't exist
            # We use WHERE NOT EXISTS with IS NOT DISTINCT FROM to handle NULLs correctly
            db.execute(text("""
                INSERT INTO catalog_parcels (codice_comune, sezione, foglio, particella)
                SELECT s.codice_comune, s.sezione, s.foglio, s.particella 
                FROM staging_parcels s
                WHERE NOT EXISTS (
                    SELECT 1 FROM catalog_parcels p
                    WHERE p.codice_comune = s.codice_comune
                      AND (p.sezione IS NOT DISTINCT FROM s.sezione)
                      AND p.foglio = s.foglio
                      AND p.particella = s.particella
                )
            """))
            
            # B) DELETE: Remove rows no longer in CSV
            db.execute(text("""
                DELETE FROM catalog_parcels
                WHERE NOT EXISTS (
                    SELECT 1 FROM staging_parcels s
                    WHERE s.codice_comune = catalog_parcels.codice_comune
                      AND (s.sezione IS NOT DISTINCT FROM catalog_parcels.sezione)
                      AND s.foglio = catalog_parcels.foglio
                      AND s.particella = catalog_parcels.particella
                )
            """))

        db.commit()
        logger.info("Catalog reload completed successfully.")
        return {"status": "success", "comuni_count": len(comuni)}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during catalog reload: {e}")
        raise
