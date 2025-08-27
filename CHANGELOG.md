# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-27

### Added
- **OpenWebUI Integration**: Complete AI chat interface with RAG capabilities
  - Web interface accessible at `http://localhost:3000`
  - GPU acceleration support for optimal performance
  - Seamless integration with existing Ollama models
  - Built-in RAG using Qdrant vector database
- **Enhanced AI Model Support**: Added gpt-oss:20b for maximum capability
- **Security Enhancements**: Comprehensive .gitignore updates
  - Added protection for certificate files (*.key, *.pem, *.p12, etc.)
  - Added .envrc file protection
  - Added backup/temp file protection
  - Added system file protection (.DS_Store, Thumbs.db)
- **Documentation Improvements**:
  - Updated service access information
  - Added OpenWebUI setup guide
  - Enhanced architecture documentation
  - Interactive HTML documentation with service status

### Changed
- **Security First**: Enhanced .gitignore with additional security patterns
- **Documentation**: Updated README.md and docs/index.html with OpenWebUI integration
- **Environment Configuration**: Added OpenWebUI secret key management
- **Service Architecture**: Integrated OpenWebUI with existing Docker network

### Security
- **Enhanced Protection**: Improved .gitignore to prevent accidental credential exposure
- **Secret Management**: Verified all sensitive files are properly excluded from git
- **Environment Security**: Added comprehensive environment file protection

## [Unreleased]

## [0.1.1] - 2025-04-24

### Added
- Explicit environment variable setup in `.env` file
- Task runner support with `N8N_RUNNERS_ENABLED=true`
- Troubleshooting section in README.md

### Changed
- Improved Docker Compose configuration to use environment variables consistently
- Updated README.md with more detailed setup instructions
- Enhanced documentation for environment variables

### Fixed
- Resolved environment variable warnings for PostgreSQL and n8n containers
- Fixed encryption key mismatch issues between n8n and its database
- Corrected database connection issues by properly resetting volumes when needed

## [0.1.0] - 2025-04-23

### Added
- Initial setup of n8n with PostgreSQL database
- Configured Ollama with NVIDIA GPU support
- Added llama3.1:8b model for LLM capabilities
- Added gemma3:12b model for enhanced AI processing
- Created shared directory for n8n workflows
- Set up secrets directory for secure credential storage
- Added Qdrant vector database
- Comprehensive documentation in README.md
- Environment configuration with secure keys

### Changed
- Updated n8n configuration to disable secure cookies for development
- Modified Docker Compose configuration for proper GPU support

### Removed
- Removed llama3.2 model in favor of llama3.1:8b

### Fixed
- Resolved cookie security issues in n8n
- Ensured proper NVIDIA GPU passthrough to containers