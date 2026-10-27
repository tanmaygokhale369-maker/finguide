from app.core.user_context import get_current_user
from starlette.requests import Request


def _request():
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b"", "server": ("testserver", 80), "client": ("testclient", 123)})


def test_dev_user_is_created_on_first_call(db_session):
    user = get_current_user(request=_request(), db=db_session, credentials=None)
    assert user.email == "dev@finguide.local"
    assert user.id is not None


def test_dev_user_is_reused_on_subsequent_calls(db_session):
    first = get_current_user(request=_request(), db=db_session, credentials=None)
    second = get_current_user(request=_request(), db=db_session, credentials=None)
    assert first.id == second.id


def test_dev_user_context_refuses_outside_development(db_session, monkeypatch):
    from fastapi import HTTPException

    from app.core import user_context

    monkeypatch.setattr(user_context.settings, "environment", "production")

    try:
        raised = False
        try:
            get_current_user(request=_request(), db=db_session, credentials=None)
        except HTTPException as exc:
            raised = True
            assert exc.status_code == 401
        assert raised, "expected get_current_user to refuse outside development"
    finally:
        monkeypatch.setattr(user_context.settings, "environment", "development")
