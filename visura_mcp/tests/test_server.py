import pytest
import respx
from visura_mcp.server import request_visura, get_visura_result, request_intestati

@pytest.mark.asyncio
@respx.mock
async def test_request_visura_success():
    respx.post("http://localhost:8000/visura").respond(200, json={
        "request_ids": ["req_T_1"],
        "status": "queued"
    })
    
    result = await request_visura("ROMA", "ROMA", "1", "1")
    assert "Request IDs: req_T_1" in result
    assert "Status: queued" in result

@pytest.mark.asyncio
@respx.mock
async def test_get_visura_result_success():
    respx.get("http://localhost:8000/visura/req_T_1").respond(200, json={
        "request_id": "req_T_1",
        "status": "completed",
        "data": {"some": "data"}
    })
    
    result = await get_visura_result("req_T_1")
    assert "'status': 'completed'" in result
    assert "'some': 'data'" in result

@pytest.mark.asyncio
@respx.mock
async def test_request_intestati_success():
    respx.post("http://localhost:8000/visura/intestati").respond(200, json={
        "request_id": "intestati_1",
        "status": "queued"
    })
    
    result = await request_intestati("ROMA", "ROMA", "1", "1", "F", subalterno="1")
    assert "Request ID: intestati_1" in result
