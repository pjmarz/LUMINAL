#!/bin/bash
# ===========================================================================
# LUMINAL DOCKER REBUILD SCRIPT
# ===========================================================================
# Rebuilds all Docker containers by pulling latest images and restarting
# services. Includes cleanup of unused Docker resources.
# ===========================================================================

# Exit on error
set -e

# Get the script's directory path and the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LUMINAL_ROOT="$(dirname "$SCRIPT_DIR")"

# Source environment variables
ENV_FILE="${LUMINAL_ROOT}/env.sh"
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo "Environment file $ENV_FILE not found. Exiting."
    exit 1
fi

# Logging configuration
LOG_DIR="${LUMINAL_ROOT}/logs"
LOG_FILE="${LOG_DIR}/$(basename "$0" .sh).log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Initialize log file
: > "$LOG_FILE"

# Logging function
log() {
    local msg="$*"
    local timestamp
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "${timestamp} - ${msg}" | tee -a "$LOG_FILE"
}

# Error handling function
handle_error() {
    local exit_code=$?
    local line_number=$1
    log "Error on line $line_number: Exit code $exit_code"
    exit $exit_code
}

# Set error trap
trap 'handle_error $LINENO' ERR

# Log script start
log "=== LUMINAL Docker Rebuild Script Start ==="
log "Project root: $LUMINAL_ROOT"

# Function to rebuild all docker services using the root compose file
rebuild_docker_services() {
    log "Rebuilding all services using docker-compose.yml"

    cd "$LUMINAL_ROOT" || {
        log "Failed to change directory to $LUMINAL_ROOT"
        return 1
    }

    log "Stopping all containers..."
    docker compose down 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log "Failed to stop containers"
        return 1
    fi

    log "Pulling latest images for all services..."
    docker compose pull 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log "Failed to pull latest images"
        return 1
    fi

    log "Starting all containers..."
    docker compose up -d 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log "Failed to start containers"
        return 1
    fi

    log "Waiting for services to be healthy..."
    sleep 5

    # Show container status
    log "Container status:"
    docker compose ps 2>&1 | tee -a "$LOG_FILE"

    return 0
}

# Function to prune unused docker resources
prune_docker_system() {
    log "Pruning unused Docker resources..."
    
    log "Pruning stopped containers..."
    docker container prune -f --filter "label=com.docker.compose.project=luminal" 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log "Warning: Container pruning failed"
    fi
    
    log "Pruning unused images..."
    docker image prune -f --filter "label=com.docker.compose.project=luminal" 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log "Warning: Image pruning failed"
    fi

    log "Pruning unused networks..."
    docker network prune -f --filter "label=com.docker.compose.project=luminal" 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log "Warning: Network pruning failed"
    fi
    
    log "Docker resources pruning completed"
    return 0
}

# Function to display disk usage after cleanup
show_disk_usage() {
    log "Docker disk usage:"
    docker system df 2>&1 | tee -a "$LOG_FILE"
}

# Main execution
log "Starting LUMINAL rebuild process..."

# Rebuild all services
rebuild_docker_services

# Clean up any unused images, containers, and networks
prune_docker_system

# Show disk usage
show_disk_usage

# Cleanup function
cleanup() {
    local exit_code=$?
    log "=== Script Complete (Exit Code: $exit_code) ==="
}

trap cleanup EXIT
