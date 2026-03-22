# SIMKL OAuth Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Flask service at `simkl-oauth/` that guides Kometa users through SIMKL OAuth 2.0 and displays their `user_token` for use in `config.yml`.

**Architecture:** Standard OAuth 2.0 redirect/callback flow — user clicks "Connect with SIMKL", authorizes on SIMKL's site, SIMKL redirects back to `/callback?code=...`, the backend exchanges the code for an access token using fixed env var credentials, and the result page shows the Kometa config snippet. Stateless — no Flask session.

**Tech Stack:** Python 3.12, Flask ≥3.0, gunicorn, requests, pytest

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `simkl-oauth/requirements.txt` | Create | Python dependencies |
| `simkl-oauth/Dockerfile` | Create | Container definition (mirrors trakt-oauth) |
| `simkl-oauth/app.py` | Create | Flask app — routes and token exchange logic |
| `simkl-oauth/templates/index.html` | Create | Single template with three Jinja2 states |
| `simkl-oauth/conftest.py` | Create | Pytest env var setup (required before app import) |
| `simkl-oauth/test_app.py` | Create | Unit tests |
| `simkl-oauth/README.md` | Create | Usage documentation |
| `docker-compose.yml` | Modify | Add `simkl-oauth` service |
| `docker-compose.override.yml` | Modify | Add local build entry |
| `Caddyfile.example` | Modify | Add `/simkl-oauth*` reverse proxy route |

---

## Task 1: Scaffold — requirements, Dockerfile, README

**Files:**
- Create: `simkl-oauth/requirements.txt`
- Create: `simkl-oauth/Dockerfile`
- Create: `simkl-oauth/README.md`

- [ ] **Step 1: Create `simkl-oauth/requirements.txt`**

```
flask>=3.0.0
gunicorn>=21.2.0
requests>=2.31.0
```

- [ ] **Step 2: Create `simkl-oauth/Dockerfile`**

```dockerfile
FROM python:3.12-slim

EXPOSE 5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
```

- [ ] **Step 3: Create `simkl-oauth/README.md`**

```markdown
# SIMKL OAuth - Kometa

A simple Flask web application for authenticating with SIMKL and obtaining access tokens for use with Kometa.

## Features

- Clean, modern UI with SIMKL branding
- One-click OAuth 2.0 authorization flow
- Automatic configuration generation for Kometa
- Copy-to-clipboard functionality

## Usage

1. Visit the application
2. Click "Connect with SIMKL"
3. Authorize the Kometa app on SIMKL's website
4. Copy the generated configuration into your Kometa config.yml

## Running Locally

### Python
```bash
export CLIENT_ID=your_simkl_client_id
export CLIENT_SECRET=your_simkl_client_secret
export REDIRECT_URI=http://localhost:8080/callback
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:8080`

### Docker
```bash
docker build -t simkl-oauth .
docker run -p 8080:5000 \
  -e CLIENT_ID=your_client_id \
  -e CLIENT_SECRET=your_client_secret \
  -e REDIRECT_URI=http://localhost:8080/callback \
  simkl-oauth
```

## Environment Variables

- `CLIENT_ID` - SIMKL app client ID (required)
- `CLIENT_SECRET` - SIMKL app client secret (required)
- `REDIRECT_URI` - Callback URL registered in SIMKL app settings (required)
- `ROOT_PATH` - Set to `/simkl-oauth` for path-based routing behind a reverse proxy
- `PORT` - Port to run on (default: 8080)
- `HOST` - Host to bind to (default: 127.0.0.1)
- `DEBUG` - Enable debug mode (default: False)

## Deployment

This service is designed to be deployed behind a reverse proxy like Caddy.

### With Caddy
```caddy
handle /simkl-oauth* {
    uri strip_prefix /simkl-oauth
    reverse_proxy simkl-oauth:5000
}
```
```

- [ ] **Step 4: Commit scaffold**

```bash
git add simkl-oauth/requirements.txt simkl-oauth/Dockerfile simkl-oauth/README.md
git commit -m "feat(simkl-oauth): add project scaffold"
```

---

## Task 2: Health endpoint (TDD)

**Files:**
- Create: `simkl-oauth/conftest.py`
- Create: `simkl-oauth/test_app.py`
- Create: `simkl-oauth/app.py`

