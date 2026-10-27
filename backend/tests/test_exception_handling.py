from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_unmatched_route_returns_structured_error():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert "message" in body["error"]


def test_wrong_method_returns_structured_http_error():
    # /api/v1/health only supports GET
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    body = response.json()
    assert body["error"]["type"] == "http_error"


def test_validation_error_returns_structured_details():
    # The health route takes no query params; passing a body to a GET
    # doesn't trigger validation, so we exercise the handler directly
    # against a route that does have typed parameters: FastAPI's own
    # OpenAPI schema endpoint accepts none, so instead we hit the health
    # endpoint with a malformed query string type via a stand-in route
    # is unnecessary — instead we unit-test the handler directly to keep
    # this brick free of throwaway endpoints.
    from fastapi.exceptions import RequestValidationError

    from app.core.exceptions import validation_exception_handler
    import asyncio

    exc = RequestValidationError(
        errors=[
            {
                "loc": ("query", "monthly_income"),
                "msg": "Input should be a valid number",
                "type": "float_parsing",
            }
        ]
    )
    response = asyncio.run(validation_exception_handler(request=None, exc=exc))
    assert response.status_code == 422
    import json

    body = json.loads(response.body)
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["details"] == [
        {"field": "query.monthly_income", "message": "Input should be a valid number"}
    ]


def test_unhandled_exception_returns_structured_500(monkeypatch):
    @app.get("/api/v1/_test_boom")
    def _boom():
        raise RuntimeError("boom")

    response = client.get("/api/v1/_test_boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["type"] == "internal_error"
    assert "message" in body["error"]

    # Remove the temporary route so it doesn't leak into other tests.
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/api/v1/_test_boom"]
