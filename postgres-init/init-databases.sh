#!/bin/bash
set -e

# Read database passwords from Docker secrets
N8N_DB_PASSWORD=$(cat /run/secrets/n8n_db_password 2>/dev/null || echo "n8n")
LANGFLOW_DB_PASSWORD=$(cat /run/secrets/langflow_db_password 2>/dev/null || echo "langflow")

# Export environment variables for envsubst
export N8N_DB_PASSWORD
export LANGFLOW_DB_PASSWORD

# Use envsubst to substitute variables in template and execute via psql
envsubst < /docker-entrypoint-initdb.d/init-databases.sql.template | psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"

