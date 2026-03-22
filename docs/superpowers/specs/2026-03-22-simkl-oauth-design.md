# SIMKL OAuth Service — Design Spec

**Date:** 2026-03-22
**Status:** Approved

---

## Overview

A new standalone Flask service (`simkl-oauth/`) that guides Kometa users through SIMKL OAuth 2.0 authorization and displays their `user_token` for use in `config.yml`. Modeled after the existing `trakt-oauth/` service.

---

## OAuth Flow

SIMKL uses a standard OAuth 2.0 authorization code redirect flow:

1. User visits the app's main page and clicks "Connect with SIMKL"
2. Browser redirects to `https://simkl.com/oauth/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}`
3. User authorizes the Kometa app on SIMKL
4. SIMKL redirects back to `{REDIRECT_URI}?code={code}` (or `?error=access_denied&error_description=...` if denied)
5. App's `/callback` endpoint receives the code and POSTs to `https://api.simkl.com/oauth/token` with:
   - `code`
   - `client_id`
   - `client_secret`
   - `redirect_uri`
   - `grant_type: authorization_code`
6. SIMKL returns an `access_token` (never expires, no refresh token)
7. App displays the Kometa config snippet

No Flask session required — all credentials are server-side env vars. The service is stateless by design; any gunicorn worker count is safe and no `SECRET_KEY` is needed.

**Note on CSRF:** The spec omits a `state` parameter. Since `client_id` and `client_secret` are fixed server-side and the resulting token belongs to whoever performs the browser authorization, the practical risk of login CSRF is low. This is a conscious tradeoff.

---

## Directory Structure

```
simkl-oauth/
  app.py
  Dockerfile
  requirements.txt
  templates/
    index.html
```

---

## Components

### `app.py`

**Startup validation:** At module load, validate that `CLIENT_ID`, `CLIENT_SECRET`, and `REDIRECT_URI` are all set. If any are missing, raise `RuntimeError` with a clear message. Gunicorn will surface this cleanly and prevent the service from starting silently misconfigured.

Three routes:

- `GET /` — Renders main page. Builds SIMKL auth URL from `CLIENT_ID` and `REDIRECT_URI` env vars and passes it to the template.
- `GET /callback` — Receives `?code=` (or `?error=`) from SIMKL redirect. On `?error=`, renders error state using the `error_description` query parameter if present, falling back to `error` value. On `?code=`, calls `exchange_code_for_token(code)` and renders success or error state accordingly.
- `GET /api/health` — Returns `{"status": "ok"}`.

**`exchange_code_for_token(code: str) -> dict | None`**

Reads `CLIENT_ID`, `CLIENT_SECRET`, and `REDIRECT_URI` from env vars. POSTs to `https://api.simkl.com/oauth/token`. Returns parsed JSON on success. On `requests.exceptions.HTTPError`, returns a dict `{"error": "<status_code>: <response_body>"}` so the caller can surface detail to the user (matching the MAL pattern). On any other exception, returns `None`. Errors are printed to stdout.

### `templates/index.html`

Single template, three server-rendered states passed via template variables:

- **Default state** (`state="default"`): Instructions + "Connect with SIMKL" button (anchor tag linking to the SIMKL authorize URL)
- **Success state** (`state="success"`, `user_token=...`): Kometa config snippet with copy button, and a "Connect Another Account" link back to `/`
- **Error state** (`state="error"`, `error_message=...`): Error message with a "Try Again" link back to `/`

SIMKL branding colors (teal: `#1CE8B5`, dark background).

### `Dockerfile`

Identical to `trakt-oauth/Dockerfile`: Python 3.12-slim, gunicorn on port 5000.

```dockerfile
FROM python:3.12-slim
EXPOSE 5000
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
```

### `requirements.txt`

```
flask>=3.0.0
gunicorn>=21.2.0
requests>=2.31.0
```

---

## Environment Variables

| Variable         | Required | Default     | Description                                                   |
|------------------|----------|-------------|---------------------------------------------------------------|
| `CLIENT_ID`      | Yes      | —           | SIMKL app client ID (Kometa's registered app)                 |
| `CLIENT_SECRET`  | Yes      | —           | SIMKL app client secret                                       |
| `REDIRECT_URI`   | Yes      | —           | Callback URL registered in SIMKL app settings (e.g. `https://yourdomain.com/simkl-oauth/callback`) |
| `ROOT_PATH`      | No       | `""`        | Set to `/simkl-oauth` for path-based routing behind a reverse proxy. Read by `app.py` and used in the JS `basePath` detection in the template (matching the `trakt-oauth` pattern: `window.location.pathname.startsWith('/simkl-oauth')`). |
| `PORT`           | No       | `8080`      | Port to run on (local dev only; gunicorn uses 5000)           |
| `HOST`           | No       | `127.0.0.1` | Host to bind to (local dev only)                              |
| `DEBUG`          | No       | `False`     | Enable Flask debug mode (local dev only)                      |

No `SECRET_KEY` — Flask sessions are not used.

Sensitive vars (`CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`) are supplied via the project-root `.env` file as `SIMKL_CLIENT_ID`, `SIMKL_CLIENT_SECRET`, `SIMKL_REDIRECT_URI` and referenced in `docker-compose.yml` via variable substitution (matching the pattern used by `TRAKT_SECRET_KEY`).

---

## Kometa Config Output

```yaml
simkl:
  user_token: <access_token>
```

---

## Integration

### `docker-compose.yml`

Add service:

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

### `docker-compose.override.yml`

Add local build entry:

```yaml
simkl-oauth:
  pull_policy: build
  build:
    context: ./simkl-oauth
    dockerfile: Dockerfile
```

### `Caddyfile.example`

Add route alongside existing oauth handlers:

```caddy
handle /simkl-oauth* {
    uri strip_prefix /simkl-oauth
    reverse_proxy simkl-oauth:5000
}
```

**Note:** The `/callback` route is hit directly by the user's browser after SIMKL redirects — it is not called by an external server. If basic auth is enabled on the domain, the user will already be authenticated in their browser session, so no special bypass rule is required (unlike `plex-oauth/auth/callback` which is called by Plex's servers). However, if cookie/session-based auth is used, implementers should verify the callback URL remains accessible in their specific setup.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing required env vars at startup | `RuntimeError` raised at module load; service fails to start |
| `?error=` on callback (e.g. user denied) | Render error state; show `error_description` query param if present, else `error` value |
| SIMKL token exchange returns non-2xx | Render error state with response status and body |
| `exchange_code_for_token` raises exception | Returns `None`; render generic error state |
| `access_token` absent from successful response | Render error state: "Unexpected response from SIMKL" |

---

## Testing

- Unit test: `exchange_code_for_token(code)` with mocked `requests.post` — success case returns token dict, failure returns `None`
- Unit test: `GET /` renders authorize URL containing `CLIENT_ID` and `REDIRECT_URI`
- Unit test: `GET /callback?code=...` → success state with correct `user_token`
- Unit test: `GET /callback?error=access_denied&error_description=User+denied` → error state with message
- Unit test: `GET /callback?code=...` when token exchange fails → error state
- Unit test: `GET /api/health` → `{"status": "ok"}`
- Manual: full OAuth round-trip against SIMKL
