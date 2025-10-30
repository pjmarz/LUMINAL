# LUMINAL - Self-Hosted AI Automation Platform

## Project Showcase

This repository demonstrates my skills in designing and implementing a containerized AI environment that integrates workflow automation with state-of-the-art AI capabilities. This project is primarily for showcasing technical expertise in job applications and interviews.

## Technical Architecture Overview

This platform integrates multiple cutting-edge technologies into a cohesive, containerized environment:

- **Workflow Automation**: n8n with custom AI nodes and integrations
- **Visual AI Development**: Langflow for drag-and-drop AI workflow creation
- **Data Persistence**: PostgreSQL with secure container configurations
- **AI Processing**:
  - Ollama with NVIDIA GPU acceleration for performant LLM inference
  - **OpenWebUI**: Self-hosted AI web interface with chat, RAG, and model management
  - Vector database (Qdrant) for semantic search and embeddings storage
- **Security**: Advanced secrets management and environment isolation

## Technical Skills Demonstrated

### Infrastructure & DevOps
- Docker containerization with advanced configuration patterns
- NVIDIA GPU passthrough for accelerated AI workloads
- Container orchestration with Docker Compose
- Automated container updates with Watchtower
- Secure secrets management and environment configuration
- Service networking and inter-container communication

### AI & Data Engineering
- Large Language Model (LLM) deployment and optimization
- Vector database setup for AI applications
- Database architecture for workflow automation
- Hardware acceleration integration for AI workloads

### Security Engineering
- Implementation of Docker security best practices
- Secrets management without hardcoded credentials
- Proper network isolation between services
- Environment variable security patterns
- Persistent volumes configured for data security

### System Architecture
- Multi-service application design
- Scalable workflow automation platform
- AI services integration
- Data persistence and reliability patterns

## Implementation Highlights

### Security-First Design
- No hardcoded credentials in Docker Compose files
- Sensitive information stored in secret files using Docker Secrets
- Secrets mounted directly into containers via `/run/secrets/`
- Environment variables loaded securely for local development

### Performance Optimization
- NVIDIA GPU acceleration for AI model inference
- Task runners for improved workflow execution
- Optimized container configurations for resource utilization

### Documentation and Knowledge Sharing
- Comprehensive architecture documentation
- Clear technical evolution tracking
- Troubleshooting guidance for complex systems

## Accessing Your Services

Once your stack is running, you can access the following services:

- **n8n Workflow Automation**: http://localhost:5678
- **Langflow Visual AI Builder**: http://localhost:7860
- **OpenWebUI AI Interface**: http://localhost:3000
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Ollama API**: http://localhost:11434

### Getting Started with Langflow

1. Visit http://localhost:7860 in your browser
2. Create your first workflow using the drag-and-drop interface
3. Langflow automatically detects your Ollama models (llama3.1:8b, gemma3:12b, gpt-oss:20b)
4. Build visual AI workflows with LangChain components!

### Key Langflow Features

- **Visual Workflow Builder**: Drag-and-drop interface for creating AI applications
- **LangChain Integration**: Access to 600+ integrations from the LangChain ecosystem
- **Ollama Integration**: Seamlessly use your local LLM models
- **GPU Acceleration**: Direct GPU passthrough for optimal performance
- **PostgreSQL Backend**: Persistent storage for your workflows and configurations
- **Qdrant Support**: Built-in vector database integration for RAG applications

### Getting Started with OpenWebUI

1. Visit http://localhost:3000 in your browser
2. Create your first admin account
3. Navigate to Settings → Models to verify your Ollama models are detected
4. Start chatting with your AI models!

### Key OpenWebUI Features

- **Multi-Model Support**: Seamlessly switch between llama3.1:8b, gemma3:12b, and gpt-oss:20b
  - **llama3.1:8b** (4.9GB) - Fast and capable general-purpose model
  - **gemma3:12b** (8.1GB) - High-performance model for complex tasks
  - **gpt-oss:20b** (~20GB) - Maximum capability for advanced reasoning
- **RAG Integration**: Built-in retrieval-augmented generation using your Qdrant vector database
- **GPU Acceleration**: Direct GPU passthrough for optimal performance
- **Secure Authentication**: JWT-based authentication with secure secret keys

## Environment Configuration

This project uses multiple environment management approaches:

- **`.env`**: Non-sensitive configuration variables (tracked in git as template)
- **`env.sh`**: Shell script for loading secrets into environment (tracked in git as template)
- **`.envrc`**: direnv configuration for automatic environment loading
- **`secrets/`**: Sensitive credentials and keys (excluded from git)

**Note**: The `.env` and `env.sh` files are included in the repository as templates. When you clone this project, you should update the `secrets/` directory with your own credentials. These environment files help with local development but never contain sensitive information directly.

## Technical Evolution

For a detailed log of the technical evolution of this project, including specific achievements and skills demonstrated, please see the [CHANGELOG.md](./CHANGELOG.md) file.
