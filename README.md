# Kometa Utilities

A single repo for Kometa support utilities.

One repo, one deployment.

## Docker Workflow

This repository publishes Docker images for its locally maintained utility services:

- `ghcr.io/kometa-team/anidb-mirror`
- `ghcr.io/kometa-team/plex-oauth`
- `ghcr.io/kometa-team/trakt-oauth`
- `ghcr.io/kometa-team/mal-oauth`

The base `docker-compose.yml` uses those published GHCR images.

For local development, `docker-compose.override.yml` is automatically picked up by Docker Compose and switches those same services back to local `build:` contexts. In practice that means:

- server/production usage pulls published images by default
- local development builds from source by default

If you want to force a local rebuild, use:

```bash
docker compose up -d --build
```

## GitHub Actions

The repository includes two Docker-related GitHub Actions workflows:

- **Pull requests to `main`**: build the utility images for validation only
- **Pushes to `main`**: build and publish the utility images to GHCR

Relevant workflow files:

- `.github/workflows/docker-pr-build.yml`
- `.github/workflows/docker-build.yml`

This lets contributors verify Docker changes in PRs while keeping image publishing limited to the `main` branch.
