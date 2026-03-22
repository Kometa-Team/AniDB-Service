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