The module-level env var validation in `app.py` runs at import time, so `conftest.py` must set env vars **before** `app.py` is imported. pytest loads `conftest.py` before test modules, so setting env vars there is safe.

- [ ] **Step 1: Create `simkl-oauth/conftest.py`**

```python
"""Configure test environment before app module is imported."""

import os

os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("REDIRECT_URI", "http://localhost:8080/callback")
```

- [ ] **Step 2: Write the failing health test in `simkl-oauth/test_app.py`**

```python
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
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
cd simkl-oauth
pip install -r requirements.txt pytest
pytest test_app.py::test_health_endpoint -v
```

Expected: `ModuleNotFoundError: No module named 'app'` or similar import failure.

- [ ] **Step 4: Create minimal `simkl-oauth/app.py`**

```python
"""SIMKL OAuth Flask Application.

A minimal Flask web application for authenticating with SIMKL and obtaining
access tokens for use with Kometa.
"""

import os

import requests  # type: ignore[import-untyped]
from flask import Flask, render_template, request

# Validate required env vars at startup
_CLIENT_ID = os.getenv("CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
_REDIRECT_URI = os.getenv("REDIRECT_URI", "")

_missing = [name for name, val in [
    ("CLIENT_ID", _CLIENT_ID),
    ("CLIENT_SECRET", _CLIENT_SECRET),
    ("REDIRECT_URI", _REDIRECT_URI),
] if not val]
if _missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(_missing)}")

CLIENT_ID: str = _CLIENT_ID
CLIENT_SECRET: str = _CLIENT_SECRET
REDIRECT_URI: str = _REDIRECT_URI

SIMKL_AUTH_URL = "https://simkl.com/oauth/authorize"
SIMKL_TOKEN_URL = "https://api.simkl.com/oauth/token"

app = Flask(__name__, template_folder="templates")


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=debug)
```

- [ ] **Step 5: Run test to confirm it passes**

```bash
pytest test_app.py::test_health_endpoint -v
```

Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add simkl-oauth/conftest.py simkl-oauth/test_app.py simkl-oauth/app.py
git commit -m "feat(simkl-oauth): add Flask app with health endpoint"
```

---

## Task 3: Index route (TDD)

**Files:**
- Modify: `simkl-oauth/test_app.py`
- Modify: `simkl-oauth/app.py`

- [ ] **Step 1: Add the failing index test**

Append to `simkl-oauth/test_app.py`:

```python
def test_index_page_renders(client) -> None:
    response = client.get("/")
    assert response.status_code == 200


def test_index_page_contains_auth_url(client) -> None:
    response = client.get("/")
    html = response.data.decode()
    assert "https://simkl.com/oauth/authorize" in html
    assert "test-client-id" in html
    assert "http://localhost:8080/callback" in html
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest test_app.py::test_index_page_renders test_app.py::test_index_page_contains_auth_url -v
```

Expected: both `FAILED` (template not found / route not defined).

- [ ] **Step 3: Add `GET /` route to `simkl-oauth/app.py`**

Add after the startup validation block, before the `health` route:

```python
@app.route("/")
def index():
    """Render the main page."""
    auth_url = (
        f"{SIMKL_AUTH_URL}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return render_template("index.html", state="default", auth_url=auth_url)
```

- [ ] **Step 4: Create a minimal stub template `simkl-oauth/templates/index.html`**

This stub is just enough for the route test to pass. It will be replaced in Task 6.

```html
<!DOCTYPE html>
<html lang="en">
<head><title>SIMKL OAuth</title></head>
<body>
{% if state == "default" %}
  <a href="{{ auth_url }}">Connect with SIMKL</a>
{% elif state == "success" %}
  <p>user_token: {{ user_token }}</p>
{% elif state == "error" %}
  <p>Error: {{ error_message }}</p>
{% endif %}
</body>
</html>
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest test_app.py::test_index_page_renders test_app.py::test_index_page_contains_auth_url -v
```

Expected: both `PASSED`

- [ ] **Step 6: Commit**

```bash
git add simkl-oauth/app.py simkl-oauth/templates/index.html
git commit -m "feat(simkl-oauth): add index route and stub template"
```

---

## Task 4: Token exchange function (TDD)

**Files:**
- Modify: `simkl-oauth/test_app.py`
- Modify: `simkl-oauth/app.py`

- [ ] **Step 1: Add the failing token exchange tests**

These tests use `unittest.mock.patch` to avoid real HTTP calls.

Append to `simkl-oauth/test_app.py`:

```python
from unittest.mock import MagicMock, patch


def test_exchange_code_for_token_success() -> None:
    from app import exchange_code_for_token

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "tok_abc123"}
    mock_response.raise_for_status.return_value = None

    with patch("app.requests.post", return_value=mock_response):
        result = exchange_code_for_token("auth-code-xyz")

    assert result == {"access_token": "tok_abc123"}


