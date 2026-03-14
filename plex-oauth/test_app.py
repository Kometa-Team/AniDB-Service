import pytest
from plex_oauth.app import app


@pytest.fixture()
def client():
    """Flask test client for the Plex OAuth app."""
    with app.test_client() as client:
        yield client


def test_health_endpoint(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_index_page(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
