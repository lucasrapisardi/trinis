#!/bin/bash
set -e

echo "=== ProductSync EC2 Setup ==="

# 1. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
sudo systemctl enable docker

# 3. Install Docker Compose plugin
sudo apt-get install -y docker-compose-plugin git certbot

# 4. Clone repo
cd ~
git clone https://github.com/lucasrapisardi/trinis.git trinis_ai
cd trinis_ai

echo "=== Setup complete! Now configure .env files ==="
echo "Run: nano trinis/.env.prod"
echo "Run: nano productsync-web/.env.prod"
echo "Run: nano .env"
