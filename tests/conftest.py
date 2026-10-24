import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Load .env so we get TEST_DATABASE_URL
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Safety check: Refuse to run if we aren't on a test DB
test_url = os.environ.get("TEST_DATABASE_URL")
if not test_url:
    raise RuntimeError("TEST_DATABASE_URL is not set in .env")

db_name = test_url.rsplit("/", 1)[-1].split("?")[0]
if not (db_name.endswith("_test") or "localhost" in test_url or "127.0.0.1" in test_url):
    raise RuntimeError(f"Refusing to run tests on non-test database: {db_name}")

# Override environment variables BEFORE importing app
os.environ["DATABASE_URL"] = test_url
os.environ["DIRECT_DATABASE_URL"] = test_url
os.environ["JWT_SECRET_KEY"] = "test-secret-test-secret-test-secret-123"
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
from app.main import app
from app.db import engine, SessionLocal

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Run Alembic migrations to set up the schema exactly like production
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    yield

@pytest.fixture(autouse=True)
def clean_tables():
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE idempotency_keys, chunks, documents, hubs, users RESTART IDENTITY CASCADE"))
        conn.commit()
    yield

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()