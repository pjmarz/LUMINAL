#!/bin/bash
set -e

# Read secrets from Docker secrets mount point
PGADMIN_EMAIL=$(cat /run/secrets/pgadmin_email 2>/dev/null || echo "admin@admin.com")
PGADMIN_PASSWORD=$(cat /run/secrets/pgadmin_password 2>/dev/null || echo "admin")

# Export environment variables for pgAdmin
export PGADMIN_DEFAULT_EMAIL="${PGADMIN_EMAIL}"
export PGADMIN_DEFAULT_PASSWORD="${PGADMIN_PASSWORD}"

# Execute the original pgAdmin entrypoint
exec /entrypoint.sh "$@"

