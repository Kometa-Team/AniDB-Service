"""Tests for the SIMKL OAuth Flask application."""

import pytest


@pytest.fixture()
def client():
    """Flask test client."""
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_endpoint(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
