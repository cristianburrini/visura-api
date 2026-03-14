import logging
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from memory.database import Immobile, Soggetto, Titolarita

logger = logging.getLogger(__name__)

def get_flexible_attr(data: Dict[str, Any], keys: List[str]) -> Any:
    """Helper to find a value in a dictionary using multiple possible keys (case-insensitive)."""
    if not data:
        return None
    for k in keys:
        # Exact match first
        if k in data:
            return data[k]
        # Case insensitive match
        for data_key in data.keys():
            if data_key.lower() == k.lower():
                return data[data_key]
    return None

def normalize_visura_data(db: Session, results: List[Dict[str, Any]], params: Dict[str, Any]):
    """
    Normalizes the raw JSON response from visure-api into the relational tables.
    """
    
    logger.info(f"Normalizing {len(results)} results")
    
    # Define mapping variations for common headers
    MAPPING = {
        "foglio": ["Foglio", "Fg", "Fg."],
        "particella": ["Particella", "Part.", "Part", "Mappale", "Mapp."],
        "subalterno": ["Subalterno", "Sub", "Sub."],
        "categoria": ["Categoria", "Cat."],
        "classe": ["Classe", "Cl."],
        "consistenza": ["Consistenza", "Cons."],
        "rendita": ["Rendita", "Rend."],
        "indirizzo": ["Indirizzo", "Ubicazione"],
        "partita": ["Partita", "Mod."]
    }

    for res in results:
        imm_raw = res.get("immobile", {})
        int_raw = res.get("intestati", [])
        
        # 1. Extract values robustly
        foglio = get_flexible_attr(imm_raw, MAPPING["foglio"]) or params.get("foglio")
        particella = get_flexible_attr(imm_raw, MAPPING["particella"]) or params.get("particella")
        subalterno = get_flexible_attr(imm_raw, MAPPING["subalterno"]) or params.get("subalterno")
        
        # 2. Handle Immobile Lookup
        query = db.query(Immobile).filter(
            Immobile.provincia == params.get("provincia"),
            Immobile.comune == params.get("comune"),
            Immobile.foglio == foglio,
            Immobile.particella == particella
        )
        
        if subalterno:
            query = query.filter(Immobile.subalterno == str(subalterno))
        else:
            query = query.filter(Immobile.subalterno.is_(None))
            
        # Handle sezione
        sezione = params.get("sezione")
        if sezione:
            query = query.filter(Immobile.sezione == sezione)
        else:
            query = query.filter(Immobile.sezione.is_(None))
            
        immobile = query.first()
        
        if not immobile:
            logger.info(f"Creating new Immobile entry for F.{foglio} P.{particella} Sub.{subalterno}")
            immobile = Immobile(
                provincia=params.get("provincia"),
                comune=params.get("comune"),
                sezione=params.get("sezione"),
                foglio=foglio,
                particella=particella,
                subalterno=str(subalterno) if subalterno else None,
                tipo_catasto=params.get("tipo_catasto"),
                categoria=get_flexible_attr(imm_raw, MAPPING["categoria"]),
                classe=get_flexible_attr(imm_raw, MAPPING["classe"]),
                consistenza=get_flexible_attr(imm_raw, MAPPING["consistenza"]),
                rendita=get_flexible_attr(imm_raw, MAPPING["rendita"]),
                indirizzo=get_flexible_attr(imm_raw, MAPPING["indirizzo"]),
                partita=get_flexible_attr(imm_raw, MAPPING["partita"])
            )
            db.add(immobile)
            db.flush() # Ensure ID is generated for Titolarita
            
        # 3. Handle Soggetti and Titolarita
        for i_raw in int_raw:
            nominativo = i_raw.get("Soggetto") or i_raw.get("Nominativo o denominazione")
            cf = i_raw.get("Codice fiscale")
            
            if not nominativo:
                continue
                
            # Try to match soggetto
            soggetto = None
            if cf:
                soggetto = db.query(Soggetto).filter(Soggetto.codice_fiscale == cf).first()
            
            if not soggetto:
                soggetto = db.query(Soggetto).filter(Soggetto.nominativo == nominativo).first()
                
            if not soggetto:
                soggetto = Soggetto(
                    codice_fiscale=cf,
                    nominativo=nominativo
                )
                db.add(soggetto)
                db.flush()
            
            # 4. Create Titolarita link (Always linked to this specific immobile record)
            tit_exists = db.query(Titolarita).filter(
                Titolarita.immobile_id == immobile.id,
                Titolarita.soggetto_id == soggetto.id,
                Titolarita.tipo_titolarita == (i_raw.get("Diritto o Titolarità") or i_raw.get("Titolarità")),
                Titolarita.quota == i_raw.get("Quota"),
                Titolarita.regime == i_raw.get("Regime")
            ).first()
            
            if not tit_exists:
                tit = Titolarita(
                    immobile_id=immobile.id,
                    soggetto_id=soggetto.id,
                    tipo_titolarita=i_raw.get("Diritto o Titolarità") or i_raw.get("Titolarità"),
                    quota=i_raw.get("Quota"),
                    regime=i_raw.get("Regime")
                )
                db.add(tit)
    
