from unittest.mock import patch
from app.services.observability import log_ai_call

def test_log_ai_call_success(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    
    def dummy_ai(): return "ok"
    
    result = log_ai_call("test_op", "user1", "hub1", dummy_ai)
    assert result == "ok"
    assert '"event": "ai_call"' in caplog.text
    assert '"operation": "test_op"' in caplog.text
    assert '"status": "success"' in caplog.text