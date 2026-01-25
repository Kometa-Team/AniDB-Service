output "droplet_id" {
  description = "ID of the created droplet"
  value       = digitalocean_droplet.anidb_mirror.id
}

output "droplet_name" {
  description = "Name of the droplet"
  value       = digitalocean_droplet.anidb_mirror.name
}

output "droplet_ipv4" {
  description = "Public IPv4 address of the droplet"
  value       = digitalocean_droplet.anidb_mirror.ipv4_address
}

output "droplet_ipv6" {
  description = "Public IPv6 address of the droplet"
  value       = digitalocean_droplet.anidb_mirror.ipv6_address
}

output "reserved_ip" {
  description = "Reserved IP address (if enabled)"
  value       = var.use_reserved_ip ? digitalocean_reserved_ip.anidb[0].ip_address : null
}

output "public_ip" {
  description = "Public IP to use for DNS (reserved IP if enabled, otherwise droplet IP)"
  value       = var.use_reserved_ip ? digitalocean_reserved_ip.anidb[0].ip_address : digitalocean_droplet.anidb_mirror.ipv4_address
}

output "spaces_bucket_name" {
  description = "Name of the Spaces bucket for backups"
  value       = var.create_spaces_bucket ? digitalocean_spaces_bucket.anidb_backups[0].name : null
}

output "spaces_endpoint" {
  description = "Spaces endpoint URL"
  value       = var.create_spaces_bucket ? "https://${var.spaces_region}.digitaloceanspaces.com" : null
}

output "spaces_bucket_domain" {
  description = "Full Spaces bucket domain"
  value       = var.create_spaces_bucket ? "${digitalocean_spaces_bucket.anidb_backups[0].name}.${var.spaces_region}.digitaloceanspaces.com" : null
}

output "ssh_connection_string" {
  description = "SSH connection command"
  value       = "ssh root@${var.use_reserved_ip ? digitalocean_reserved_ip.anidb[0].ip_address : digitalocean_droplet.anidb_mirror.ipv4_address}"
}

output "dns_record" {
  description = "DNS A record (if created)"
  value       = var.create_dns_record ? "${digitalocean_record.anidb[0].name}.${var.dns_domain}" : null
}

output "volume_id" {
  description = "ID of the additional storage volume (if created)"
  value       = var.create_volume ? digitalocean_volume.anidb_data[0].id : null
}

output "project_id" {
  description = "ID of the DigitalOcean project (if created)"
  value       = var.create_project ? digitalocean_project.anidb[0].id : null
}
