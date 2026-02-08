# MyAnimeList OAuth - Kometa

A simple Flask web application for authenticating with MyAnimeList and obtaining access tokens for use with Kometa.

## Features

- Clean, modern UI with MAL branding
- Step-by-step authentication process with PKCE
- Automatic configuration generation for Kometa
- Copy-to-clipboard functionality
- Secure token exchange

## Usage

1. Visit the application
2. Enter your MyAnimeList Client ID and Client Secret
3. Click "Get Authorization URL" to generate the authentication link
4. Click "Open URL" and authorize on MyAnimeList's website
5. Copy the localhost URL (it won't load - this is expected!)
6. Paste the localhost URL and click "Submit"
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
docker build -t mal-oauth .
docker run -p 8080:8080 mal-oauth
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
mal-oauth.example.com {
    reverse_proxy http://127.0.0.1:8080
}
```

## Technical Details

This service uses PKCE (Proof Key for Code Exchange) for secure authentication with MyAnimeList's OAuth2 implementation.
