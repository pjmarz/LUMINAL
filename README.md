<div align="center">
  <a href="https://github.com/pjmarz/LUMINAL">
    <h1>LUMINAL</h1>
  </a>
</div>

---

> Note: This repository is a showcase of the LUMINAL architecture and user experience. It is not a turnkey deployment and is not intended to be cloned or run as-is.

## 🎯 Project Overview

LUMINAL is a self-hosted AI automation platform built with Docker and Docker Compose that integrates workflow automation with state-of-the-art AI capabilities. The project demonstrates containerized AI services including LLM inference, visual workflow development, and intelligent automation tools.

## 🛠️ System Components

<table>
  <thead>
    <tr>
      <th>Category</th>
      <th colspan="2">Service</th>
      <th>Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="3"><b>🤖 AI Services</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/n8n.png" width="32" height="32" alt="n8n"></td>
      <td><b><a href="https://github.com/n8n-io/n8n">n8n</a></b></td>
      <td>Workflow Automation Platform</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/open-webui.png" width="32" height="32" alt="OpenWebUI"></td>
      <td><b><a href="https://github.com/open-webui/open-webui">OpenWebUI</a></b></td>
      <td>AI Chat Interface with RAG</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/ollama.png" width="32" height="32" alt="Ollama"></td>
      <td><b><a href="https://github.com/ollama/ollama">Ollama</a></b></td>
      <td>Local LLM Inference Server</td>
    </tr>
    <tr>
      <td rowspan="2"><b>🧠 AI Infrastructure</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/qdrant.png" width="32" height="32" alt="Qdrant"></td>
      <td><b><a href="https://github.com/qdrant/qdrant">Qdrant</a></b></td>
      <td>Vector Database for Semantic Search</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/docker.png" width="36" height="24" alt="Docker"></td>
      <td><b><a href="https://www.docker.com/">Docker</a></b></td>
      <td>Containerization Platform</td>
    </tr>
    <tr>
      <td rowspan="1"><b>🏠 Home Automation</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/home-assistant.png" width="32" height="32" alt="Home Assistant"></td>
      <td><b><a href="https://www.home-assistant.io/">Home Assistant</a></b></td>
      <td>Home Automation Platform</td>
    </tr>
  </tbody>
</table>

## ✅ Prerequisites (for reference only)

- **Docker**: Engine installed and running
- **Docker Compose v2**: `docker compose` CLI available
- **NVIDIA GPU** (recommended): For accelerated AI workloads
- **Proxmox VE** (optional): Recommended host environment

## 🔐 Secrets & Environment Configuration

### 🔄 Environment Variable Management

LUMINAL uses **direnv** for automatic environment variable loading:

- **`.envrc`**: Automatically loads `.env` (for Docker Compose) and `env.sh` (for scripts)
- **direnv hook**: Configured in shell for seamless environment isolation
- **Automatic loading**: Environment variables load automatically when you `cd` into the project directory
- **Script compatibility**: Scripts still source `env.sh` explicitly for non-interactive execution (cron, etc.)

This ensures consistent environment variable access across interactive shells, scripts, and Docker Compose commands.

LUMINAL uses a centralized architecture for managing environment files and secrets, following Docker best practices:

### Centralized Architecture

- **`/etc/LUMINAL/env.sh`**: Centralized environment configuration file (actual file location)
  - **`env.sh`** in project root is a symlink pointing to `/etc/LUMINAL/env.sh`
  - Excluded from git (tracked in `.gitignore`)
  - Contains environment variable exports for local development
  
- **`/etc/LUMINAL/secrets/`**: Centralized secrets directory (actual directory location)
  - **`secrets/`** in project root is a symlink pointing to `/etc/LUMINAL/secrets`
  - Excluded from git (tracked in `.gitignore`)
  - Contains sensitive credentials and keys managed via Docker Secrets

### Setting Up Secrets

Create the following files with secure permissions in `/etc/LUMINAL/secrets/`:

```bash
mkdir -p /etc/LUMINAL/secrets
printf "<YOUR_N8N_ENCRYPTION_KEY>\n" > /etc/LUMINAL/secrets/n8n_encryption_key.txt
printf "<YOUR_N8N_JWT_SECRET>\n" > /etc/LUMINAL/secrets/n8n_jwt_secret.txt
printf "<YOUR_OPENWEBUI_SECRET_KEY>\n" > /etc/LUMINAL/secrets/openwebui_secret_key.txt
chmod 700 /etc/LUMINAL/secrets
chmod 600 /etc/LUMINAL/secrets/*
```

The symlinks in the project root (`env.sh` and `secrets/`) will automatically point to these centralized locations.

### Required Secrets

