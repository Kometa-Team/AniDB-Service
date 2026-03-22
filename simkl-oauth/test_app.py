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


def test_index_page_renders(client) -> None:
    response = client.get("/")
    assert response.status_code == 200


def test_index_page_contains_auth_url(client) -> None:
    response = client.get("/")
    html = response.data.decode()
    assert "https://simkl.com/oauth/authorize" in html
    assert "test-client-id" in html
    assert "http://localhost:8080/callback" in html
