# AWS Free Tier Deployment Guide

Complete guide to deploying AniDB Mirror Service on AWS Free Tier.

---

## 📋 What You'll Get (Free Tier)

- **EC2 Instance:** t2.micro (1 vCPU, 1 GB RAM) - 750 hours/month free for 12 months
- **Storage:** 30 GB EBS SSD - Free for 12 months
- **Data Transfer:** 15 GB outbound per month - Free
- **S3 Storage:** 5 GB standard storage - Free for 12 months
- **Elastic IP:** 1 static IP - Free when attached

**Estimated Monthly Cost After Free Tier:** $5-10/month depending on usage

---

## 🚀 Step-by-Step Deployment

### Part 1: AWS Account Setup

#### 1.1 Create AWS Account

1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Click "Create an AWS Account"
3. Follow signup process (requires credit card for verification)
4. Select "Basic Support (Free)" plan

#### 1.2 Set Up Billing Alerts

1. Go to **AWS Console → Billing Dashboard**
2. Click **Billing Preferences**
3. Enable:
   - ✅ Receive Free Tier Usage Alerts
   - ✅ Receive Billing Alerts
4. Set alert threshold: $5 USD
5. Save preferences

---

### Part 2: Launch EC2 Instance

#### 2.1 Create EC2 Instance

1. Go to **EC2 Dashboard**
2. Click **Launch Instance**

**Instance Configuration:**

| Setting | Value |
|---------|-------|
| **Name** | `anidb-mirror-server` |
| **AMI** | Ubuntu Server 24.04 LTS (Free tier eligible) |
| **Instance Type** | `t2.micro` (1 vCPU, 1 GB RAM) |
| **Key Pair** | Create new: `anidb-mirror-key.pem` (Download and save!) |
| **Network** | Default VPC |
| **Storage** | 30 GB gp3 (max free tier) |

#### 2.2 Configure Security Group

Create new security group: `anidb-mirror-sg`

**Inbound Rules:**

| Type | Protocol | Port | Source | Description |
|------|----------|------|--------|-------------|
| SSH | TCP | 22 | Your IP | SSH access |
| HTTP | TCP | 80 | 0.0.0.0/0 | Web traffic |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Secure web traffic |

**Outbound Rules:** Allow all (default)

#### 2.3 Launch Instance

1. Review settings
2. Click **Launch Instance**
3. Wait 2-3 minutes for instance to start
4. Note your **Public IPv4 Address**

---

### Part 3: Allocate Elastic IP

#### 3.1 Create Elastic IP

1. Go to **EC2 → Elastic IPs**
2. Click **Allocate Elastic IP address**
3. Click **Allocate**
4. Select the new IP → **Actions → Associate Elastic IP address**
5. Select your `anidb-mirror-server` instance
6. Click **Associate**

**Important:** Keep this IP associated to avoid charges ($0.005/hour for unattached IPs)

---

### Part 4: Domain Configuration

#### 4.1 Point Domain to Server

1. Go to your domain registrar (Namecheap, Cloudflare, etc.)
2. Add DNS A record:

```
Type: A
Name: anidb-service (or subdomain of your choice)
Value: [Your Elastic IP]
TTL: 300
```

Example: `anidb-service.yourdomain.com → 3.15.123.456`

#### 4.2 Wait for DNS Propagation

```bash
# Check DNS propagation (run locally)
nslookup anidb-service.yourdomain.com

# Or use online tool
https://dnschecker.org
```

---

### Part 5: Server Setup

#### 5.1 Connect to Server

```bash
# Set key permissions (Mac/Linux)
chmod 400 ~/Downloads/anidb-mirror-key.pem

# Connect via SSH
ssh -i ~/Downloads/anidb-mirror-key.pem ubuntu@[YOUR_ELASTIC_IP]
```

**Windows users:** Use PuTTY with .ppk converted key

#### 5.2 Update System

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y git curl wget unzip
```

#### 5.3 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker ubuntu

# Exit and reconnect for group changes
exit
# SSH back in
ssh -i ~/Downloads/anidb-mirror-key.pem ubuntu@[YOUR_ELASTIC_IP]

# Verify Docker
docker --version
docker compose version
```

