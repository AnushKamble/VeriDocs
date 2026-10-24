def test_health_endpoint(test_client):
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "veridocs"
    assert "X-Correlation-ID" in response.headers
    assert "X-Process-Time-Ms" in response.headers


def test_models_status_endpoint(test_client):
    response = test_client.get("/api/v1/models/status")
    assert response.status_code == 200
    data = response.json()
    assert "generator" in data
    assert "retrieval" in data
    assert "auditor" in data
    assert data["retrieval"]["embedding_model_id"] == "BAAI/bge-small-en-v1.5"
    assert data["retrieval"]["faiss_installed"] is True
