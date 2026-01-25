# 🛡️ Draconian AniDB Mirror (Production)

A high-performance, private metadata hub for **Kometa** and **Plex**. This service acts as a "smart proxy" for the AniDB API, shielding your IP from bans while providing advanced relational features like tag-based searching and sequel mapping.



---

## 🚀 Core Strategy
* **IP Protection:** Strict 4-second request throttling and a hard 200 req/day limit.
* **Relational Intelligence:** Automatically indexes AniDB XMLs into a **SQLite** database for instant genre/franchise queries.
* **Production Security:** Standardized **HTTPS** via Caddy with **Basic Auth** protection.
* **Mature Content:** Authenticates with AniDB to fetch and cache "restricted" metadata.
* **Resilience:** Automatic maintenance pages during updates and daily S3 backups.

---

## 📂 Project Structure
```text
/anidb-mirror
├── data/                     # Persistent XML cache (.xml files)
├── main.py                   # FastAPI service & relational background worker
├── seed_db.py                # One-time tool to index existing XML collections
├── update.sh                 # Automated Git pull and Docker rebuild script
├── backup.sh                 # Daily local backups
├── backup-spaces.sh          # DigitalOcean Spaces backup integration
├── restore-spaces.sh         # Restore from Spaces backup
├── deploy-digitalocean.sh    # Automated DigitalOcean deployment
├── maintenance.html          # Custom page served during updates
├── database.db               # SQLite data (Tags, Relations, Quota Logs)
├── Caddyfile                 # Reverse proxy & Auth configuration
├── Dockerfile                # Python 3.11-slim container definition
├── docker-compose.yml        # Multi-container orchestration
└── terraform/                # Infrastructure as Code
    └── digitalocean/         # DigitalOcean Terraform configs
```

---

## 🌐 Deployment Options

### Quick Deploy
- **[DigitalOcean](DIGITALOCEAN_DEPLOYMENT.md)** - $6/month, automated script available
- **[AWS Free Tier](AWS_DEPLOYMENT.md)** - Free for 12 months, then ~$5-10/month
- **[Oracle Cloud](ORACLE_DEPLOYMENT.md)** - Always free tier available

### Infrastructure as Code
- **[Terraform (DigitalOcean)](terraform/digitalocean/README.md)** - Automated infrastructure provisioning

---