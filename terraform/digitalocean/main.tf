terraform {
  required_version = ">= 1.0"
  
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

# Configure DigitalOcean provider
provider "digitalocean" {
  token = var.do_token
}

# SSH Key for Droplet access
resource "digitalocean_ssh_key" "anidb" {
  name       = "anidb-service-key"
  public_key = var.ssh_public_key
}

# Droplet for AniDB Service
resource "digitalocean_droplet" "anidb_mirror" {
  name      = var.droplet_name
  region    = var.region
  size      = var.droplet_size
  image     = var.droplet_image
  
  ssh_keys  = [digitalocean_ssh_key.anidb.fingerprint]
  
  # Enable monitoring and backups
  monitoring = true
  backups    = var.enable_backups
  ipv6       = true
  
  # User data script for initial setup
  user_data = templatefile("${path.module}/user-data.sh", {
    domain_name = var.domain_name
  })
  
  tags = var.tags
}

# Firewall rules
resource "digitalocean_firewall" "anidb" {
  name = "anidb-service-firewall"
  
  droplet_ids = [digitalocean_droplet.anidb_mirror.id]
  
  # SSH
  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = var.ssh_allowed_ips
  }
  
  # HTTP
  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  # HTTPS
  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  # Allow all outbound
  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# Reserved IP (optional)
resource "digitalocean_reserved_ip" "anidb" {
  count  = var.use_reserved_ip ? 1 : 0
  region = var.region
}

resource "digitalocean_reserved_ip_assignment" "anidb" {
  count      = var.use_reserved_ip ? 1 : 0
  ip_address = digitalocean_reserved_ip.anidb[0].ip_address
  droplet_id = digitalocean_droplet.anidb_mirror.id
}

# DigitalOcean Spaces for backups (S3-compatible)
resource "digitalocean_spaces_bucket" "anidb_backups" {
  count  = var.create_spaces_bucket ? 1 : 0
  name   = var.spaces_bucket_name
  region = var.spaces_region
  
  acl = "private"
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    enabled = true
    id      = "delete-old-backups"
    
    expiration {
      days = var.backup_retention_days
    }
  }
}

# DNS record for the service
resource "digitalocean_record" "anidb" {
  count  = var.create_dns_record ? 1 : 0
  domain = var.dns_domain
  type   = "A"
  name   = var.dns_subdomain
  value  = var.use_reserved_ip ? digitalocean_reserved_ip.anidb[0].ip_address : digitalocean_droplet.anidb_mirror.ipv4_address
  ttl    = 300
}

# Project organization
resource "digitalocean_project" "anidb" {
  count       = var.create_project ? 1 : 0
  name        = "AniDB Service"
  description = "AniDB Mirror Service infrastructure"
  purpose     = "Service or API"
  environment = var.environment
  
  resources = concat(
    [digitalocean_droplet.anidb_mirror.urn],
    var.use_reserved_ip ? [digitalocean_reserved_ip.anidb[0].urn] : [],
    var.create_spaces_bucket ? [digitalocean_spaces_bucket.anidb_backups[0].urn] : []
  )
}

# Volume for additional storage (optional)
resource "digitalocean_volume" "anidb_data" {
  count                   = var.create_volume ? 1 : 0
  region                  = var.region
  name                    = "anidb-data-volume"
  size                    = var.volume_size
  description             = "Additional storage for AniDB XML data"
  initial_filesystem_type = "ext4"
}

resource "digitalocean_volume_attachment" "anidb_data" {
  count      = var.create_volume ? 1 : 0
  droplet_id = digitalocean_droplet.anidb_mirror.id
  volume_id  = digitalocean_volume.anidb_data[0].id
}
