from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_running_status():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"


def test_health_endpoint_returns_ok():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app_name" in body
    assert "environment" in body


def test_readiness_endpoint_confirms_real_db_connection():
    """Exercises the actual test Postgres database — not mocked."""
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "database": "ok"}


def test_readiness_endpoint_reports_503_when_db_unreachable():
    from app.db.session import get_db

    def _broken_db():
        class _Broken:
            def execute(self, *args, **kwargs):
                raise RuntimeError("simulated connection failure")

        yield _Broken()

    app.dependency_overrides[get_db] = _broken_db
    try:
        response = client.get("/api/v1/readiness")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["type"] == "http_error"
    finally:
        app.dependency_overrides.clear()
