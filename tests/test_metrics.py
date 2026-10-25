import pytest

def test_metrics_endpoint_returns_prometheus_text(client):
    """Verify that /metrics is public and returns valid Prometheus format."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    
    # Prometheus format usually includes HELP and TYPE lines
    content = res.text
    assert "# HELP" in content or "# TYPE" in content
    
    # It should track HTTP requests (this might require a request to happen first)
    # Trigger a request to increment the counter
    client.get("/healthz")
    
    res2 = client.get("/metrics")
    assert "http_requests_total" in res2.text