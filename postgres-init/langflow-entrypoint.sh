#!/bin/bash
set -e

# Read langflow database password from Docker secrets
LANGFLOW_DB_PASSWORD=$(cat /run/secrets/langflow_db_password)

# Construct database URL with password from secret
export LANGFLOW_DATABASE_URL="postgresql://langflow:${LANGFLOW_DB_PASSWORD}@postgres:5432/langflow"

# Execute the original langflow entrypoint/command
exec "$@"

