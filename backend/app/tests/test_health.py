"""PHASE 15 verification: health + metrics endpoints."""


def test_health_endpoint(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


def test_health_ready(client):
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_metrics_endpoint(client):
    client.get("/api/v1/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "counters" in r.json()


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "LeadSynt API"
