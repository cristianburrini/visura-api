import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from main import BrowserManager, VisuraRequest
from datetime import datetime

@pytest.mark.asyncio
async def test_browser_manager_busy_lock():
    # Setup BrowserManager with mocked components
    manager = BrowserManager()
    manager.auth_page = AsyncMock()
    manager.authenticated = True
    
    # Mock run_visura to simulate a successful run
    with patch('main.run_visura', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"status": "success"}
        
        request = VisuraRequest(
            request_id="test_req",
            tipo_catasto="F",
            provincia="TR",
            comune="TERNI",
            foglio="134",
            particella="10"
        )
        
        # We need to mock _ensure_authenticated to avoid real login
        with patch.object(BrowserManager, '_ensure_authenticated', new_callable=AsyncMock):
            # The bug was 'self.browser_manager' inside BrowserManager methods.
            # This call should NOT raise AttributeError if fixed.
            await manager.esegui_visura(request)
            
            # Verify flag was toggled (even if it's now False, we'd need a more complex mock to see it True during execution)
            assert manager.is_busy is False
            mock_run.assert_called_once()

@pytest.mark.asyncio
async def test_session_refresh_skips_when_busy():
    manager = BrowserManager()
    manager.auth_page = AsyncMock()
    manager.is_busy = True # Simulate active visura
    
    # This should return True (skip) without calling page.goto
    result = await manager._perform_session_refresh()
    
    assert result is True
    manager.auth_page.goto.assert_not_called()
