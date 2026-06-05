"""
Wave 2 API tests — pytest + FastAPI TestClient (httpx)

Run from the api/ directory:
    pytest tests/test_api.py
"""
import sys
import os

# Ensure the api/ directory is on the path so `import main` works
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# Patch DB startup check so tests don't need a real database
@pytest.fixture(autouse=True, scope="session")
def skip_startup_db_check():
    with patch("main.get_connection") as mock_conn:
        # Default: return a mock connection that behaves correctly
        mock_conn.return_value = MagicMock()
        yield mock_conn


@pytest.fixture(scope="session")
def client(skip_startup_db_check):
    # Import after patching
    from main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert "application/json" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# Happy path — stocks present
# ---------------------------------------------------------------------------

def test_current_bmsb_with_results(client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("AAPL", "NASDAQ"), ("JPM", "NYSE")]
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)

    with patch("main.get_connection", return_value=mock_conn):
        r = client.get("/api/screener/bmsb/current")

    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert {"symbol": "AAPL", "exchange": "NASDAQ"} in data
    assert {"symbol": "JPM", "exchange": "NYSE"} in data
    assert "application/json" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# Happy path — empty result (latest version has zero passing stocks)
# ---------------------------------------------------------------------------

def test_current_bmsb_empty_result(client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)

    with patch("main.get_connection", return_value=mock_conn):
        r = client.get("/api/screener/bmsb/current")

    assert r.status_code == 200
    assert r.json() == []
    assert "application/json" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# DB unavailable at request time → 503
# ---------------------------------------------------------------------------

def test_current_bmsb_db_unavailable(client):
    import psycopg2

    with patch("main.get_connection", side_effect=psycopg2.OperationalError("connection refused")):
        r = client.get("/api/screener/bmsb/current")

    assert r.status_code == 503
    assert r.json() == {"detail": "Database unavailable"}
    assert "application/json" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# Health check is unaffected by screener failures
# ---------------------------------------------------------------------------

def test_health_unaffected_by_db_failure(client):
    import psycopg2

    with patch("main.get_connection", side_effect=psycopg2.OperationalError("down")):
        r = client.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Query execution failure → 500
# ---------------------------------------------------------------------------

def test_current_bmsb_query_failure(client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = Exception("unexpected query error")
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)

    with patch("main.get_connection", return_value=mock_conn):
        r = client.get("/api/screener/bmsb/current")

    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error"}
    assert "application/json" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# 404 for unknown routes
# ---------------------------------------------------------------------------

def test_unknown_route(client):
    r = client.get("/api/does/not/exist")
    assert r.status_code == 404
    assert "application/json" in r.headers["content-type"]