#### 5.4 Install AWS CLI

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify
aws --version
```

---

### Part 6: Deploy Application

#### 6.1 Clone Repository

```bash
cd ~
git clone https://github.com/Kometa-Team/AniDB-Service.git
cd AniDB-Service
```

#### 6.2 Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Required Changes:**

```bash
# === API Authentication ===
API_USER=kometa_admin
API_PASS=YOUR_SECURE_PASSWORD_HERE  # Change this!

# === AniDB Configuration ===
ANIDB_USERNAME=your_anidb_username  # Your AniDB account
ANIDB_PASSWORD=your_anidb_password  # Your AniDB password

# === AWS S3 Backup ===
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
S3_BUCKET_NAME=anidb-mirror-backups-YOUR_NAME
```

#### 6.3 Update Caddyfile

```bash
nano Caddyfile
```

Replace `anidb-service.kometa.wiki` with your domain:

```
anidb-service.yourdomain.com {
    # ... rest of config
}
```

#### 6.4 Upload Seed Data (Optional)

If you have seed XML files:

```bash
# Create seed_data directory
mkdir -p seed_data

# Upload zip file from local machine
# On your local machine:
scp -i ~/Downloads/anidb-mirror-key.pem your-seed-data.zip ubuntu@[YOUR_ELASTIC_IP]:~/AniDB-Service/seed_data/
```

---

### Part 7: Launch Service

#### 8.1 Start Docker Containers

```bash
cd ~/AniDB-Service

# Build and start
docker compose up -d --build

# Watch logs
docker compose logs -f
```

**Expected output:**
```
🔧 Initializing AniDB Service...
📦 Extracting seed data from seed_data.zip...
✅ Extracted 1234 XML files
📚 Indexing 1234 seed files...
✅ Indexed 1234 files
🚀 AniDB worker started
✅ Service ready
```

#### 8.2 Verify Service

```bash
# Check container status
docker compose ps

# Test local endpoint
curl http://localhost:8000/stats

# Test from outside (replace with your domain)
curl https://anidb-service.yourdomain.com/stats
```

---

### Part 8: Automated Backups

#### 8.1 Make Scripts Executable

```bash
chmod +x backup.sh update.sh
```

#### 8.2 Test Backup

```bash
./backup.sh
```

Backups are stored locally in `./backups/` as compressed archives.

#### 8.3 Schedule Daily Backups

```bash
# Edit crontab
crontab -e

# Add these lines:
# Daily backup at 2 AM
0 2 * * * cd /home/ubuntu/AniDB-Service && ./backup.sh >> /home/ubuntu/backup.log 2>&1

# Daily update at 3 AM
0 3 * * * cd /home/ubuntu/AniDB-Service && ./update.sh >> /home/ubuntu/update.log 2>&1

# Weekly restart (optional, clears memory)
0 4 * * 0 cd /home/ubuntu/AniDB-Service && docker compose restart
```

---

### Part 9: Monitoring & Maintenance

#### 10.1 Check Service Health

```bash
# View logs
docker compose logs -f anidb-mirror
docker compose logs -f caddy

# Check stats
curl https://anidb-service.yourdomain.com/stats

# Check disk usage
df -h

# Check memory
free -h
```

#### 10.2 CloudWatch Monitoring (Optional)

1. Go to **CloudWatch → Alarms → Create Alarm**
2. Select metric: **EC2 → Per-Instance Metrics → CPUUtilization**
3. Set threshold: > 80% for 5 minutes
4. Configure notification (email/SNS)

#### 10.3 Set Up CloudWatch Logs

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure to send Docker logs
# (Follow AWS CloudWatch Agent documentation)
```

---

## 🔒 Security Hardening

### Restrict SSH Access

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Change:
PermitRootLogin no
PasswordAuthentication no
Port 2222  # Optional: change from default 22

# Restart SSH
sudo systemctl restart sshd
```

### Enable UFW Firewall

```bash
# Install and configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 2222/tcp  # SSH (or 22 if not changed)
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Check status
sudo ufw status
```

### Set Up Fail2Ban

```bash
# Install Fail2Ban
sudo apt install fail2ban -y

