# DigitalOcean Spaces Quick Setup Guide

DigitalOcean Spaces is an S3-compatible object storage service perfect for storing backups.

## What is Spaces?

- S3-compatible object storage
- 250GB free outbound transfer per month
- $5/month for 250GB storage
- Simple pricing, no surprise charges
- Works with AWS CLI and S3 tools

## Create a Spaces Bucket

### 1. Access Spaces

Go to: https://cloud.digitalocean.com/spaces

### 2. Create Bucket

1. Click **Create a Spaces Bucket**
2. Choose datacenter region (same as your droplet for best performance)
3. Enable CDN: **No** (not needed for backups)
4. Choose unique bucket name: `anidb-backups-yourname`
5. Select file listing: **Private**
6. Click **Create a Spaces Bucket**

### 3. Generate Access Keys

1. Go to: https://cloud.digitalocean.com/account/api/spaces
2. Click **Generate New Key**
3. Name: `anidb-backups`
4. Click **Generate Key**
5. **IMPORTANT**: Copy both keys immediately:
   - Access Key (like: `DO00ABCDEF...`)
   - Secret Key (like: `abc123xyz...`)
6. You cannot view the secret key again!

## Configure Your Service

### Option 1: During Deployment

The `deploy-digitalocean.sh` script will prompt for Spaces configuration.

### Option 2: Manual Configuration

Edit your `.env` file:

```bash
cd ~/anidb-service
nano .env
```

Add these lines:

```bash
# === DigitalOcean Spaces Backup ===
AWS_ACCESS_KEY_ID=DO00ABCDEFGHIJKLMNOP
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=nyc3
S3_BUCKET_NAME=anidb-backups-yourname
S3_ENDPOINT=https://nyc3.digitaloceanspaces.com
```

**Available Regions:**
- `nyc3` - New York
- `sfo3` - San Francisco
- `ams3` - Amsterdam
- `sgp1` - Singapore
- `fra1` - Frankfurt

## Test Your Configuration

```bash
# Test Spaces connection
aws s3 ls \
    --endpoint-url=https://nyc3.digitaloceanspaces.com \
    s3://anidb-backups-yourname/

# Should show empty bucket or existing files
```

## Perform Your First Backup

```bash
cd ~/anidb-service

# Run backup script
./backup-spaces.sh

# Check if backup appears in Spaces
aws s3 ls \
    --endpoint-url=https://nyc3.digitaloceanspaces.com \
    s3://anidb-backups-yourname/
```

## View Backups in Console

1. Go to https://cloud.digitalocean.com/spaces
2. Click your bucket name
3. See all backup files listed

## Restore from Backup

```bash
cd ~/anidb-service

# Run restore script (interactive)
./restore-spaces.sh

# Follow prompts to select backup
```

## Automated Backups

Set up cron job for daily backups:

```bash
crontab -e

# Add this line:
0 2 * * * cd /home/deploy/anidb-service && ./backup-spaces.sh >> /home/deploy/backup.log 2>&1
```

## Cost Calculator

**Storage:**
- First 250GB: $5/month
- Additional: $0.02/GB/month

**Transfer:**
- First 250GB outbound: Free
- Additional outbound: $0.01/GB
- Inbound: Always free

**Example Monthly Cost:**
```
10GB stored backups: $5.00 (minimum)
Backup uploads: Free (inbound)
Backup downloads: Free (under 250GB/month)
Total: $5.00/month
```

## Troubleshooting

### "403 Forbidden" Error

Check:
1. Access keys are correct in `.env`
2. Bucket name is correct
3. Region matches your bucket
4. Endpoint URL includes region

### "Unknown endpoint" Error

Make sure endpoint URL includes the region:
```bash
S3_ENDPOINT=https://nyc3.digitaloceanspaces.com
```
NOT:
```bash
S3_ENDPOINT=https://digitaloceanspaces.com
```

### Cannot List Bucket

Test with AWS CLI directly:
```bash
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"

aws s3 ls \
    --endpoint-url=https://nyc3.digitaloceanspaces.com \
    s3://your-bucket-name/
```

## Security Best Practices

1. **Use unique access keys** for each application
2. **Rotate keys** every 90 days
3. **Never commit keys** to git (already in .gitignore)
4. **Use private buckets** - never enable public access for backups
5. **Enable versioning** to protect against accidental deletion

## Lifecycle Management

To automatically delete old backups:

1. Go to Spaces bucket in console
2. Click **Settings** tab
3. Enable **Lifecycle Policy**
4. Set expiration: 30 days (or your preference)

Or let the `backup-spaces.sh` script handle it (deletes backups >30 days old).

## Alternative: Using rclone

If you prefer rclone over AWS CLI:

```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Configure
rclone config

# When prompted:
# Name: digitalocean
# Storage: s3
# Provider: DigitalOcean Spaces
# Access Key ID: your_key
# Secret Access Key: your_secret
# Endpoint: nyc3.digitaloceanspaces.com

# Test
rclone ls digitalocean:anidb-backups-yourname
```

## Resources

- [DigitalOcean Spaces Documentation](https://docs.digitalocean.com/products/spaces/)
- [AWS CLI with Spaces](https://docs.digitalocean.com/products/spaces/reference/aws-cli/)
- [s3cmd with Spaces](https://docs.digitalocean.com/products/spaces/reference/s3cmd/)
