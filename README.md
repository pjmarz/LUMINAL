# LUMINAL - Self-Hosted AI Automation Platform

## Project Showcase

This repository demonstrates my skills in designing and implementing a containerized AI environment that integrates workflow automation with state-of-the-art AI capabilities. This project is primarily for showcasing technical expertise in job applications and interviews.

## Technical Architecture Overview

This platform integrates multiple cutting-edge technologies into a cohesive, containerized environment:

- **Workflow Automation**: n8n with custom AI nodes and integrations
- **Data Persistence**: PostgreSQL with secure container configurations
- **AI Processing**: 
  - Ollama with NVIDIA GPU acceleration for performant LLM inference
  - Vector database (Qdrant) for semantic search and embeddings storage
- **Security**: Advanced secrets management and environment isolation

## Technical Skills Demonstrated

### Infrastructure & DevOps
- Docker containerization with advanced configuration patterns
- NVIDIA GPU passthrough for accelerated AI workloads
- Container orchestration with Docker Compose
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

## Technical Evolution

For a detailed log of the technical evolution of this project, including specific achievements and skills demonstrated, please see the [CHANGELOG.md](./CHANGELOG.md) file.
