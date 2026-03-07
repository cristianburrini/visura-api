import os
import logging
import httpx
from typing import Optional
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

# --- Tools ---

@mcp.tool()
async def request_visura(
    provincia: str,
    comune: str,
    foglio: str,
    particella: str,
    sezione: Optional[str] = None,
    tipo_catasto: Optional[str] = None
) -> str:
    """
    Triggers a new cadastral search (visura) on SISTER.
    
    Args:
        provincia: Italian province name (e.g., 'ROMA')
        comune: Italian municipality name (e.g., 'ROMA')
        foglio: Cadastral sheet number
        particella: Cadastral parcel number
        sezione: Optional cadastral section (use '_' for empty/placeholder if needed)
        tipo_catasto: 'T' for Terreni (Land), 'F' for Fabbricati (Buildings). 
                     If omitted, both will be requested.
    
    Returns:
        A confirmation message with the request ID(s).
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
            return f"Visura requested successfully. Request IDs: {ids}. Status: {data.get('status')}."
        except httpx.HTTPStatusError as e:
            return f"API Error: {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

@mcp.tool()
async def get_visura_result(request_id: str) -> str:
    """
    Retrieves the result of a previously triggered visura.
    
    Args:
        request_id: The ID returned by request_visura (e.g., 'req_T_123456789')
    
    Returns:
        JSON string containing the visura data or current status.
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
async def request_intestati(
    provincia: str,
    comune: str,
    foglio: str,
    particella: str,
    tipo_catasto: str,
    subalterno: Optional[str] = None,
    sezione: Optional[str] = None
) -> str:
    """
    Triggers a specific search for property owners (intestati).
    Necessary for Fabbricati (Buildings) if you need the owners of a specific subalterno.
    
    Args:
        provincia: Italian province name
        comune: Italian municipality name
        foglio: Cadastral sheet number
        particella: Cadastral parcel number
        tipo_catasto: 'T' for Terreni, 'F' for Fabbricati
        subalterno: Required for Fabbricati.
        sezione: Optional cadastral section.
    
    Returns:
        A confirmation message with the request ID.
    """
    payload = {
        "provincia": provincia,
        "comune": comune,
        "foglio": foglio,
        "particella": particella,
        "tipo_catasto": tipo_catasto,
        "subalterno": subalterno,
        "sezione": sezione
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{VISURA_API_URL}/visura/intestati", json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return f"Intestati search requested. Request ID: {data.get('request_id')}. Status: {data.get('status')}."
        except httpx.HTTPStatusError as e:
            return f"API Error: {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

if __name__ == "__main__":
    # Start the MCP server (stdio mode by default)
    mcp.run()
