"""
Tests for the chat API.

Uses the same fresh-user-per-test dependency override pattern as
test_profile_api.py, for the same reason: isolate tests from each other
and from the shared dev-user singleton.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User


@pytest.fixture()
def client(db_session):
    from app.core.user_context import get_current_user
    from app.db.session import get_db

    user = User(email="chat-test-user@example.com")
    db_session.add(user)
    db_session.flush()

    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _switch_current_user(db_session, email: str) -> TestClient:
    """
    Swaps the identity override to a fresh user with the given email and
    returns a TestClient. Used within a single test (sequentially, not
    concurrently with another client fixture) to simulate a second user
    acting against the same app — app.dependency_overrides is a single
    global dict, so two independent client fixtures used together would
    silently clobber each other's override instead of representing two
    distinct users.
    """
    from app.core.user_context import get_current_user

    user = User(email=email)
    db_session.add(user)
    db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_send_message_without_conversation_id_creates_one(client):
    response = client.post("/api/v1/chat", json={"message": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"]
    assert body["reply"]["role"] == "assistant"
    assert "FinGuide+" in body["reply"]["content"]


def test_sending_a_second_message_continues_the_same_conversation(client):
    first = client.post("/api/v1/chat", json={"message": "hi"})
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/v1/chat",
        json={"message": "thanks", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id


def test_get_conversation_returns_full_history_in_order(client):
    first = client.post("/api/v1/chat", json={"message": "hi"})
    conversation_id = first.json()["conversation_id"]
    client.post("/api/v1/chat", json={"message": "thanks", "conversation_id": conversation_id})

    response = client.get(f"/api/v1/chat/{conversation_id}")
    assert response.status_code == 200
    body = response.json()
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert body["messages"][0]["content"] == "hi"
    assert body["messages"][2]["content"] == "thanks"


def test_unknown_conversation_id_returns_404(client):
    response = client.get(f"/api/v1/chat/{uuid.uuid4()}")
    assert response.status_code == 404


def test_malformed_conversation_id_returns_422(client):
    response = client.get("/api/v1/chat/not-a-uuid")
    assert response.status_code == 422


def test_cannot_post_to_another_users_conversation(client, db_session):
    mine = client.post("/api/v1/chat", json={"message": "hi"})
    my_conversation_id = mine.json()["conversation_id"]

    other_client = _switch_current_user(db_session, "other-chat-user@example.com")
    response = other_client.post(
        "/api/v1/chat",
        json={"message": "sneaky", "conversation_id": my_conversation_id},
    )
    assert response.status_code == 404


def test_cannot_get_another_users_conversation(client, db_session):
    mine = client.post("/api/v1/chat", json={"message": "hi"})
    my_conversation_id = mine.json()["conversation_id"]

    other_client = _switch_current_user(db_session, "other-chat-user-2@example.com")
    response = other_client.get(f"/api/v1/chat/{my_conversation_id}")
    assert response.status_code == 404


def test_empty_message_is_rejected(client):
    response = client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422


def test_context_sent_to_engine_is_bounded(client, monkeypatch):
    """
    Confirms the "conversation context is controlled" rule: regardless of
    how many messages exist, the engine only ever receives the last
    MAX_CONTEXT_MESSAGES turns.
    """
    from app.services import chat_service

    monkeypatch.setattr(chat_service, "MAX_CONTEXT_MESSAGES", 4)

    conversation_id = None
    for i in range(10):
        response = client.post(
            "/api/v1/chat",
            json={"message": f"message {i}", "conversation_id": conversation_id},
        )
        conversation_id = response.json()["conversation_id"]

    captured_history_lengths = []
    original_send_message = chat_service.send_message

    def _spy_send_message(db, user_id, message_text, conversation_id):
        from app.ai.chatbot import get_chatbot_engine

        real_engine = get_chatbot_engine()
        original_generate_reply = real_engine.generate_reply

        def _spy_generate_reply(history, user_message):
            captured_history_lengths.append(len(history))
            return original_generate_reply(history, user_message)

        real_engine.generate_reply = _spy_generate_reply
        try:
            return original_send_message(db, user_id, message_text, conversation_id)
        finally:
            real_engine.generate_reply = original_generate_reply

    monkeypatch.setattr(chat_service, "send_message", _spy_send_message)

    client.post("/api/v1/chat", json={"message": "one more", "conversation_id": conversation_id})

    assert captured_history_lengths == [4]
