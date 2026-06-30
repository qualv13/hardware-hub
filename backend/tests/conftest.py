import os
import pathlib

import pytest

# Configure an isolated test DB and force the AI fallbacks BEFORE importing
# the app (settings read env at import time).
os.environ["DATABASE_URL"] = "sqlite:///./test_hub.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ADMIN_EMAIL"] = "admin@booksy.com"
os.environ["ADMIN_PASSWORD"] = "admin123"

_DB = pathlib.Path("test_hub.db")
if _DB.exists():
    _DB.unlink()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    # Entering the context manager runs the lifespan -> seeds the audited data.
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post(
        "/api/auth/login", json={"email": "admin@booksy.com", "password": "admin123"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
