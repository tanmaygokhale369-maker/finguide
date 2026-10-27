"""Password and short-lived bearer-token helpers (stdlib only)."""
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid

from fastapi import HTTPException, status

from app.core.config import settings

_DEV_SIGNING_KEY = "development-only-signing-key-change-before-production"


def _key() -> bytes:
    return (settings.secret_key or _DEV_SIGNING_KEY).encode("utf-8")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt${}${}${}".format(
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(derived).decode(),
        "16384",
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, salt_text, digest_text, n_text = encoded.split("$")
        if algorithm != "scrypt" or int(n_text) != 16384:
            return False
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()
    signing_input = (encode({"alg": "HS256", "typ": "JWT"}) + "." + encode({"sub": str(user_id), "iss": "finguide-plus", "iat": int(time.time()), "exp": int(time.time()) + settings.access_token_ttl_minutes * 60})).encode()
    signature = hmac.new(_key(), signing_input, hashlib.sha256).digest()
    return signing_input.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def decode_access_token(token: str) -> uuid.UUID:
    try:
        header_text, payload_text, signature_text = token.split(".")
        signing_input = (header_text + "." + payload_text).encode()
        expected = hmac.new(_key(), signing_input, hashlib.sha256).digest()
        signature = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        if not hmac.compare_digest(expected, signature):
            raise ValueError("signature")
        header = json.loads(base64.urlsafe_b64decode(header_text + "=" * (-len(header_text) % 4)))
        if header != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError("algorithm")
        body = json.loads(base64.urlsafe_b64decode(payload_text + "=" * (-len(payload_text) % 4)))
        if body.get("iss") != "finguide-plus" or int(body["exp"]) <= int(time.time()):
            raise ValueError("expired")
        return uuid.UUID(body["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired access token.", headers={"WWW-Authenticate": "Bearer"})
