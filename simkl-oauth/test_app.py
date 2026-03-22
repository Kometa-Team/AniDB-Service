"""Tests for the SIMKL OAuth Flask application."""

from unittest.mock import MagicMock, patch

import pytest
import requests as req  # type: ignore[import-untyped]


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


def test_exchange_code_for_token_success() -> None:
    from app import exchange_code_for_token

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "tok_abc123"}
    mock_response.raise_for_status.return_value = None

    with patch("app.requests.post", return_value=mock_response):
        result = exchange_code_for_token("auth-code-xyz")

    assert result == {"access_token": "tok_abc123"}


def test_exchange_code_for_token_http_error() -> None:
    from app import exchange_code_for_token

    mock_response = MagicMock()
    mock_response.text = '{"error":"invalid_grant"}'
    http_error = req.exceptions.HTTPError(response=mock_response)

    with patch("app.requests.post", side_effect=http_error):
        result = exchange_code_for_token("bad-code")

    assert result is not None
    assert "error" in result
    assert "invalid_grant" in result["error"]


def test_exchange_code_for_token_network_error() -> None:
    from app import exchange_code_for_token

    with patch("app.requests.post", side_effect=ConnectionError("timeout")):
        result = exchange_code_for_token("any-code")

    assert result is None
