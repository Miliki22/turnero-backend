"""Shared pytest fixtures."""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app.models.user  # noqa: F401
import app.models.client  # noqa: F401
import app.models.service  # noqa: F401
import app.models.appointment  # noqa: F401
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def ensure_schema() -> None:
    """Create DB schema required by tests when missing."""
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    """Return a test client for API requests."""
    return TestClient(app)


@pytest.fixture
def db_session() -> Session:
    """Provide a database session and cleanup auth test users."""
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM appointments"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'test-auth-%'"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'test-clients-%'"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'test-services-%'"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'test-appointments-%'"))
        db.execute(text("DELETE FROM clients WHERE full_name LIKE 'Test Client %'"))
        db.execute(text("DELETE FROM services WHERE name LIKE 'Service %'"))
        db.commit()
        yield db
        db.rollback()
        db.execute(text("DELETE FROM appointments"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'test-auth-%'"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'test-clients-%'"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'test-services-%'"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'test-appointments-%'"))
        db.execute(text("DELETE FROM clients WHERE full_name LIKE 'Test Client %'"))
        db.execute(text("DELETE FROM services WHERE name LIKE 'Service %'"))
        db.commit()
    finally:
        db.close()
