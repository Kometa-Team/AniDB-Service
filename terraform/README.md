# Terraform Infrastructure Files

This directory contains Terraform configurations for deploying AniDB Service infrastructure.

## Available Configurations

- [`digitalocean/`](digitalocean/) - DigitalOcean deployment with Terraform

## Quick Start

1. Choose your cloud provider directory
2. Copy `terraform.tfvars.example` to `terraform.tfvars`
3. Update variables with your values
4. Run:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

## Documentation

Each provider directory contains its own README with detailed instructions.
