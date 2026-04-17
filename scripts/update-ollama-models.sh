#!/bin/bash
# ===========================================================================
# LUMINAL OLLAMA MODEL UPDATE SCRIPT
# ===========================================================================
# Updates all configured Ollama models to their latest versions.
# Run this script periodically to ensure models are up to date.
# ===========================================================================

# Exit on error
set -e

# Get the script's directory path and the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LUMINAL_ROOT="$(dirname "$SCRIPT_DIR")"

# Source environment variables
ENV_FILE="${LUMINAL_ROOT}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
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
log "=== LUMINAL Ollama Model Update Script Start ==="
log "Project root: $LUMINAL_ROOT"

# Define models to update (use env vars with defaults matching docker-compose.yml)
MODELS=(
    "${OLLAMA_MODEL_LLAMA:-llama3.1:8b}"
    "${OLLAMA_MODEL_GEMMA:-gemma3:12b}"
    "${OLLAMA_MODEL_GPT_OSS:-gpt-oss:20b}"
)

# Check if Ollama container is running
check_ollama_running() {
    if ! docker ps --format '{{.Names}}' | grep -q '^ollama$'; then
        log "ERROR: Ollama container is not running."
        log "Start the stack with: docker compose up -d"
        exit 1
    fi
    log "Ollama container is running"
}

# Show current models
show_current_models() {
    log "Current models installed:"
    docker exec ollama ollama list 2>&1 | tee -a "$LOG_FILE"
}

# Update a single model
update_model() {
    local model="$1"
    log "Pulling latest version of: $model"
    docker exec ollama ollama pull "$model" 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log "Successfully updated: $model"
    else
        log "WARNING: Failed to update: $model"
    fi
}

# Main execution
log "Starting model update process..."

# Verify Ollama is running
check_ollama_running

# Show current state
log "--- Current Model State ---"
show_current_models

# Update each model
log "--- Updating Models ---"
for model in "${MODELS[@]}"; do
    update_model "$model"
done

# Show final state
log "--- Final Model State ---"
show_current_models

# Cleanup function
cleanup() {
    local exit_code=$?
    log "=== Script Complete (Exit Code: $exit_code) ==="
}

trap cleanup EXIT
