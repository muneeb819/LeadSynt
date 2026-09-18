"""Test fixtures: isolated in-memory SQLite DB + API client + auth helpers.

Every test gets a fresh schema (migrations are exercised separately by the
`make db-upgrade` flow; here create_all from the same models).
"""

from __future__ import annotations

import os

os.environ["LEADSynt_CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["LEADSynt_LOG_JSON"] = "false"
os.environ["LEADSynt_LOG_LEVEL"] = "WARNING"
os.environ["LEADSynt_SECRET_KEY"] = "test-secret-key-not-for-production-0123456789"
os.environ["LEADSynt_ALLOW_SELF_REGISTRATION"] = "true"
os.environ["LEADSynt_WEBHOOK_SHARED_SECRET"] = "test-webhook-secret"

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.core.database as dbmod  # noqa: E402
from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  (register tables)
import app.main as mainmod  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    # Point every session consumer (app, deps, workers) at the test DB.
    dbmod.engine = engine
    dbmod.SessionLocal = session_factory
    mainmod.SessionLocal = session_factory
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    with TestClient(mainmod.app) as c:
        yield c


def _make_user(db, email: str, role: str, password: str = "Test-Password-123!") -> str:
    from sqlalchemy import select

    from app.auth.rbac import ensure_rbac_seeded
    from app.core.security import hash_password
    from app.models.user import Role, User, UserRole

    ensure_rbac_seeded(db)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, full_name=email.split("@")[0].title(),
                    password_hash=hash_password(password))
        db.add(user)
        db.flush()
        role_row = db.execute(select(Role).where(Role.name == role)).scalar_one()
        db.add(UserRole(user_id=user.id, role_id=role_row.id))
        db.flush()
    return user.id


def _token(user_id: str) -> str:
    from app.core.security import TokenType, create_token

    return create_token(user_id, TokenType.ACCESS)


@pytest.fixture()
def make_user(db_session):
    def _make(email: str, role: str) -> str:
        uid = _make_user(db_session, email, role)
        db_session.commit()
        return uid

    return _make


@pytest.fixture()
def auth_headers(make_user):
    """Returns a function: headers_for(role) -> Authorization header dict."""

    def _headers(role: str = "admin") -> dict:
        uid = make_user(f"{role}-{role}@example.com", role)
        return {"Authorization": f"Bearer {_token(uid)}"}

    return _headers


@pytest.fixture()
def admin_headers(auth_headers):
    return auth_headers("admin")


@pytest.fixture()
def operator_headers(auth_headers):
    return auth_headers("operator")


@pytest.fixture()
def viewer_headers(auth_headers):
    return auth_headers("viewer")


def make_ticket_payload(**overrides) -> dict:
    base = {
        "type_code": "PROCUREMENT",
        "market_sector": "Manufacturing",
        "product": "CNC spindles",
        "requirement": "Procurement requirement for 12 CNC spindles with warranty.",
        "intent_level": "HIGH",
        "urgency": "WEEK",
        "budget": 120000,
        "currency": "USD",
        "location": "Karachi, PK",
        "company": {"legal_name": "Acme Fab", "domain": "acme-fab.example.com",
                    "website": "https://acme-fab.example.com"},
        "contact": {"full_name": "John Buyer", "title": "Procurement Lead",
                    "work_email": "john.buyer@acme-fab.example.com",
                    "phone": "+92 21 555 0100"},
        "original_url": "https://devmarket.example.com/listings/t-1",
        "platform": "dev-marketplace",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def create_ticket(client, operator_headers):
    def _create(**overrides) -> dict:
        resp = client.post("/api/v1/tickets", json=make_ticket_payload(**overrides),
                           headers=operator_headers)
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]

    return _create
