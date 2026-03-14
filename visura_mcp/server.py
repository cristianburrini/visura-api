import os
import logging
import httpx
from typing import Optional, Union
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("visura-mcp")

# Initialize FastMCP server
mcp = FastMCP("Visura")

# API Configuration
VISURA_API_URL = os.getenv("VISURA_API_URL", "http://localhost:8000")

# --- Resources ---

@mcp.resource("protocol://docs/api_guide")
def get_api_guide() -> str:
    """Detailed human-readable guidance on interpreting cadastral data."""
    with open("visura_mcp/docs/api_guide.md", "r") as f:
        return f.read()

@mcp.resource("protocol://docs/openapi_spec")
def get_openapi_spec() -> str:
    """The machine-readable OpenAPI definition of the underlying Visura API."""
    with open("visura_mcp/docs/openapi_spec.yaml", "r") as f:
        return f.read()

@mcp.resource("protocol://docs/arazzo_workflows")
def get_arazzo_workflows() -> str:
    """An Arazzo Specification describing the standard 'journeys'."""
    with open("visura_mcp/docs/arazzo_workflows.yaml", "r") as f:
        return f.read()

@mcp.resource("protocol://docs/mcp_examples")
def get_mcp_examples() -> str:
    """Esempi pratici di utilizzo degli strumenti MCP con prompt, parametri e risposte attese."""
    with open("visura_mcp/docs/mcp_examples.md", "r") as f:
        return f.read()

# --- Tools ---

