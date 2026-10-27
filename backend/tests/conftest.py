"""
Shared test fixtures for database-backed tests.

Tests always run against a dedicated test database
(`finguide_test` by default), never whatever `DATABASE_URL` happens to
be in `.env` — this is set here, before any `app.*` module is imported,
so pydantic-settings picks up the override (environment variables take
priority over the .env file). This avoids the exact class of
env/config-mismatch bug documented in the README's Troubleshooting
section: a developer's local `.env` should never be able to make the
test suite quietly point at (and mutate) their real dev database.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://finguide:test-only@localhost:5432/finguide_test",
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.db.base import Base
from app.core.config import settings

if "test" not in settings.database_url:
    raise RuntimeError(
        "Refusing to run tests: DATABASE_URL does not look like a test "
        f"database ({settings.database_url!r}). The test suite creates "
        "and DROPS all tables — running it against a real database would "
        "destroy data. Set DATABASE_URL to a database with 'test' in its "
        "name, or unset any shell-level DATABASE_URL override."
    )

engine = create_engine(settings.database_url)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    """Create all tables once for the test session, drop them afterward."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """
    A transactional session, rolled back after each test for isolation.

    Uses `join_transaction_mode="create_savepoint"` so that code under
    test calling `db.commit()` (as the real service layer does — see
    app/services/financial_profile_service.py) only commits a SAVEPOINT,
    not the outer transaction. The outer transaction — and everything
    committed inside it — is still fully rolled back here, keeping tests
    isolated from each other and from the real dev database.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