def test_exchange_code_for_token_http_error() -> None:
    import requests as req

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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest test_app.py::test_exchange_code_for_token_success \
       test_app.py::test_exchange_code_for_token_http_error \
       test_app.py::test_exchange_code_for_token_network_error -v
```

Expected: all `FAILED` (`ImportError: cannot import name 'exchange_code_for_token'`).

- [ ] **Step 3: Add `exchange_code_for_token` to `simkl-oauth/app.py`**

Add after the constants, before the routes:

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest test_app.py::test_exchange_code_for_token_success \
       test_app.py::test_exchange_code_for_token_http_error \
       test_app.py::test_exchange_code_for_token_network_error -v
```

Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add simkl-oauth/app.py simkl-oauth/test_app.py
git commit -m "feat(simkl-oauth): add token exchange function"
```

---

## Task 5: Callback route (TDD)

**Files:**
- Modify: `simkl-oauth/test_app.py`
- Modify: `simkl-oauth/app.py`

- [ ] **Step 1: Add the failing callback tests**

Append to `simkl-oauth/test_app.py`:

```python
def test_callback_success(client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "tok_abc123"}
    mock_response.raise_for_status.return_value = None

    with patch("app.requests.post", return_value=mock_response):
        response = client.get("/callback?code=auth-code-xyz")

    assert response.status_code == 200
    html = response.data.decode()
    assert "tok_abc123" in html


def test_callback_error_param(client) -> None:
    response = client.get("/callback?error=access_denied&error_description=User+denied+access")
    assert response.status_code == 200
    html = response.data.decode()
    assert "User denied access" in html


def test_callback_error_param_no_description(client) -> None:
    response = client.get("/callback?error=access_denied")
    assert response.status_code == 200
    html = response.data.decode()
    assert "access_denied" in html


def test_callback_no_code(client) -> None:
    response = client.get("/callback")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Error" in html or "error" in html


def test_callback_exchange_fails(client) -> None:
    with patch("app.requests.post", side_effect=ConnectionError("timeout")):
        response = client.get("/callback?code=any-code")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Error" in html or "error" in html


def test_callback_exchange_http_error(client) -> None:
    import requests as req

    mock_response = MagicMock()
    mock_response.text = '{"error":"invalid_grant"}'
    http_error = req.exceptions.HTTPError(response=mock_response)

    with patch("app.requests.post", side_effect=http_error):
        response = client.get("/callback?code=bad-code")

    assert response.status_code == 200
    html = response.data.decode()
    assert "Error" in html or "error" in html


def test_callback_missing_access_token(client) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"token_type": "Bearer"}  # no access_token
    mock_response.raise_for_status.return_value = None

    with patch("app.requests.post", return_value=mock_response):
        response = client.get("/callback?code=any-code")

    assert response.status_code == 200
    html = response.data.decode()
    assert "Error" in html or "error" in html
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest test_app.py -k "callback" -v
```

Expected: all `FAILED` (route not defined).

- [ ] **Step 3: Add `GET /callback` route to `simkl-oauth/app.py`**

Add after the `index` route, before `health`:

```python
@app.route("/callback")
def callback():
    """Handle SIMKL OAuth callback."""
    error = request.args.get("error")
    if error:
        error_description = request.args.get("error_description", error)
        return render_template("index.html", state="error", error_message=error_description)

    code = request.args.get("code")
    if not code:
        return render_template(
            "index.html", state="error", error_message="No authorization code received."
        )

    token_data = exchange_code_for_token(code)
    if token_data is None:
        return render_template(
            "index.html",
            state="error",
            error_message="Failed to connect to SIMKL. Please try again.",
        )

    if "error" in token_data:
        return render_template("index.html", state="error", error_message=token_data["error"])

    access_token = token_data.get("access_token")
    if not access_token:
        return render_template(
            "index.html", state="error", error_message="Unexpected response from SIMKL."
        )

    return render_template("index.html", state="success", user_token=access_token)