@mcp.tool()
async def avvia_ricerca_immobili_o_terreni(
    provincia: str,
    comune: str,
    foglio: str,
    particella: str,
    sezione: Optional[str] = None,
    tipo_catasto: Optional[str] = None
) -> str:
    """
    Avvia una nuova ricerca catastale (visura) per identificare gli immobili su una particella.
    
    PARAMETRI:
    - provincia: Nome della provincia (es: 'ROMA', 'TR'). Accetta anche sigle.
    - comune: Nome del comune (es: 'ROMA', 'TERNI').
    - foglio: Numero del foglio catastale.
    - particella: Numero della particella (mappale).
    - sezione: (Opzionale) Sezione censuaria/urbana. Omettere se non nota.
    - tipo_catasto: (Opzionale) 'T' per Terreni, 'F' per Fabbricati. Se omesso, esegue entrambe le ricerche.
    
    RITORNO:
    - Stringa contenente uno o più Request ID (es: 'req_F_123456789').
    
    NOTE:
    - Questa operazione aggiunge la richiesta a una coda sequenziale.
    - USA SEMPRE 'recupera_risultati_ricerca' con il Request ID ricevuto per ottenere i dati finali.
    - La ricerca può richiedere da 30 secondi a diversi minuti.
    """
    payload = {
        "provincia": provincia,
        "comune": comune,
        "foglio": foglio,
        "particella": particella,
        "sezione": sezione,
        "tipo_catasto": tipo_catasto
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{VISURA_API_URL}/visura", json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            ids = ", ".join(data.get("request_ids", []))
            return f"Ricerca avviata. Request IDs: {ids}. Status: {data.get('status')}. Usa recupera_risultati_ricerca per attendere il risultato."
        except httpx.HTTPStatusError as e:
            return f"API Error: {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

@mcp.tool()
async def richiedi_stato_ricerca(request_id: str) -> str:
    """
    Controlla lo stato immediato di una ricerca senza attendere.
    
    PARAMETRI:
    - request_id: L'ID della richiesta ricevuto da avvia_ricerca_immobili_o_terreni o avvia_ricerca_intestatari.
    
    RITORNO (in formato stringa JSON):
    - status: 'processing', 'completed', o 'error'.
    - data: Presente solo se status='completed'. Contiene gli immobili o gli intestatari trovati.
    - error: Presente se status='error' o 'completed' con errori (es: 'NESSUNA CORRISPONDENZA TROVATA').
    
    NOTE:
    - Se ricevi 'processing', attendi alcuni secondi prima di riprovare o usa 'recupera_risultati_ricerca'.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{VISURA_API_URL}/visura/{request_id}", timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return str(data)
        except httpx.HTTPStatusError as e:
            return f"API Error: {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

@mcp.tool()
async def recupera_risultati_ricerca(
    request_id: str,
    timeout_secondi: int = 30
) -> str:
    """
    Attende il completamento di una ricerca eseguendo polling automatico.
    
    PARAMETRI:
    - request_id: L'ID della richiesta da monitorare.
    - timeout_secondi: Tempo massimo di attesa per questa singola chiamata (default 30s).
    
    RITORNO (stringa JSON o messaggio di timeout):
    - Se completata: Il payload JSON dei dati catastali.
    - Se timeout: Un messaggio che invita a richiamare lo strumento.
    
    CONSIGLIO PER AGENTI:
    - NON smettere di cercare se ricevi un timeout. Le visure SISTER sono lente.
    - Richiama questo tool finché non ottieni 'status': 'completed' o un errore definitivo.
    - Intervallo di polling interno: 10 secondi.
    """
    import asyncio, time
    POLL_INTERVAL = 10  # secondi fissi — non modificare per evitare traffico eccessivo su SISTER
    deadline = time.monotonic() + timeout_secondi
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(f"{VISURA_API_URL}/visura/{request_id}", timeout=30.0)
                response.raise_for_status()
                data = response.json()
                if data.get("status") != "processing":
                    return str(data)
            except Exception as e:
                return f"Error durante il polling: {str(e)}"
            await asyncio.sleep(POLL_INTERVAL)
    return f"Timeout: la ricerca '{request_id}' non e' ancora disponibile. Riprova con recupera_risultati_ricerca."

@mcp.tool()
async def avvia_ricerca_intestatari(
    provincia: str,
    comune: str,
    foglio: str,
    particella: str,
    tipo_catasto: str,
    subalterno: Optional[Union[str, int]] = None,
    sezione: Optional[str] = None
) -> str:
    """
    Avvia la ricerca dei proprietari (intestatari) per un immobile specifico.
    Obbligatorio per i Fabbricati ('F') dopo aver identificato il subalterno con la ricerca immobili.
    
    PARAMETRI:
    - provincia/comune/foglio/particella: Come per la ricerca immobili.
    - tipo_catasto: 'F' (Fabbricati) o 'T' (Terreni).
    - subalterno: (Obbligatorio per F) Numero subalterno (es: '1', '501').
    - sezione: (Opzionale) Sezione censuaria/urbana.
    
    RITORNO:
    - Request ID specifico per la ricerca intestati (es: 'intestati_F_1_...').
    
    NOTE:
    - Per i Terreni ('T'), gli intestati sono solitamente inclusi già nella ricerca immobili.
    - Usa 'recupera_risultati_ricerca' con il nuovo ID per ottenere i nomi dei proprietari.
    """
    payload = {
        "provincia": provincia,
        "comune": comune,
        "foglio": foglio,
        "particella": particella,
        "tipo_catasto": tipo_catasto,
        "subalterno": str(subalterno) if subalterno is not None else None,
        "sezione": sezione
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{VISURA_API_URL}/visura/intestati", json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return f"Ricerca intestatari avviata. Request ID: {data.get('request_id')}. Status: {data.get('status')}. Usa recupera_risultati_ricerca per attendere il risultato."
        except httpx.HTTPStatusError as e:
            return f"API Error: {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

@mcp.tool()
async def mcp_visure_get_health() -> str:
    """Controlla lo stato di salute dell'infrastruttura sottostante (Visura API)."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{VISURA_API_URL}/health", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return f"API Status: {data.get('status')}. Authenticated: {data.get('authenticated')}. Queue Size: {data.get('queue_size')}."
        except httpx.HTTPStatusError as e:
            return f"API Health Error: {e.response.text}"
        except Exception as e:
            return f"Error connecting to API health endpoint: {str(e)}"

# --- Catalog Tools ---

@mcp.tool()
async def mcp_visure_search_comune(
    q: Optional[str] = None,
    provincia: Optional[str] = None,
    regione: Optional[str] = None,
    istat: Optional[str] = None
) -> str:
    """
    Cerca un comune nel catalogo statico per ottenere i codici corretti (Catastale/ISTAT).
    Usa questo tool per validare i nomi dei comuni prima di avviare una visura.
    
    PARAMETRI:
    - q: Testo per ricerca fuzzy (es: 'Terni', 'Ala di Stura').
    - provincia: Sigla provincia per filtrare (es: 'RM', 'TO').
    - regione: Nome regione per filtrare (es: 'Lazio').
    - istat: Codice ISTAT per ricerca esatta.
    
    RITORNO:
    - Lista di comuni con: denominazione, codice_catastale, sigla_provincia, regione, codice_istat.
    """
    params = {}
    if q: params["q"] = q
    if provincia: params["provincia"] = provincia
    if regione: params["regione"] = regione
    if istat: params["istat"] = istat
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{VISURA_API_URL}/catalog/comuni", params=params, timeout=10.0)
            response.raise_for_status()
            return str(response.json())
        except Exception as e:
            return f"Error searching catalog: {str(e)}"

@mcp.tool()
async def mcp_visure_list_parcels(
    codice_catastale: str,
    foglio: Optional[str] = None,
    sezione: Optional[str] = None
) -> str:
    """
    Elenca i fogli o le particelle registrate nel catalogo per un comune.
    Usa questo tool per scoprire quali sono gli identificativi validi di un comune.
    
    PARAMETRI:
    - codice_catastale: Il codice di 4 caratteri del comune (es: 'H501' per Roma, 'L117' per Terni).
    - foglio: (Opzionale) Se fornito, elenca le particelle di quel foglio. Se omesso, elenca tutti i fogli del comune.
    - sezione: (Opzionale) Filtra per sezione censuaria.
    
    RITORNO:
    - Lista di stringhe (numeri di foglio o numeri di particella).
    """
    async with httpx.AsyncClient() as client:
        try:
            if not foglio:
                # List sheets
                response = await client.get(f"{VISURA_API_URL}/catalog/comuni/{codice_catastale}/sheets", timeout=10.0)
                response.raise_for_status()
                return f"Fogli disponibili per {codice_catastale}: {str(response.json())}"
            else:
                # List parcels
                params = {"sezione": sezione} if sezione else {}
                response = await client.get(f"{VISURA_API_URL}/catalog/comuni/{codice_catastale}/sheets/{foglio}/parcels", params=params, timeout=10.0)
                response.raise_for_status()
                return f"Particelle disponibili per {codice_catastale} F.{foglio}: {str(response.json())}"
        except Exception as e:
            return f"Error listing catalog data: {str(e)}"

@mcp.tool()
async def mcp_visure_reload_catalog() -> str:
    """[ADMIN] Ricarica il catalogo statico di comuni e particelle dai file CSV montati sul server proxy."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{VISURA_API_URL}/catalog/reload", timeout=300.0)
            response.raise_for_status()
            return f"Catalogo ricaricato correttamente: {str(response.json())}"
        except Exception as e:
            return f"Error reloading catalog: {str(e)}"

if __name__ == "__main__":
    # Start the MCP server (stdio mode by default)
    mcp.run()
