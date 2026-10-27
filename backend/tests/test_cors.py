from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cors_allows_configured_origin():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_allows_any_localhost_port_in_development():
    """
    Regression test: Vite falls back to a different port (5174, 5175, ...)
    when the default is already in use. The backend must not silently
    reject that origin in development — see README troubleshooting notes.
    """
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5199",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5199"


def test_cors_rejects_non_localhost_origin():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
