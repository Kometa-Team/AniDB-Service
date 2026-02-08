# Trakt OAuth - Kometa

A simple Flask web application for authenticating with Trakt and obtaining access tokens for use with Kometa.

## Features

- Clean, modern UI with Trakt branding
- Step-by-step authentication process
- Automatic configuration generation for Kometa
- Copy-to-clipboard functionality
- Secure token exchange

## Usage

1. Visit the application
2. Enter your Trakt Client ID and Client Secret
3. Click "Get Authorization URL" to generate the authentication link
4. Click "Open URL" and authorize on Trakt's website
5. Copy the PIN code provided by Trakt
6. Paste the PIN and click "Submit"
7. Copy the generated configuration into your Kometa config.yml

## Running Locally

### Python
```bash
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:8080`

### Docker
```bash
docker build -t trakt-oauth .
docker run -p 8080:8080 trakt-oauth
```

## Environment Variables

- `PORT` - Port to run on (default: 8080)
- `HOST` - Host to bind to (default: 127.0.0.1)
- `DEBUG` - Enable debug mode (default: False)
- `SECRET_KEY` - Flask secret key (default: dev-key-change-in-production)

## Deployment

This service is designed to be deployed behind a reverse proxy like Caddy.

### With Caddy
```caddy
trakt-oauth.example.com {
    reverse_proxy http://127.0.0.1:8080
}
```
