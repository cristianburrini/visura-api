import pytest
from unittest.mock import patch, AsyncMock
from visura_mcp.server import request_visura, get_visura_result, request_intestati

@pytest.mark.asyncio
async def test_request_visura_success():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(status_code=200)
        mock_post.return_value.json.return_value = {
            "request_ids": ["req_T_1"],
            "status": "queued"
        }
        
        result = await request_visura("ROMA", "ROMA", "1", "1")
        assert "Request IDs: req_T_1" in result
        assert "Status: queued" in result

@pytest.mark.asyncio
async def test_get_visura_result_success():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200)
        mock_get.return_value.json.return_value = {
            "request_id": "req_T_1",
            "status": "completed",
            "data": {"some": "data"}
        }
        
        result = await get_visura_result("req_T_1")
        assert "'status': 'completed'" in result
        assert "'some': 'data'" in result

@pytest.mark.asyncio
async def test_request_intestati_success():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(status_code=200)
        mock_post.return_value.json.return_value = {
            "request_id": "intestati_1",
            "status": "queued"
        }
        
        result = await request_intestati("ROMA", "ROMA", "1", "1", "F", subalterno="1")
        assert "Request ID: intestati_1" in result
