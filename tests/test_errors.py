def test_404_returns_envelope(client):
    response = client.get("/nope")
    assert response.status_code == 404
    
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "ROUTE_NOT_FOUND"
    assert data["error"]["status"] == 404
    assert "request_id" in data["error"]

def test_422_returns_field_details(client):
    # We will create a temporary endpoint just for this test to trigger a 422
    from app.main import app
    from pydantic import BaseModel
    
    class DummySchema(BaseModel):
        email: str
    
    @app.post("/test-validation")
    def test_route(data: DummySchema):
        return {"ok": True}
        
    response = client.post("/test-validation", json={"wrong_field": "value"})
    assert response.status_code == 422
    
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["details"][0]["field"] == "body.email"
    assert data["error"]["details"][0]["reason"] == "missing"

def test_request_id_header_present(client):
    response = client.get("/healthz")
    assert "X-Request-ID" in response.headers
    
def test_unhandled_exception_returns_500_envelope(client):
    from app.main import app
    @app.get("/test-crash")
    def crash_route():
        raise ValueError("Boom!")
        
    response = client.get("/test-crash")
    assert response.status_code == 500
    data = response.json()
    assert data["error"]["code"] == "INTERNAL_ERROR"
    # Ensure no traceback leaks
    assert "Traceback" not in response.text
    assert "ValueError" not in response.text