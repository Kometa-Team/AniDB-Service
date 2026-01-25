#!/bin/bash
set -e

# Log output to file
exec > >(tee -a /var/log/user-data.log)
exec 2>&1

echo "========================================"
echo "Starting AniDB Service Setup"
echo "Time: $(date)"
echo "========================================"

# Update system
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install essential packages
echo "Installing essential packages..."
apt-get install -y \
    git \
    curl \
    wget \
    unzip \
    ufw \
    fail2ban \
    htop

# Configure firewall
echo "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Install Docker
echo "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Create deploy user
echo "Creating deploy user..."
if ! id -u deploy &>/dev/null; then
    useradd -m -s /bin/bash deploy
    usermod -aG sudo deploy
    usermod -aG docker deploy
    
    # Set up SSH for deploy user
    mkdir -p /home/deploy/.ssh
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
    chown -R deploy:deploy /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh
    chmod 600 /home/deploy/.ssh/authorized_keys
fi

# Configure Fail2Ban
echo "Configuring Fail2Ban..."
cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
EOF

systemctl enable fail2ban
systemctl start fail2ban

# Enable automatic security updates
echo "Enabling automatic security updates..."
apt-get install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# Create swap space (helpful for 1GB RAM droplet)
echo "Creating swap space..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Create application directories
echo "Creating application directories..."
mkdir -p /opt/anidb-service
chown deploy:deploy /opt/anidb-service

# Install AWS CLI (for Spaces S3-compatible API)
echo "Installing AWS CLI for Spaces integration..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install
rm -rf awscliv2.zip aws/

# Download repository
echo "Cloning AniDB Service repository..."
su - deploy -c "cd /opt && git clone https://github.com/Kometa-Team/AniDB-Service.git anidb-service"

# Create .env template
echo "Creating .env template..."
su - deploy -c "cd /opt/anidb-service && cp .env.example .env"

# Harden SSH (optional)
echo "Hardening SSH configuration..."
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

echo "========================================"
echo "Initial setup complete!"
echo "Next steps:"
echo "1. SSH into droplet as 'deploy' user"
echo "2. Configure .env file at /opt/anidb-service/.env"
echo "3. Update Caddyfile with your domain: ${domain_name}"
echo "4. Run: cd /opt/anidb-service && docker compose up -d"
echo "========================================"
