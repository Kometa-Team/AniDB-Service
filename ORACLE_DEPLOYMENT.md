# Oracle Cloud Free Tier Deployment Guide

Deploy AniDB Mirror Service on Oracle Cloud's **Always Free** tier - **$0 forever**.

---

## 🎁 What You Get (Always Free - No Expiration)

- **2x Compute VMs:** AMD (1/8 OCPU, 1 GB RAM) OR 4x Arm Ampere A1 (4 cores, 24 GB RAM total)
- **Storage:** 200 GB block volumes total
- **Object Storage:** 20 GB (S3-compatible)
- **Data Transfer:** 10 TB outbound per month
- **Load Balancer:** 1 instance (10 Mbps)
- **Public IPv4:** 2 reserved IPs

**This is PERMANENTLY FREE - no credit card expiration after 12 months!**

---

## 🚀 Step-by-Step Deployment

### Part 1: Oracle Cloud Account Setup

#### 1.1 Create Account

1. Go to [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)
2. Click **Start for free**
3. Select your home region (cannot be changed later)
   - Recommended: **US East (Ashburn)** or closest to your users
4. Verify email and phone
5. Add credit card (for verification - won't be charged unless you upgrade)

#### 1.2 Wait for Activation

- Account activation takes **5-30 minutes**
- You'll receive email when ready
- Check spam folder if delayed

#### 1.3 First Login

1. Go to [cloud.oracle.com](https://cloud.oracle.com)
2. Enter your **Cloud Account Name** (from email)
3. Click **Continue**
4. Login with credentials

---

### Part 2: Create Compute Instance

#### 2.1 Navigate to Compute

1. Click **☰ Menu** → **Compute** → **Instances**
2. Ensure you're in correct compartment (usually "root")
3. Click **Create Instance**

#### 2.2 Instance Configuration

**Basic Information:**
- **Name:** `anidb-mirror-server`
- **Compartment:** (root) or create new

**Placement:**
- **Availability Domain:** (select any available)
- **Fault Domain:** (leave default)

**Image and Shape:**

1. Click **Edit** on Image and Shape
2. **Image:**
   - Click **Change Image**
   - Select **Canonical Ubuntu** → **24.04**
   - Click **Select Image**

3. **Shape:**
   - Click **Change Shape**
   - Select **AMD** (Intel and AMD)
   - Choose **VM.Standard.E2.1.Micro** (Always Free eligible)
   - Shows **1/8 OCPU, 1 GB RAM** ✅ Always Free

**Networking:**
- **VCN:** Create new VCN (or use existing)
- **Subnet:** Public subnet
- **Assign public IPv4:** ✅ Yes
- **Use network security groups:** ❌ No

**Add SSH Keys:**
- Select **Generate SSH key pair**
- Click **Save Private Key** → Save as `anidb-oracle-key`
- Click **Save Public Key** (optional backup)

**Boot Volume:**
- **Size:** 50 GB (within free tier 200 GB total)
- **VPUs:** 10 (Balanced performance)

#### 2.3 Create Instance

1. Click **Create**
2. Wait 2-3 minutes for provisioning
3. Instance state changes to **Running** (green)
4. Note your **Public IP Address**

---

### Part 3: Configure Networking

#### 3.1 Update Security List

1. Click on your instance name
2. Under **Instance Details**, find **Primary VNIC**
3. Click on the **Subnet** link
4. Click on the **Security List** (Default Security List)
5. Click **Add Ingress Rules**

**Add these rules:**

| Stateless | Source CIDR | IP Protocol | Source Port | Dest Port | Description |
|-----------|-------------|-------------|-------------|-----------|-------------|
| No | 0.0.0.0/0 | TCP | All | 80 | HTTP |
| No | 0.0.0.0/0 | TCP | All | 443 | HTTPS |
| No | YOUR_IP/32 | TCP | All | 22 | SSH (restrict to your IP) |

**Note:** Port 22 is already open by default. Consider restricting it to your IP for security.

#### 3.2 Reserve Public IP (Optional but Recommended)

1. Go to **☰ Menu** → **Networking** → **Reserved Public IPs**
2. Click **Reserve Public IP Address**
3. Name: `anidb-mirror-ip`
4. Click **Reserve**
5. Select the new IP → **⋮** → **Associate**
6. Select your instance and primary VNIC
7. Click **Associate**

---

### Part 4: Connect and Setup Server

#### 4.1 Connect via SSH

```bash
# Set key permissions (Mac/Linux)
chmod 400 ~/Downloads/anidb-oracle-key

# Connect (replace with your public IP)
ssh -i ~/Downloads/anidb-oracle-key ubuntu@[YOUR_PUBLIC_IP]
```

**Windows:** Use PuTTY or Windows Terminal with the key

#### 4.2 Update System and Firewall

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Configure firewall (Oracle Linux firewall must allow traffic)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

# Install essentials
sudo apt install -y git curl wget unzip
```

#### 4.3 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker ubuntu

# Exit and reconnect
exit
ssh -i ~/Downloads/anidb-oracle-key ubuntu@[YOUR_PUBLIC_IP]

# Verify
docker --version
docker compose version
```

---

### Part 5: Deploy Application

#### 5.1 Clone Repository

```bash
cd ~
git clone https://github.com/Kometa-Team/AniDB-Service.git
cd AniDB-Service
```

#### 5.2 Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit configuration
nano .env
```

**Update these values:**

```bash
# === API Authentication ===
API_USER=kometa_admin
API_PASS=YOUR_SECURE_PASSWORD

# === AniDB Configuration ===
ANIDB_USERNAME=your_anidb_username
ANIDB_PASSWORD=your_anidb_password
```

#### 5.3 Update Caddyfile

```bash
nano Caddyfile
```

Replace domain with yours:
```
anidb-service.yourdomain.com {
    # ... rest
}
```

#### 5.4 Upload Seed Data (Optional)

```bash
# On local machine
scp -i ~/Downloads/anidb-oracle-key seed-data.zip ubuntu@[PUBLIC_IP]:~/AniDB-Service/seed_data/
```

---

### Part 6: Launch Service

#### 7.1 Start Docker Containers

```bash
cd ~/AniDB-Service

# Build and start
docker compose up -d --build

# Watch logs
docker compose logs -f
```

#### 7.2 Test Service

```bash
# Local test
curl http://localhost:8000/stats

# External test
curl https://anidb-service.yourdomain.com/stats

# Test authentication
curl -u kometa_admin:YOUR_PASSWORD https://anidb-service.yourdomain.com/anime/1
```

---

### Part 7: Automated Backups

#### 7.1 Test Local Backups

```bash
chmod +x backup.sh
./backup.sh
```

Backups are stored locally in `./backups/` directory.

#### 7.2 Schedule Backups

```bash
# Make scripts executable
chmod +x backup.sh update.sh

# Test backup
./backup.sh

# Schedule with cron
crontab -e

# Add:
0 2 * * * cd /home/ubuntu/AniDB-Service && ./backup.sh >> /home/ubuntu/backup.log 2>&1
0 3 * * * cd /home/ubuntu/AniDB-Service && ./update.sh >> /home/ubuntu/update.log 2>&1
```

---

## 🔒 Security Best Practices

### Update Security List Rules

1. Go to your **Security List**
2. Edit the SSH rule (port 22)
3. Change **Source CIDR** from `0.0.0.0/0` to `YOUR_IP/32`
4. This restricts SSH to only your IP

### Enable OS Firewall

```bash
# UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Disable Password Authentication

```bash
sudo nano /etc/ssh/sshd_config

# Set:
PasswordAuthentication no
PermitRootLogin no

# Restart
sudo systemctl restart sshd
```

---

## 💡 Oracle Cloud Tips

### Instance Always Free Eligibility

✅ **VM.Standard.E2.1.Micro** - AMD (1/8 OCPU, 1 GB RAM)  
✅ **VM.Standard.A1.Flex** - ARM (up to 4 OCPU, 24 GB RAM total across all instances)

**Pro Tip:** Use ARM instances if available - you get 4 cores and 24 GB RAM free!

### Monitoring

1. Go to **☰ Menu** → **Observability & Management** → **Monitoring**
2. Default metrics available:
   - CPU utilization
   - Memory usage
   - Disk I/O
   - Network traffic

### Auto-Shutdown Prevention

Oracle may reclaim idle Always Free instances. Keep it active:

```bash
# Add to crontab
*/30 * * * * curl -s http://localhost:8000/stats > /dev/null
```

### Backup Strategy

- Object Storage: 20 GB free (plenty for database backups)
- Boot volume backups: Free (uses block storage quota)
- Keep 30 days of backups within free tier

---

## 🐛 Troubleshooting

### Cannot SSH

```bash
# Check instance is running
# OCI Console → Compute → Instances → Check status

# Verify Security List allows port 22
# Check Source CIDR includes your IP

# Try from different network
```

### HTTP/HTTPS Not Working

```bash
# Check iptables rules
sudo iptables -L -n | grep -E '80|443'

# If missing, add:
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

### Out of Memory

```bash
# Add 2GB swap (1GB instance needs this)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Object Storage Access Denied

```bash
# Verify credentials in .env
# Check bucket policy allows your user
# Verify endpoint URL is correct
# Test with oci CLI:
oci os object list --bucket-name anidb-backups
```

---

## 📊 Resource Limits (Always Free)

| Resource | Limit | Usage |
|----------|-------|-------|
| Compute (AMD) | 2 VMs | 1 VM |
| OCPU | 1/8 per VM | 1/8 total |
| Memory | 1 GB per VM | 1 GB total |
| Boot Volume | 200 GB total | 50 GB used |
| Block Volume | 200 GB total | 0 (not needed) |
| Object Storage | 20 GB | ~5-10 GB |
| Outbound Transfer | 10 TB/month | <1 GB/month |
| **Remaining** | **150 GB storage available** | **Can add more VMs!** |

---

## 🚀 Upgrade Options (If Needed)

**Scenario 1: Need More Power**
- Upgrade to VM.Standard.E2.2 (2 OCPUs, 16 GB) - $33/month
- Or use ARM A1.Flex (pay-as-you-grow)

**Scenario 2: Need High Availability**
- Deploy 2nd VM in different availability domain
- Use free load balancer
- Still within free tier!

**Scenario 3: Need Database**
- Oracle Autonomous Database Free Tier
- 2 databases, 20 GB each, forever free

---

## ✅ Post-Deployment Checklist

- [ ] Instance running with reserved public IP
- [ ] Domain DNS configured
- [ ] HTTPS working via Caddy
- [ ] `/stats` endpoint accessible
- [ ] Authentication working
- [ ] Local backups tested and scheduled
- [ ] Firewall configured (Security List + UFW)
- [ ] Monitoring dashboard checked
- [ ] Documentation saved

---

## 🎉 Benefits Over AWS

✅ **$0 forever** (not 12 months)  
✅ More generous free tier (10 TB vs 15 GB transfer)  
✅ Larger storage (200 GB vs 30 GB)  
✅ Can run multiple VMs in free tier  
✅ Free load balancer included  
✅ No surprise bills after year 1

**Oracle Cloud is perfect for this lightweight service - you'll never pay a cent!**
