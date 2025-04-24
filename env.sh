#!/bin/bash

# Source this file with:
# source ./env.sh

# This script loads environment variables for local development
# Docker Compose will use the secrets files directly

# Load PostgreSQL credentials
export POSTGRES_USER="n8n"
export POSTGRES_PASSWORD=$(cat ./secrets/postgres_password)
export POSTGRES_DB="n8n"

# Load n8n configuration
export N8N_ENCRYPTION_KEY=$(cat ./secrets/n8n_encryption_key)
export N8N_USER_MANAGEMENT_JWT_SECRET=$(cat ./secrets/n8n_jwt_secret)
export N8N_SECURE_COOKIE=false

# Add any other environment variables here
