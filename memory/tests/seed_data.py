from sqlalchemy import text

def seed_test_catalog(db):
    """
    Populates the catalog tables with all test data required by the suite
    to satisfy strict validation.
    """
    # 1. Seed Comuni
    db.execute(text("""
        INSERT OR IGNORE INTO catalog_comuni (codice_catastale, denominazione, sigla_provincia, regione, codice_istat)
        VALUES 
        ('L117', 'TERNI', 'TR', 'UMBRIA', '055032'),
        ('H501', 'ROMA', 'RM', 'LAZIO', '058091'),
        ('H501_FULL', 'ROMA', 'ROMA', 'LAZIO', '058091'),
        ('L424', 'TRIESTE', 'TS', 'FRIULI VENEZIA GIULIA', '032006'),
        ('L424_FULL', 'TRIESTE', 'TRIESTE', 'FRIULI VENEZIA GIULIA', '032006'),
        ('F205', 'MILANO', 'MI', 'LOMBARDIA', '015146'),
        ('F205_FULL', 'MILANO', 'MILANO', 'LOMBARDIA', '015146'),
        ('ANY', 'ANY', 'ANY', 'ANY', '000001'),
        ('NEW', 'NEW', 'NEW', 'ANY', '000002')
    """))
    
    # 2. Seed Parcels
    parcels = [
        # Terni
        ('L117', None, '1', '1'),
        # Roma
        ('H501', None, '10', '100'),
        ('H501', None, '100', '200'),
        ('H501', None, '123', '456'),
        ('H501_FULL', None, '10', '100'),
        ('H501_FULL', None, '100', '200'),
        ('H501_FULL', None, '123', '456'), # for test_titolarita_persistence_and_reuse
        # Trieste
        ('L424', None, '1', '1'),
        ('L424_FULL', None, '1', '1'),
        # Milano
        ('F205', None, '10', '20'),
        ('F205_FULL', None, '10', '20'),
        ('F205_FULL', 'A', '10', '20'), # for test_params_persistence_context (section A)
        # Dummy labels for reliability tests (must match lowercase if test uses lowercase)
        ('ANY', None, 'any', 'any'),
        ('NEW', None, 'new', 'new')
    ]
    
    for p in parcels:
        db.execute(text("""
            INSERT OR IGNORE INTO catalog_parcels (codice_comune, sezione, foglio, particella)
            VALUES (:comune, :sezione, :foglio, :particella)
        """), {"comune": p[0], "sezione": p[1], "foglio": p[2], "particella": p[3]})
    
    db.commit()
