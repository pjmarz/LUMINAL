#!/bin/bash
# ===========================================================================
# LUMINAL ENVIRONMENT VARIABLES
# ===========================================================================
# This file defines all environment variables used by the LUMINAL system.
# These variables are exported to the shell environment and used by scripts
# and Docker Compose files for configuration.
# ===========================================================================

# User/Group Settings
# These control file ownership and permissions in containers
export PUID=1000                # Process User ID - maps container processes to this host user ID
export PGID=984                 # Process Group ID - maps container processes to this host group ID
export UMASK=002                # File creation permission mask (002 = rwxrwxr-x)

# Timezone
# Used for logs, scheduling, and time-sensitive operations
export TZ="America/New_York"    # Timezone for all containers and services

# Base Directories
# Define the paths for configuration and shared data
export CONFIG_DIR="/etc/LUMINAL/config"    # Configuration files storage location
export SHARED_DIR="./shared"                # Shared data directory for n8n workflows

# AI Services Ports
# Ports for AI workflow and automation services
export N8N_PORT=5678            # n8n workflow automation UI port
export LANGFLOW_PORT=7860       # Langflow visual AI builder port
export OPENWEBUI_PORT=3000      # OpenWebUI AI chat interface port (maps to container 8080)

# AI Infrastructure Ports
# Ports for AI model inference and vector database services
export OLLAMA_PORT=11434        # Ollama LLM API port
export QDRANT_PORT=6333         # Qdrant vector database port

# AI Model Configuration
# Configuration for Ollama LLM models
export OLLAMA_BASE_URL="http://ollama:11434"  # Internal Ollama API URL for service communication
export QDRANT_URI="http://qdrant:6333"        # Internal Qdrant vector database URL
export VECTOR_DB="qdrant"                     # Vector database backend (qdrant)

# Ollama Models
# LLM models available in the Ollama service
export OLLAMA_MODEL_LLAMA="llama3.1:8b"       # Fast general-purpose model (4.9GB)
export OLLAMA_MODEL_GEMMA="gemma3:12b"        # High-performance model for complex tasks (8.1GB)
export OLLAMA_MODEL_GPT_OSS="gpt-oss:20b"     # Maximum capability for advanced reasoning (~20GB)

# n8n Configuration
# Settings for workflow automation
export N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true  # Enforce secure file permissions
export N8N_RUNNERS_ENABLED=true                    # Enable task runners for improved performance
export N8N_SECURE_COOKIE=false                     # Disable secure cookies for development

# OpenWebUI Configuration
# Settings for AI chat interface
export ENABLE_RAG_WEB_SEARCH=true           # Enable retrieval-augmented generation with web search
export RAG_WEB_SEARCH_ENGINE="searxng"      # Web search engine for RAG

# Langflow Configuration
# Settings for visual AI workflow builder
export LANGFLOW_AUTO_LOGIN=true             # Enable automatic login for convenience

# Logging
# Logging level configuration for services that support it
export LOG_LEVEL="debug"           # Standard logging level (debug, info, warn, error)

# ===========================================================================
# SECRETS LOADING
# ===========================================================================
# Load sensitive credentials from secrets directory
# These are used for local development; Docker Compose uses Docker Secrets directly
# ===========================================================================

# Get the directory where this script is located
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# n8n Secrets (if files exist)
# Reads encryption and JWT secrets from ./secrets/ directory
N8N_ENCRYPTION_KEY_FILE="${ENV_DIR}/secrets/n8n_encryption_key.txt"
if [ -f "$N8N_ENCRYPTION_KEY_FILE" ]; then
  # Strip newlines/carriage returns to avoid passing an invalid key
  export N8N_ENCRYPTION_KEY="$(tr -d '\n' < "$N8N_ENCRYPTION_KEY_FILE" | tr -d '\r')"
fi

N8N_JWT_SECRET_FILE="${ENV_DIR}/secrets/n8n_jwt_secret.txt"
if [ -f "$N8N_JWT_SECRET_FILE" ]; then
  export N8N_USER_MANAGEMENT_JWT_SECRET="$(tr -d '\n' < "$N8N_JWT_SECRET_FILE" | tr -d '\r')"
fi

# OpenWebUI Secret (if file exists)
# Reads secret key from ./secrets/ directory
OPENWEBUI_SECRET_KEY_FILE="${ENV_DIR}/secrets/openwebui_secret_key.txt"
if [ -f "$OPENWEBUI_SECRET_KEY_FILE" ]; then
  export OPENWEBUI_SECRET_KEY="$(tr -d '\n' < "$OPENWEBUI_SECRET_KEY_FILE" | tr -d '\r')"
fi
