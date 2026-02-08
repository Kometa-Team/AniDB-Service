"""
Plex OAuth Flask Application.

A minimal Flask web application for authenticating with Plex and obtaining access tokens.
"""

import os

import requests  # type: ignore[import-untyped]
from flask import Flask, jsonify, render_template

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev-key-change-in-production")

# Plex API Configuration
PLEX_IDENTIFIER = "com.kometa.plex-oauth"
PLEX_VERSION = "1.0.0"
PLEX_API_URL = "https://plex.tv/api/v2"


def get_plex_pin():
    """Get a PIN from Plex for OAuth flow."""
    try:
        response = requests.post(
            f"{PLEX_API_URL}/pins",
            json={
                "strong": True,
                "label": "Kometa Utilities",
            },
            headers={
                "Accept": "application/json",
                "X-Plex-Client-Identifier": PLEX_IDENTIFIER,
                "X-Plex-Product": "Kometa",
                "X-Plex-Version": PLEX_VERSION,
                "X-Plex-Device": "Kometa-Utilities",
                "X-Plex-Platform": "Web",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting PIN: {e}")
        return None


def check_pin_auth(pin_id):
    """Check if a PIN has been authorized by the user."""
    try:
        response = requests.get(
            f"{PLEX_API_URL}/pins/{pin_id}",
            headers={
                "Accept": "application/json",
                "X-Plex-Client-Identifier": PLEX_IDENTIFIER,
                "X-Plex-Product": "Kometa",
                "X-Plex-Version": PLEX_VERSION,
                "X-Plex-Device": "Kometa-Utilities",
                "X-Plex-Platform": "Web",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error checking PIN: {e}")
        return None


def get_user_info(auth_token):
    """Get user information using an auth token."""
    try:
        response = requests.get(
            f"{PLEX_API_URL}/user",
            headers={
                "Accept": "application/json",
                "X-Plex-Client-Identifier": PLEX_IDENTIFIER,
                "X-Plex-Product": "Kometa",
                "X-Plex-Version": PLEX_VERSION,
                "X-Plex-Device": "Kometa-Utilities",
                "X-Plex-Platform": "Web",
                "X-Plex-Token": auth_token,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting user info: {e}")
        return None


@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")


@app.route("/api/start-auth", methods=["POST"])
def start_auth():
    """Start the Plex authentication flow by getting a PIN."""
    pin_data = get_plex_pin()
    if not pin_data:
        return jsonify({"error": "Failed to get PIN from Plex"}), 500

    return jsonify(
        {
            "pin_id": pin_data["id"],
            "code": pin_data["code"],
            "auth_url": f"https://app.plex.tv/auth#?clientID={PLEX_IDENTIFIER}&code={pin_data['code']}",
        }
    )


@app.route("/api/check-auth/<int:pin_id>", methods=["GET"])
def check_auth(pin_id):
    """Check if the user has authenticated."""
    pin_data = check_pin_auth(pin_id)
    if not pin_data:
        return jsonify({"error": "Failed to check PIN status"}), 500

    if pin_data.get("authToken"):
        auth_token = pin_data["authToken"]

        # Fetch user information using the auth token
        user_data = get_user_info(auth_token)

        if not user_data:
            return jsonify({"error": "Failed to fetch user information"}), 500

        # Extract user information
        username = user_data.get("username", "Unknown")
        user_id = user_data.get("id", "Unknown")
        email = user_data.get("email", "Unknown")
        avatar = user_data.get("thumb", None)
        admin = user_data.get("admin", False)
        title = user_data.get("title", username)

        return jsonify(
            {
                "authenticated": True,
                "token": auth_token,
                "username": username,
                "user_id": user_id,
                "email": email,
                "avatar": avatar,
                "admin": admin,
                "title": title,
            }
        )
    else:
        return jsonify({"authenticated": False})


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=debug)
