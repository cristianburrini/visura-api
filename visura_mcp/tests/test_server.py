import pytest
import respx
from visura_mcp.server import avvia_ricerca_immobili_o_terreni, richiedi_stato_ricerca, avvia_ricerca_intestatari, mcp_visure_get_health

@pytest.mark.asyncio
@respx.mock
async def test_avvia_ricerca_immobili_o_terreni_success():
    respx.post("http://localhost:8000/visura").respond(200, json={
        "request_ids": ["req_T_1"],
        "status": "queued"
    })
    
    result = await avvia_ricerca_immobili_o_terreni("ROMA", "ROMA", "1", "1")
    assert "Request IDs: req_T_1" in result
    assert "Status: queued" in result

@pytest.mark.asyncio
@respx.mock
async def test_richiedi_stato_ricerca_success():
    respx.get("http://localhost:8000/visura/req_T_1").respond(200, json={
        "request_id": "req_T_1",
        "status": "completed",
        "data": {"some": "data"}
    })
    
    result = await richiedi_stato_ricerca("req_T_1")
    assert "'status': 'completed'" in result
    assert "'some': 'data'" in result

@pytest.mark.asyncio
@respx.mock
async def test_avvia_ricerca_intestatari_success():
    respx.post("http://localhost:8000/visura/intestati").respond(200, json={
        "request_id": "intestati_1",
        "status": "queued"
    })
    
    result = await avvia_ricerca_intestatari("ROMA", "ROMA", "1", "1", "F", subalterno="1")
    assert "Request ID: intestati_1" in result

@pytest.mark.asyncio
@respx.mock
async def test_get_health_success():
    respx.get("http://localhost:8000/health").respond(200, json={
        "status": "healthy",
        "authenticated": True,
        "queue_size": 0
    })
    
    result = await mcp_visure_get_health()
    assert "API Status: healthy" in result
    assert "Authenticated: True" in result
    assert "Queue Size: 0" in result
