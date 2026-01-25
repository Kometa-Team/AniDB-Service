variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for droplet access"
  type        = string
}

variable "droplet_name" {
  description = "Name of the droplet"
  type        = string
  default     = "anidb-mirror"
}

variable "region" {
  description = "DigitalOcean region (nyc1, nyc3, sfo3, ams3, sgp1, lon1, fra1, tor1, blr1)"
  type        = string
  default     = "nyc3"
}

variable "droplet_size" {
  description = "Droplet size slug"
  type        = string
  default     = "s-1vcpu-1gb" # $6/month
}

variable "droplet_image" {
  description = "Operating system image"
  type        = string
  default     = "ubuntu-24-04-x64"
}

variable "enable_backups" {
  description = "Enable automated weekly backups (+$1.20/month for basic droplet)"
  type        = bool
  default     = true
}

variable "ssh_allowed_ips" {
  description = "List of IP addresses allowed to SSH (CIDR notation). Use ['0.0.0.0/0'] for all IPs (less secure)"
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}

variable "tags" {
  description = "Tags for the droplet"
  type        = list(string)
  default     = ["anidb-service", "production"]
}

variable "use_reserved_ip" {
  description = "Use a reserved IP (static IP that survives droplet rebuilds)"
  type        = bool
  default     = false
}

variable "domain_name" {
  description = "Domain name for the service (used in Caddyfile)"
  type        = string
  default     = "anidb-service.example.com"
}

variable "create_dns_record" {
  description = "Create DNS A record in DigitalOcean"
  type        = bool
  default     = false
}

variable "dns_domain" {
  description = "The domain to add DNS record to (must already exist in DO)"
  type        = string
  default     = "example.com"
}

variable "dns_subdomain" {
  description = "Subdomain for the A record"
  type        = string
  default     = "anidb-service"
}

variable "environment" {
  description = "Environment (Production, Staging, Development)"
  type        = string
  default     = "Production"
}

variable "create_project" {
  description = "Create a DigitalOcean project to organize resources"
  type        = bool
  default     = true
}

variable "create_spaces_bucket" {
  description = "Create a DigitalOcean Spaces bucket for backups"
  type        = bool
  default     = true
}

variable "spaces_bucket_name" {
  description = "Name for the Spaces bucket (must be globally unique)"
  type        = string
  default     = "anidb-backups"
}

variable "spaces_region" {
  description = "Region for Spaces bucket (nyc3, ams3, sgp1, sfo3, fra1)"
  type        = string
  default     = "nyc3"
}

variable "backup_retention_days" {
  description = "Number of days to retain backups in Spaces"
  type        = number
  default     = 30
}

variable "create_volume" {
  description = "Create additional storage volume for XML data"
  type        = bool
  default     = false
}

variable "volume_size" {
  description = "Size of additional volume in GB (min 1GB, max 16TB)"
  type        = number
  default     = 10
}
