# 🚀 AniDB Service - Setup Guide

Complete step-by-step setup instructions for deploying the AniDB Mirror service.

---

## 📋 Prerequisites

- Docker & Docker Compose installed
- AWS account with S3 access (for backups)
- Domain name configured (for HTTPS via Caddy)
- Git installed

---

## 🔧 Initial Setup

### 1. Clone and Configure

```bash
# Clone the repository
git clone <your-repo-url>
cd AniDB-Service

# Copy the environment template
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` with your actual values:

```bash
nano .env
```

**Required Changes:**

- `API_PASS`: Change to a strong password for API authentication
- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `S3_BUCKET_NAME`: Your S3 bucket name for backups

**Optional Adjustments:**

- `API_USER`: Default is `kometa_admin`
- `DAILY_LIMIT`: API requests per day (default: 200)
- `THROTTLE_SECONDS`: Delay between requests (default: 4)
- `UPDATE_THRESHOLD_DAYS`: Cache freshness in days (default: 7)

### 3. Update Caddyfile

Edit `Caddyfile` and replace `anidb-service.kometa.wiki` with your actual domain:

```bash
nano Caddyfile
```

### 4. Build and Start Services

```bash
# Build and start in detached mode
docker compose up -d --build

# Check logs
docker compose logs -f
```

---

### Verify Authentication

Test the API authentication:

```bash
# Should return 401 Unauthorized
curl https://your-domain.com/anime/1

# Should work with credentials
curl -u kometa_admin:your_password https://your-domain.com/anime/1
```

---

## 📊 Initial Data Seeding

If you have existing XML files from AniDB:

```bash
# Place XML files in ./data/ directory
cp /path/to/xmls/*.xml ./data/

# Run the seeding script
docker compose exec anidb-mirror python seed_db.py
```

---

## 🔄 Automated Updates

### Setup Git Auto-Deploy

The `update.sh` script handles automatic code updates:

```bash
# Make executable
chmod +x update.sh

# Test manual update
./update.sh
```

### Setup Cron for Updates

Add to crontab for daily updates at 3 AM:

```bash
crontab -e
```

Add this line:

```
0 3 * * * cd /path/to/AniDB-Service && ./update.sh >> /var/log/anidb-update.log 2>&1
```

---

## 💾 Backup Configuration

### AWS S3 Setup

1. Create an S3 bucket:
   ```bash
   aws s3 mb s3://your-anidb-mirror-backups
   ```

2. Make backup script executable:
   ```bash
   chmod +x backup.sh
   ```

3. Test backup:
   ```bash
   ./backup.sh
   ```

### Automated Daily Backups

Add to crontab for daily backups at 2 AM:

```bash
crontab -e
```

Add:

```
0 2 * * * cd /path/to/AniDB-Service && ./backup.sh >> /var/log/anidb-backup.log 2>&1
```

---

## 🔍 Monitoring & Health Checks

### Check Service Status

```bash
# View running containers
docker compose ps

# Check logs
docker compose logs -f anidb-mirror
docker compose logs -f caddy

# View database statistics
curl https://your-domain.com/stats
```

### Health Check Response

The `/stats` endpoint returns:

```json
{
  "status": "online",
  "cached_anime": 1234,
  "api_calls_last_24h": 45,
  "queue_size": 0,
  "daily_limit": 200
}
```

---

## 🛠️ Common Operations

### Restart Services

```bash
docker compose restart
```

### View Database

```bash
docker compose exec anidb-mirror sqlite3 /app/database.db
```

Example queries:

```sql
-- Count cached anime
SELECT COUNT(*) FROM anime;

-- View recent API calls
SELECT * FROM api_logs ORDER BY timestamp DESC LIMIT 10;

-- Search by tag
SELECT aid, name, weight FROM tags WHERE LOWER(name) LIKE '%action%';
```

### Clear Cache

```bash
# Stop services
docker compose down

# Remove database and XML files
rm database.db
rm -rf data/*

# Restart
docker compose up -d
```

---

## 🐛 Troubleshooting

### Issue: "Daily API limit reached"

**Solution:** Check current usage:

```bash
curl https://your-domain.com/stats
```

Wait until the 24-hour window resets or increase `DAILY_LIMIT` in `.env`.

### Issue: Container won't start

**Solution:** Check logs:

```bash
docker compose logs anidb-mirror
```

Common causes:
- Missing `.env` file
- Invalid environment variables
- Port conflicts (8000 already in use)

### Issue: 401 Unauthorized

**Solution:** Verify credentials in `.env` match those used in requests.

### Issue: AniDB ban

**Solution:** 
- Verify `THROTTLE_SECONDS` is at least 4
- Check `DAILY_LIMIT` hasn't been exceeded
- Wait 24 hours before retrying

---

## 📈 API Usage

### Fetch Anime by ID

```bash
curl -u username:password https://your-domain.com/anime/1
```

Returns XML metadata (cached or fetched from AniDB).

### Search by Tags

```bash
curl -u username:password "https://your-domain.com/search/tags?tags=action,comedy&min_weight=200"
```

Returns JSON with matching anime IDs.

### Check Statistics

```bash
curl https://your-domain.com/stats
```

Public endpoint (no authentication required).

---

## 🔄 Updating the Service

```bash
# Pull latest code
git pull origin main

# Run update script (rebuilds and restarts)
./update.sh
```

---

## 📞 Support

For issues or questions:
1. Check the logs: `docker compose logs -f`
2. Review AniDB API status: https://anidb.net/
3. Check your daily API limit via `/stats`

---

## 🔒 Security Best Practices

1. ✅ Always use HTTPS (Caddy handles this automatically)
2. ✅ Use strong passwords in `.env`
3. ✅ Never commit `.env` to Git (already in `.gitignore`)
4. ✅ Regularly backup to S3
5. ✅ Monitor API usage to avoid bans
6. ✅ Keep Docker images updated
7. ✅ Restrict server firewall to necessary ports (80, 443)

---

## 📚 Additional Resources

- [AniDB API Documentation](https://wiki.anidb.net/HTTP_API_Definition)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Caddy Documentation](https://caddyserver.com/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