- **n8n_encryption_key.txt**: Encryption key for n8n credential storage (32+ characters recommended)
- **n8n_jwt_secret.txt**: JWT secret for n8n user authentication (64 characters recommended)
- **openwebui_secret_key.txt**: Secret key for OpenWebUI session management (64 characters recommended)

This centralized approach ensures consistent configuration management across the system and aligns with industry best practices for Docker-based deployments.

## 💾 Storage Configuration

LUMINAL uses Docker Named Volumes for all persistent data storage, ensuring separation of data from the container lifecycle.

### Storage Architecture

- **`luminal_n8n_storage`**: Stores n8n workflows, credentials, and execution data.
- **`luminal_ollama_storage`**: caches downloaded LLM models (approx. 40GB+ for full model set).
- **`luminal_qdrant_storage`**: Stores vector embeddings and database indices.
- **`luminal_openwebui_storage`**: Persists chat history, user settings, and document knowledge base.
- **`luminal_homeassistant_storage`**: Stores Home Assistant configuration (`configuration.yaml`, database).

### File Ownership

- **PUID/PGID**: All services are configured to run with specific user/group IDs (defined in `.env`) to ensure file permissions on mounted volumes match the host system user.

## 🚀 Quickstart (for reference only)

```bash
# 1) Set up environment and secrets
# Create /etc/LUMINAL/env.sh and /etc/LUMINAL/secrets/ (see above)

# 2) Start all services
docker compose up -d

# 3) Stop services (optional)
docker compose down
```

## 🎨 Accessing Your Services

Once your stack is running, you can access the following services:

- **n8n Workflow Automation**: http://localhost:5678
- **OpenWebUI AI Interface**: http://localhost:3000
- **Home Assistant**: http://localhost:8123
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Ollama API**: http://localhost:11434

### Key OpenWebUI Features

- **Multi-Model Support**: Seamlessly switch between llama3.1:8b, gemma3:12b, and gpt-oss:20b
- **RAG Integration**: Built-in retrieval-augmented generation using your Qdrant vector database
- **GPU Acceleration**: Direct GPU passthrough for optimal performance
- **Secure Authentication**: JWT-based authentication with secure secret keys

### AI-Powered Home Automation Examples

- **Natural Language Control**: Chat with OpenWebUI → n8n processes request → Home Assistant executes device control
- **Intelligent Automation**: Motion sensor triggers → n8n workflow → AI analyzes with Ollama → Smart response via Home Assistant
- **Predictive Automation**: AI analyzes usage patterns → n8n workflows → Proactive home automation via Home Assistant

## 🧩 Architecture & Configuration

- Single project name: `luminal`
- Unified network architecture:
  - `luminal_default`: Main application network (all AI services)
- Secrets stored in `/etc/LUMINAL/secrets/` (centralized location, symlinked from project root)
- Environment variables centralized at `/etc/LUMINAL/env.sh` (symlinked from project root)
- NVIDIA GPU passthrough for accelerated AI workloads (Ollama, OpenWebUI)

## 💡 Implementation Details

### 📁 Configuration Directory Ownership

LUMINAL follows Docker best practices for configuration directory ownership:

- **Ownership**: Service configuration directories follow container-specific ownership requirements
- **Permissions**: All config directories use appropriate permissions for container access
- **Rationale**: Ensures container-created files have consistent ownership
- **Benefits**: Prevents permission issues, aligns with Docker ecosystem standards

## 🧠 AI Models

LUMINAL supports three LLM models via Ollama:

- **llama3.1:8b** (4.9GB) - Fast and capable general-purpose model
- **gemma3:12b** (8.1GB) - High-performance model for complex tasks
- **gpt-oss:20b** (~20GB) - Maximum capability for advanced reasoning

Models are automatically pulled on first startup and cached in the `ollama_storage` volume.

## 📚 Technical Skills Demonstrated

### Infrastructure & DevOps
- Docker containerization with advanced configuration patterns
- NVIDIA GPU passthrough for accelerated AI workloads
- Container orchestration with Docker Compose
- Secure secrets management and environment configuration
- Service networking and inter-container communication

### AI & Data Engineering
- Large Language Model (LLM) deployment and optimization
- Vector database setup for AI applications
- Workflow automation architecture
- Hardware acceleration integration for AI workloads
- Retrieval-augmented generation (RAG) implementation

### Security Engineering
- Implementation of Docker security best practices
- Secrets management without hardcoded credentials
- Proper network isolation between services
- Environment variable security patterns
- Persistent volumes configured for data security

## Technical Evolution

For a detailed log of the technical evolution of this project, including specific achievements and skills demonstrated, please see the [CHANGELOG.md](./CHANGELOG.md) file.

---

<div align="center">
  <p align="center">
    <sub><i>the child of light</i></sub>
  </p>
</div>
