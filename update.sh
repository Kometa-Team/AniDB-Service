#!/bin/bash

# --- CONFIG ---
# Ensure we are in the correct directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🔄 Starting AniDB Mirror update..."

# 1. Pull latest code from GitHub
echo "📥 Pulling latest changes from Git..."
git pull origin main

# 2. Rebuild and restart containers
# --build: Re-compiles your Dockerfile if main.py or requirements.txt changed
# -d: Keeps it running in the background
echo "🚀 Rebuilding and restarting containers..."
docker compose up -d --build

# 3. Clean up old images
# This removes "dangling" images from previous builds to save AWS disk space
echo "🧹 Cleaning up old Docker images..."
docker image prune -f

echo "✅ Update complete! Current status:"
docker compose ps
