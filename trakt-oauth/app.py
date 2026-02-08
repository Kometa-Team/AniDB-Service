"""
Trakt OAuth Flask Application.

A minimal Flask web application for authenticating with Trakt and obtaining access tokens.
"""

import os

import requests  # type: ignore[import-untyped]
from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev-key-change-in-production")

# Trakt API Configuration
TRAKT_API_URL = "https://api.trakt.tv"
TRAKT_AUTH_URL = "https://trakt.tv/oauth"


def exchange_code_for_token(client_id, client_secret, code, redirect_uri):
    """Exchange authorization code for access token."""
    try:
        response = requests.post(
            f"{TRAKT_AUTH_URL}/token",
            json={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error exchanging code: {e}")
        return None


@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")


@app.route("/api/exchange-code", methods=["POST"])
def exchange_code():
    """Exchange Trakt PIN/code for access token."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        client_id = data.get("client_id", "").strip()
        client_secret = data.get("client_secret", "").strip()
        code = data.get("code", "").strip()
        redirect_uri = data.get("redirect_uri", "urn:ietf:wg:oauth:2.0:oob")

        if not all([client_id, client_secret, code]):
            return (
                jsonify({"error": "Missing required parameters (client_id, client_secret, code)"}),
                400,
            )

        token_data = exchange_code_for_token(client_id, client_secret, code, redirect_uri)
        if not token_data:
            return (
                jsonify({"error": "Failed to exchange code for token. Check your credentials."}),
                500,
            )

        if "error" in token_data:
            error_msg = token_data.get(
                "error_description", token_data.get("error", "Unknown error")
            )
            return jsonify({"error": f"Trakt error: {error_msg}"}), 400

        return jsonify(
            {
                "success": True,
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "token_type": token_data.get("token_type", "Bearer"),
                "created_at": token_data.get("created_at"),
            }
        )
    except Exception as e:
        print(f"Error in exchange_code: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=debug)
