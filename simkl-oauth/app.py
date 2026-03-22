"""SIMKL OAuth Flask Application.

A minimal Flask web application for authenticating with SIMKL and obtaining
access tokens for use with Kometa.
"""

import os

import requests  # type: ignore[import-untyped]  # noqa: F401
from flask import Flask, render_template, request  # noqa: F401

# Validate required env vars at startup
_CLIENT_ID = os.getenv("CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
_REDIRECT_URI = os.getenv("REDIRECT_URI", "")

_missing = [
    name
    for name, val in [
        ("CLIENT_ID", _CLIENT_ID),
        ("CLIENT_SECRET", _CLIENT_SECRET),
        ("REDIRECT_URI", _REDIRECT_URI),
    ]
    if not val
]
if _missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(_missing)}")

CLIENT_ID: str = _CLIENT_ID
CLIENT_SECRET: str = _CLIENT_SECRET
REDIRECT_URI: str = _REDIRECT_URI

SIMKL_AUTH_URL = "https://simkl.com/oauth/authorize"
SIMKL_TOKEN_URL = "https://api.simkl.com/oauth/token"  # nosec: B105


def exchange_code_for_token(code: str):
    """Exchange authorization code for SIMKL access token.

    Returns parsed JSON dict on success.
    Returns dict with 'error' key on HTTP error (non-2xx response).
    Returns None on connection/unexpected errors.
    """
    try:
        response = requests.post(
            SIMKL_TOKEN_URL,
            json={
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        resp = e.response if hasattr(e, "response") and e.response is not None else None
        status = resp.status_code if resp is not None else "?"
        body = resp.text if resp is not None else str(e)
        print(f"SIMKL API HTTP Error: {e}")
        return {"error": f"{status}: {body}"}
    except Exception as e:
        print(f"Error exchanging code: {e}")
        return None


app = Flask(__name__, template_folder="templates")


@app.route("/")
def index():
    """Render the main page."""
    auth_url = (
        f"{SIMKL_AUTH_URL}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return render_template("index.html", state="default", auth_url=auth_url)


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=debug)
