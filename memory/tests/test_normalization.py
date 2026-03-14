from memory.transformer import normalize_visura_data
from memory.database import Immobile, Soggetto, Titolarita

def test_normalize_visura_data(db):
    raw_data = {
        "results": [
            {
                "immobile": {
                    "Foglio": "10",
                    "Particella": "100",
                    "Subalterno": "1",
                    "Categoria": "A/2",
                    "Classe": "1",
                    "Consistenza": "5 vani",
                    "Rendita": "500,00",
                    "Indirizzo": "Via Roma 1",
                    "Partita": "1234"
                },
                "intestati": [
                    {
                        "Soggetto": "ROSSI MARIO",
                        "Codice fiscale": "RSSMRA80A01H501Z",
                        "Titolarità": "Proprietà 1/1"
                    }
                ]
            }
        ]
    }
    params = {
        "provincia": "Trieste",
        "comune": "Trieste",
        "tipo_catasto": "F",
        "sezione": None,
        "foglio": "10",
        "particella": "100",
        "subalterno": "1"
    }
    
    # Run twice to test idempotency and lookup
    normalize_visura_data(db, raw_data["results"], params)
    db.commit()
    
    # Verify Immobile
    immobile = db.query(Immobile).filter(Immobile.foglio == "10").first()
    assert immobile is not None, "Immobile should have been created"
    assert immobile.foglio == "10"
    assert immobile.particella == "100"
    assert immobile.rendita == "500,00"
    
    # Verify Soggetto
    soggetto = db.query(Soggetto).filter(Soggetto.nominativo == "ROSSI MARIO").first()
    assert soggetto is not None, "Soggetto should have been created"
    assert soggetto.nominativo == "ROSSI MARIO"
    assert soggetto.codice_fiscale == "RSSMRA80A01H501Z"
    
    # Verify Titolarita
    titolarita = db.query(Titolarita).filter(Titolarita.immobile_id == immobile.id).first()
    assert titolarita is not None, "Titolarita should have been created"
    assert titolarita.soggetto_id == soggetto.id
    assert titolarita.tipo_titolarita == "Proprietà 1/1"
