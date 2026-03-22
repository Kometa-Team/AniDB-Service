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
4. SIMKL redirects back to `{REDIRECT_URI}?code={code}`
5. App's `/callback` endpoint receives the code and POSTs to `https://api.simkl.com/oauth/token` with:
   - `code`
   - `client_id`
   - `client_secret`
   - `redirect_uri`
   - `grant_type: authorization_code`
6. SIMKL returns an `access_token` (never expires, no refresh token)
7. App displays the Kometa config snippet

No Flask session required — all credentials are server-side env vars.

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

Three routes:

- `GET /` — Renders main page. Builds SIMKL auth URL from `CLIENT_ID` and `REDIRECT_URI` env vars.
- `GET /callback` — Receives `?code=` from SIMKL redirect. Exchanges code for token using `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI` env vars. Renders `index.html` with token (success) or error message (failure).
- `GET /api/health` — Returns `{"status": "ok"}`.

### `templates/index.html`

Single template, two visual states rendered server-side:

- **Default state:** Instructions + "Connect with SIMKL" button (anchor tag linking to the SIMKL authorize URL)
- **Result state:** Kometa config snippet with copy button, and a "Connect Another Account" link back to `/`

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

| Variable       | Required | Default     | Description                                      |
|----------------|----------|-------------|--------------------------------------------------|
| `CLIENT_ID`    | Yes      | —           | SIMKL app client ID (Kometa's registered app)    |
| `CLIENT_SECRET`| Yes      | —           | SIMKL app client secret                          |
| `REDIRECT_URI` | Yes      | —           | Callback URL registered in SIMKL app settings    |
| `PORT`         | No       | `8080`      | Port to run on                                   |
| `HOST`         | No       | `127.0.0.1` | Host to bind to                                  |
| `DEBUG`        | No       | `False`     | Enable Flask debug mode                          |

No `SECRET_KEY` — Flask sessions are not used.

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
    - CLIENT_ID=${SIMKL_CLIENT_ID}
    - CLIENT_SECRET=${SIMKL_CLIENT_SECRET}
    - REDIRECT_URI=${SIMKL_REDIRECT_URI}
  deploy:
    resources:
      limits:
        memory: 128M
      reservations:
        memory: 64M
```

### `Caddyfile.example`

Add route (alongside existing oauth handlers):

```caddy
handle /simkl-oauth* {
    uri strip_prefix /simkl-oauth
    reverse_proxy simkl-oauth:5000
}
```

---

## Error Handling

- Missing env vars (`CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`): `/callback` renders an error state in `index.html`
- SIMKL token exchange failure (non-2xx response): render error state with message
- `?error=` parameter on callback (user denied): render error state with explanation

---

## Testing

- Unit test: `exchange_code_for_token()` with mocked `requests.post`
- Unit test: `/callback` route with valid code → success state
- Unit test: `/callback` route with `?error=access_denied` → error state
- Unit test: `/api/health` → `{"status": "ok"}`
- Manual: full OAuth round-trip against SIMKL sandbox/staging