```

- [ ] **Step 4: Run all tests to confirm they pass**

```bash
pytest test_app.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add simkl-oauth/app.py simkl-oauth/test_app.py
git commit -m "feat(simkl-oauth): add callback route with full error handling"
```

---

## Task 6: Full HTML template

Replace the stub template with the production UI. SIMKL brand colors: teal `#1CE8B5`, dark background `#1a1a2e`.

**Files:**
- Modify: `simkl-oauth/templates/index.html`

- [ ] **Step 1: Replace `simkl-oauth/templates/index.html` with the full template**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SIMKL OAuth - Kometa</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 10px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            padding: 40px;
            max-width: 560px;
            width: 100%;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2rem;
            color: #333;
            margin-bottom: 10px;
        }

        .header p {
            color: #666;
            font-size: 1rem;
        }

        .instructions {
            background: #f0fdf9;
            border-left: 4px solid #1CE8B5;
            padding: 15px;
            margin: 20px 0;
            border-radius: 3px;
            font-size: 0.9rem;
            color: #333;
        }

        .instructions ol {
            margin-left: 20px;
        }

        .instructions li {
            margin: 8px 0;
        }

        .button {
            display: block;
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 5px;
            font-size: 1rem;
            cursor: pointer;
            text-align: center;
            text-decoration: none;
            transition: all 0.3s ease;
            margin: 10px 0;
        }

        .button.primary {
            background: #1CE8B5;
            color: #1a1a2e;
            font-weight: 600;
        }

        .button.primary:hover {
            background: #17c99c;
        }

        .button.secondary {
            background: #f0f0f0;
            color: #333;
            border: 1px solid #ddd;
        }

        .button.secondary:hover {
            background: #e0e0e0;
        }

        .status {
            margin: 20px 0;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }

        .status.success {
            background: #e8f5e9;
            color: #2e7d32;
            border: 1px solid #81c784;
        }

        .status.error {
            background: #ffebee;
            color: #c62828;
            border: 1px solid #ef5350;
        }

        .result-section {
            margin-top: 20px;
        }

        .config-output {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
            font-family: monospace;
            font-size: 0.85rem;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .copy-btn {
            background: #4caf50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.3s ease;
            width: 100%;
            margin-top: 10px;
        }

        .copy-btn:hover {
            background: #45a049;
        }

        .footer {
            text-align: center;
            margin-top: 30px;
            font-size: 0.85rem;
            color: #999;
        }

        .footer a {
            color: #1CE8B5;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>&#127909; SIMKL OAuth</h1>
            <p>Get your SIMKL access token for Kometa</p>
        </div>

        {% if state == "default" %}
        <div class="instructions">
            <strong>How it works:</strong>
            <ol>
                <li>Click "Connect with SIMKL" below</li>
                <li>Log in and authorize the Kometa app on SIMKL's website</li>
                <li>You'll be redirected back here with your token</li>
                <li>Copy the configuration into your Kometa config.yml</li>
            </ol>
        </div>

        <a href="{{ auth_url }}" class="button primary">Connect with SIMKL</a>

        {% elif state == "success" %}
        <div class="status success">
            &#10003; Authorization successful!
        </div>

        <div class="result-section">
            <h3 style="color: #333; margin-bottom: 15px;">&#10003; Configuration Ready</h3>
            <p style="color: #666; margin-bottom: 10px;">Copy and paste this into your Kometa config.yml:</p>
            <div class="config-output" id="configOutput">simkl:
  user_token: {{ user_token }}</div>
            <button class="copy-btn" onclick="copyConfig()">&#128203; Copy Configuration</button>
            <a href="/" class="button secondary" style="margin-top: 15px;">Connect Another Account</a>
        </div>

        {% elif state == "error" %}
        <div class="status error">
            <strong>Error:</strong> {{ error_message }}
        </div>

        <a href="/" class="button secondary">Try Again</a>
        {% endif %}

        <div class="footer">
            <p>For use with Kometa</p>
            <p><a href="/">&#8592; Back to Home</a></p>
        </div>
    </div>

    <script>
        function copyConfig() {
            const configText = document.getElementById('configOutput').textContent;
            navigator.clipboard.writeText(configText).then(() => {
                const btn = document.querySelector('.copy-btn');
                btn.textContent = '&#10003; Copied!';
                setTimeout(() => { btn.textContent = '&#128203; Copy Configuration'; }, 3000);
            }).catch(() => {
                alert('Could not copy to clipboard. Please copy manually.');
            });
        }
    </script>
</body>
</html>
```

- [ ] **Step 2: Run all tests to confirm the full template still passes**

```bash
pytest test_app.py -v
```

Expected: all `PASSED`

- [ ] **Step 3: Commit**

```bash
git add simkl-oauth/templates/index.html
git commit -m "feat(simkl-oauth): add production HTML template with SIMKL branding"
```

---

## Task 7: Integration — docker-compose, override, Caddyfile

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.override.yml`
- Modify: `Caddyfile.example`

- [ ] **Step 1: Add `simkl-oauth` service to `docker-compose.yml`**

In `docker-compose.yml`, add the following service alongside the existing `trakt-oauth` and `mal-oauth` entries (before the `fider-db` service):

```yaml
  simkl-oauth:
    image: ghcr.io/kometa-team/simkl-oauth:latest
    container_name: simkl-oauth
    restart: unless-stopped
    environment:
      - ROOT_PATH=/simkl-oauth
      - CLIENT_ID=${SIMKL_CLIENT_ID:?SIMKL_CLIENT_ID must be set in .env}
      - CLIENT_SECRET=${SIMKL_CLIENT_SECRET:?SIMKL_CLIENT_SECRET must be set in .env}
      - REDIRECT_URI=${SIMKL_REDIRECT_URI:?SIMKL_REDIRECT_URI must be set in .env}
    deploy:
      resources:
        limits:
          memory: 128M
        reservations:
          memory: 64M
```

- [ ] **Step 2: Add build entry to `docker-compose.override.yml`**

Append to the `services:` block in `docker-compose.override.yml`:

```yaml
  simkl-oauth:
    pull_policy: build
    build:
      context: ./simkl-oauth
      dockerfile: Dockerfile
```

- [ ] **Step 3: Add route to `Caddyfile.example`**

In `Caddyfile.example`, add the following block after the `handle /mal-oauth*` block:

```caddy
    # Handle /simkl-oauth path
    # Flask app for SIMKL OAuth authentication
    # Note: /callback is browser-driven (not called by external servers),
    # so no special basicauth bypass is needed — the user's browser session
    # handles auth transparently.
    handle /simkl-oauth* {
        uri strip_prefix /simkl-oauth
        reverse_proxy simkl-oauth:5000
    }
```

- [ ] **Step 4: Commit integration changes**

```bash
git add docker-compose.yml docker-compose.override.yml Caddyfile.example
git commit -m "feat(simkl-oauth): wire up docker-compose and Caddyfile routing"
```

---

## Verification

After all tasks are complete, run the full test suite from the `simkl-oauth/` directory:

```bash
cd simkl-oauth
pytest test_app.py -v
```

Expected output — all 13 tests pass:
```
test_app.py::test_health_endpoint PASSED
test_app.py::test_index_page_renders PASSED
test_app.py::test_index_page_contains_auth_url PASSED
test_app.py::test_exchange_code_for_token_success PASSED
test_app.py::test_exchange_code_for_token_http_error PASSED
test_app.py::test_exchange_code_for_token_network_error PASSED
test_app.py::test_callback_success PASSED
test_app.py::test_callback_error_param PASSED
test_app.py::test_callback_error_param_no_description PASSED
test_app.py::test_callback_no_code PASSED
test_app.py::test_callback_exchange_fails PASSED
test_app.py::test_callback_exchange_http_error PASSED
test_app.py::test_callback_missing_access_token PASSED
```
