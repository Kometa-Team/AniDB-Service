# DigitalOcean Infrastructure with Terraform

This directory contains Terraform configuration for automated DigitalOcean infrastructure deployment.

## What Gets Created

- **Droplet**: Ubuntu 24.04 server (configurable size, default $6/month)
- **Firewall**: Configured for SSH, HTTP, HTTPS
- **SSH Key**: Secure access to droplet
- **Reserved IP** (optional): Static IP that survives droplet rebuilds
- **Spaces Bucket** (optional): S3-compatible storage for backups
- **DNS Record** (optional): Automatic DNS configuration
- **Volume** (optional): Additional storage for XML data
- **Project**: Organizes all resources in DigitalOcean

## Prerequisites

1. **DigitalOcean Account**: [Sign up here](https://www.digitalocean.com)
2. **Terraform**: [Install Terraform](https://www.terraform.io/downloads)
3. **DigitalOcean API Token**: [Create token](https://cloud.digitalocean.com/account/api/tokens)
4. **SSH Key Pair**: Generate if you don't have one:
   ```bash
   ssh-keygen -t ed25519 -C "anidb-digitalocean" -f ~/.ssh/anidb_do
   ```

## Quick Start

### 1. Install Terraform

**macOS:**
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

**Linux:**
```bash
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

**Windows:**
```powershell
choco install terraform
```

Verify installation:
```bash
terraform version
```

### 2. Configure Variables

```bash
cd terraform/digitalocean

# Copy example configuration
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

**Required changes:**
- `do_token`: Your DigitalOcean API token
- `ssh_public_key`: Your public SSH key
- `domain_name`: Your domain for the service
- `spaces_bucket_name`: Unique name for backup storage

### 3. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview what will be created
terraform plan

# Deploy infrastructure
terraform apply
```

Type `yes` when prompted to confirm.

### 4. Get Connection Information

```bash
# View outputs
terraform output

# SSH into droplet
terraform output -raw ssh_connection_string | bash

# Or manually
ssh root@$(terraform output -raw public_ip)
```

### 5. Complete Setup

After Terraform completes:

```bash
# Switch to deploy user
ssh deploy@$(terraform output -raw public_ip)

# Navigate to application directory
cd /opt/anidb-service

# Configure environment
nano .env

# Update Caddyfile with your domain
nano Caddyfile

# Start services
docker compose up -d

# Watch logs
docker compose logs -f
```

## Configuration Options

### Basic Setup (Minimal Cost)

For the cheapest deployment ($6/month):

```hcl
droplet_size         = "s-1vcpu-1gb"
enable_backups       = false
use_reserved_ip      = false
create_spaces_bucket = false
create_volume        = false
```

### Recommended Setup

For production use ($7.20/month + Spaces storage):

```hcl
droplet_size         = "s-1vcpu-1gb"
enable_backups       = true   # +$1.20/month
use_reserved_ip      = false
create_spaces_bucket = true   # ~$0.20/month for 10GB
create_volume        = false
```

### High-Performance Setup

For larger deployments:

```hcl
droplet_size         = "s-2vcpu-4gb"  # $24/month
enable_backups       = true
use_reserved_ip      = true   # Free while assigned
create_spaces_bucket = true
create_volume        = true
volume_size          = 50     # GB
```

## Available Regions

- **NYC1/NYC3**: New York (US East)
- **SFO3**: San Francisco (US West)
- **AMS3**: Amsterdam (Europe)
- **SGP1**: Singapore (Asia)
- **LON1**: London (Europe)
- **FRA1**: Frankfurt (Europe)
- **TOR1**: Toronto (Canada)
- **BLR1**: Bangalore (India)

Choose the region closest to your users for best performance.

## DigitalOcean Spaces Setup

If you enabled Spaces for backups, create access keys:

1. Go to [API Tokens](https://cloud.digitalocean.com/account/api/spaces)
2. Click **Generate New Key**
3. Name it: `anidb-backups`
4. Save the **Access Key** and **Secret Key**
5. Add to your `.env` file on the droplet:

```bash
AWS_ACCESS_KEY_ID=your_spaces_access_key
AWS_SECRET_ACCESS_KEY=your_spaces_secret_key
AWS_DEFAULT_REGION=nyc3  # Match your Spaces region
S3_BUCKET_NAME=anidb-backups-yourname
S3_ENDPOINT=https://nyc3.digitaloceanspaces.com
```

## DNS Configuration

### Option 1: Manual DNS (Any Registrar)

Add an A record at your domain registrar:
```
Type: A
Name: anidb-service
Value: [droplet IP from terraform output]
TTL: 300
```

### Option 2: DigitalOcean DNS (Automated)

If your domain is managed by DigitalOcean:

1. Set `create_dns_record = true` in `terraform.tfvars`
2. Set `dns_domain` to your domain
3. Re-run `terraform apply`

### Option 3: Migrate to DigitalOcean DNS

1. Go to [DigitalOcean Networking](https://cloud.digitalocean.com/networking/domains)
2. Click **Add Domain**
3. Enter your domain
4. Copy the nameservers shown
5. Update nameservers at your registrar:
   - `ns1.digitalocean.com`
   - `ns2.digitalocean.com`
   - `ns3.digitalocean.com`
6. Wait 24-48 hours for propagation
7. Set `create_dns_record = true` and `terraform apply`

## Updating Infrastructure

```bash
# Modify terraform.tfvars as needed
nano terraform.tfvars

# Preview changes
terraform plan

# Apply changes
terraform apply
```

## Destroying Infrastructure

**WARNING**: This will delete everything!

```bash
# Preview what will be destroyed
terraform plan -destroy

# Destroy infrastructure
terraform destroy
```

Type `yes` when prompted.

## Cost Estimate

| Component | Cost |
|-----------|------|
| Basic Droplet (1GB) | $6.00/month |
| Automated Backups | +$1.20/month |
| Reserved IP (assigned) | Free |
| Spaces Storage (10GB) | ~$0.20/month |
| Spaces Transfer | Free (250GB/month) |
| **Total** | **~$7.40/month** |

After 1 year, estimate: **~$89/year**

## Troubleshooting

### Terraform Init Fails

```bash
# Clear cache and retry
rm -rf .terraform .terraform.lock.hcl
terraform init
```

### SSH Connection Refused

```bash
# Wait a few minutes for user-data script to complete
# Check droplet console in DigitalOcean dashboard

# View setup logs
ssh root@$(terraform output -raw public_ip)
tail -f /var/log/user-data.log
```

### Invalid Token Error

```bash
# Verify token in DigitalOcean dashboard
# Ensure token has both read and write permissions
# Create new token if needed
```

### Spaces Bucket Name Conflict

Spaces bucket names must be globally unique. Add a suffix:
```hcl
spaces_bucket_name = "anidb-backups-yourname-123"
```

## Best Practices

1. **Store `terraform.tfvars` securely**: Contains sensitive tokens
2. **Use Reserved IP for production**: Survives droplet rebuilds
3. **Enable backups**: Only $1.20/month for peace of mind
4. **Restrict SSH access**: Set `ssh_allowed_ips` to your IP range
5. **Use Spaces for backups**: Automatic retention and versioning
6. **Tag resources**: Helps with organization and billing

## State Management

Terraform stores state in `terraform.tfstate`. This file contains sensitive data.

**For personal use:**
- Keep `terraform.tfstate` in `.gitignore`
- Back it up securely

**For team use:**
- Use [Terraform Cloud](https://cloud.hashicorp.com/products/terraform) (free for small teams)
- Or use [DigitalOcean Spaces backend](https://www.terraform.io/docs/language/settings/backends/s3.html)

## Next Steps

After infrastructure is deployed:

1. Configure `.env` file on the droplet
2. Update Caddyfile with your domain
3. Configure Spaces backup credentials (if enabled)
4. Start Docker services
5. Test endpoints
6. Set up monitoring alerts
7. Document your specific configuration

## Support

- [DigitalOcean Documentation](https://docs.digitalocean.com)
- [Terraform DigitalOcean Provider](https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs)
- [DigitalOcean Community](https://www.digitalocean.com/community)
