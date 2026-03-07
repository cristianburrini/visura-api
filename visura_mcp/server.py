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
    """Avvia una nuova ricerca catastale (visura) sul portale SISTER per foglio e particella. Se tipo_catasto è omesso vengono richiesti sia Terreni ('T') che Fabbricati ('F')."""
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
    """Recupera lo stato corrente di una ricerca catastale. Restituisce 'processing' se ancora in corso, 'completed' con i dati o 'error'. Per un'attesa passiva usa recupera_risultati_ricerca."""
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
    """Aspetta il completamento di una ricerca (immobili o intestatari) e restituisce il risultato finale.
    Funziona con qualsiasi request_id restituito da avvia_ricerca_immobili_o_terreni o avvia_ricerca_intestatari.
    Esegue polling ogni 10 secondi (fisso, per non sovraccaricare il portale SISTER).
    IMPORTANTE: se il risultato non e' ancora disponibile entro il timeout, restituisce un messaggio
    di timeout — NON e' un errore. In quel caso l'agente deve richiamare recupera_risultati_ricerca con lo stesso
    request_id per continuare ad aspettare. Le visure possono richiedere 1-3 minuti."""
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
    """Avvia una ricerca degli intestatari (proprietari) di un immobile specifico. Necessario per i Fabbricati ('F') per ottenere i proprietari di un determinato subalterno. Usa recupera_risultati_ricerca con il request_id restituito per ottenere il risultato."""
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

if __name__ == "__main__":
    # Start the MCP server (stdio mode by default)
    mcp.run()