# Enable and start
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 💰 Cost Optimization

### Free Tier Limits (First 12 Months)

✅ **750 hours/month** EC2 t2.micro (enough for 1 instance 24/7)  
✅ **30 GB** EBS storage  
✅ **15 GB** data transfer out  
✅ **5 GB** S3 storage  
✅ **20,000** S3 GET requests  
✅ **2,000** S3 PUT requests

### After Free Tier Expires

**Estimated Monthly Costs:**

| Service | Cost |
|---------|------|
| EC2 t2.micro (on-demand) | ~$8.50 |
| EBS 30 GB | ~$3.00 |
| Elastic IP (attached) | Free |
| S3 Storage (10 GB) | ~$0.23 |
| Data Transfer (10 GB) | ~$0.90 |
| **Total** | **~$12.63/month** |

### Savings Options

1. **Reserved Instances:** Save up to 40% with 1-year commitment
2. **Spot Instances:** Save up to 90% (for non-critical workloads)
3. **Stop instance** when not in use (data persists, only pay for storage)

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose logs

# Check disk space
df -h

# Check memory
free -h

# Restart
docker compose restart
```

### Out of Memory

```bash
# Add swap space (1 GB instance needs this)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### SSL Certificate Issues

```bash
# Check Caddy logs
docker compose logs caddy

# Verify domain DNS
nslookup anidb-service.yourdomain.com

# Restart Caddy
docker compose restart caddy
```

### High CPU Usage

```bash
# Check Docker stats
docker stats

# Limit CPU usage in docker-compose.yml
services:
  anidb-mirror:
    deploy:
      resources:
        limits:
          cpus: '0.5'
```

---

## 📊 Performance Considerations

### t2.micro Limitations

- **1 vCPU, 1 GB RAM** - Handles ~100 requests/hour
- **Baseline CPU:** 10% with burst credits
- **Not suitable for:**
  - High-traffic production (>1000 req/day)
  - Large batch operations
  - Multiple concurrent users

### Upgrade Path

When you need more power:

1. **t3.small** ($15/month) - 2 vCPUs, 2 GB RAM
2. **t3.medium** ($30/month) - 2 vCPUs, 4 GB RAM
3. Add **RDS** for database (~$15/month for db.t3.micro)
4. Add **CloudFront** CDN for caching

---

## 🔄 Backup & Recovery

### Manual Backup

```bash
# Create local backup
./backup.sh

# Backups are stored in ./backups/ as compressed archives
# Copy to your preferred off-site location:
scp backups/anidb-backup-*.tar.gz user@your-backup-server:/path/
```

### Restore from Backup

```bash
# Stop service
docker compose down

# Extract backup
tar -xzf backups/anidb-backup-TIMESTAMP.tar.gz
cp database.db ./
cp -r data/* ./data/

# Restart service
docker compose up -d
```

### Disaster Recovery

If instance fails:

1. Launch new EC2 instance (same steps above)
2. Restore from S3 backup
3. Update Elastic IP association
4. Service resumes with all data intact

---

## ✅ Post-Deployment Checklist

- [ ] EC2 instance running with Elastic IP
- [ ] Domain pointing to server
- [ ] HTTPS working (check browser)
- [ ] `/stats` endpoint accessible
- [ ] Authentication working
- [ ] Local backups tested
- [ ] Cron jobs scheduled
- [ ] CloudWatch alarms set up
- [ ] Firewall configured
- [ ] Monitoring dashboard bookmarked
- [ ] Documentation saved locally

---

## 📞 Support Resources

- **AWS Free Tier Dashboard:** https://console.aws.amazon.com/billing/home#/freetier
- **AWS Documentation:** https://docs.aws.amazon.com
- **Docker Documentation:** https://docs.docker.com
- **AniDB API:** https://wiki.anidb.net/HTTP_API_Definition

---

## 🎯 Next Steps

1. Test API with Kometa
2. Monitor usage for 24 hours
3. Set up CloudWatch dashboards
4. Document any custom configurations
5. Schedule regular maintenance windows

**Congratulations! Your AniDB Mirror Service is now live on AWS! 🎉**
