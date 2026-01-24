# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-01-24

### Added
- **Cloudflare Access SSO Integration**: Google OAuth authentication for OpenWebUI
  - Trusted header authentication via Cloudflare Access
  - Automatic user provisioning on first OAuth login
  - Zero Trust security model - all access requires authentication
  - Configurable access policies for email/domain allowlisting

### Changed
- **OpenWebUI Authentication**: Migrated from local accounts to Cloudflare Access SSO
  - Added `WEBUI_URL` for public URL configuration
  - Added `WEBUI_AUTH_TRUSTED_EMAIL_HEADER` for Cloudflare email passthrough
  - Added `WEBUI_AUTH_TRUSTED_NAME_HEADER` for Cloudflare name passthrough
  - Added `ENABLE_OAUTH_SIGNUP` for automatic account creation

### Security
- **Zero Trust Architecture**: OpenWebUI now requires Cloudflare Access authentication
  - All traffic must pass through Cloudflare tunnel
  - Direct IP access disabled when trusted headers configured
  - Access policies managed in Cloudflare Zero Trust dashboard

## [1.1.0] - 2025-12-17

### Added
- **Midnight Cast Lookup Tool**: New `get_cast()` function in midnight_plex.py (v1.9.0)
  - Retrieve full cast list for any movie or TV show in Plex library
  - Returns actor names with their character/role names
  - Works for both movies (🎬) and TV shows (📺)
  - Configurable limit parameter (default: 10 cast members)
  - Fuzzy title matching for typo tolerance
  - Example: "Who's in 2012?" → Full cast with John Cusack as Jackson Curtis, etc.

### Changed
- Updated `README.md` system prompt with `get_cast()` documentation and tool selection guidance
- Updated `MIDNIGHT_REFERENCE.md` knowledge base with detailed function reference

## [1.0.0] - 2025-12-16

### Added
- **Midnight Media Assistant**: OpenWebUI-based media library assistant (v1.2.0)
  - 7 custom Python tools for Plex, Radarr, Sonarr, Bazarr, Tautulli, SABnzbd, Overseerr integration
  - Actor and director search with fuzzy matching for typo tolerance
  - Genre search with 30+ synonym mappings (sci-fi → Science Fiction, etc.)
  - Movie/TV show details: synopsis, runtime, ratings, file info
  - Real-time activity monitoring, watch history, download status
  - **Overseerr integration**: Search and request new movies/TV shows
  - Conceptual system prompt for reliable tool routing
  - Recommended base model: gemma3:12b for optimal performance
  - Anti-hallucination rules to ensure accurate responses

- **Documentation Page Redesign**: Complete visual overhaul of `docs/index.html`
  - **Lucid-style Architecture Diagram**: CSS-based diagram showing Proxmox cluster "Marz"
    - glados host with "dev" VM (`/root/LUMINAL/`) running OpenWebUI + Midnight
    - virgil host with "docker" VM (`/root/HELIOS/`) running media services
    - HTTP APIs connector between VMs
  - **Screenshots & Demos Section**: 4 clickable screenshot cards with lightbox modal
    - OpenWebUI Midnight Chat interface
    - n8n Workflow Automation dashboard
    - Qdrant Vector Database dashboard
    - Home Assistant Integration
  - **Text Visibility Fixes**: Added `!important` CSS overrides for all text elements
  - **Icon Improvements**: Fixed AI skill icon, added NVIDIA logo, consistent sizing
  - **Midnight Media Assistant Section**: Dedicated section with tools and capabilities

- **direnv Integration**: Automatic environment variable loading
  - Added `.envrc` file for automatic `.env` and `env.sh` loading
  - Configured direnv hook for seamless environment isolation
  - Environment variables automatically load when entering project directory
  - Enhanced script reliability with explicit `env.sh` sourcing for non-interactive execution

- **Documentation Enhancements**: Improved README structure and organization
  - Added direnv environment variable management section
  - Enhanced configuration directory ownership documentation
  - Improved section hierarchy and readability throughout README
  - Aligned documentation structure with HELIOS project patterns
- **Architecture Simplification**: Removed PostgreSQL infrastructure
  - Migrated n8n and langflow to default SQLite storage
  - Removed PostgreSQL service and pgAdmin
  - Eliminated database initialization scripts and wrapper scripts
  - Simplified docker-compose.yml to bare minimum essential services
  - Reduced complexity while maintaining full functionality
- **Configuration Management**: Added centralized config directory
  - Created `/etc/LUMINAL/config/` structure for service-specific configurations
  - Organized config directories for n8n, langflow, openwebui, and qdrant
  - Follows HELIOS pattern for consistency across projects

### Removed
- **Watchtower Service**: Removed from documentation and system components
  - Removed from README.md System Components table
  - Removed from Maintenance section references
  - Removed from Implementation Details section
  - Removed from index.html Infrastructure section
  - Removed from Technical Skills section
  - Removed comment from docker-compose.yml (service was never implemented)
- **PostgreSQL Infrastructure**: Removed database dependencies
  - Removed PostgreSQL service and all related configurations
  - Removed pgAdmin service
  - Removed postgres-init directory and all initialization scripts
  - Removed PostgreSQL-related secrets (postgres_password, n8n_db_password, langflow_db_password, pgadmin_email, pgadmin_password)
  - Removed PostgreSQL volume definitions

### Added
- **Langflow Integration**: Visual AI workflow builder with drag-and-drop interface
  - Web interface accessible at `http://localhost:7860`
  - GPU acceleration support for optimal performance
  - Seamless integration with existing Ollama models
  - SQLite backend for lightweight workflow storage
  - Built-in support for Qdrant vector database
  - Access to 600+ LangChain integrations
  - Visual development environment for rapid AI prototyping

### Changed
- **PostgreSQL Password Security**: Migrated to Docker secrets
  - Implemented `POSTGRES_PASSWORD_FILE` for superuser password
  - Follows PostgreSQL 16+ best practices for secret management
  - Eliminates hardcoded passwords in docker-compose.yml
- **n8n Database Password Security**: Migrated to Docker secrets
  - Changed `DB_POSTGRESDB_PASSWORD` to `DB_POSTGRESDB_PASSWORD_FILE=/run/secrets/n8n_db_password`
  - Eliminates hardcoded n8n database password from docker-compose.yml
- **Langflow Database Password Security**: Migrated to Docker secrets
  - Created wrapper script to read password from `/run/secrets/langflow_db_password`
  - Eliminates hardcoded password from database connection string
- **pgAdmin Credentials Security**: Migrated to Docker secrets
  - Created wrapper script to read email and password from Docker secrets
  - Eliminates hardcoded personal credentials from docker-compose.yml
- **PostgreSQL Initialization Scripts**: Enhanced with secrets support
  - Converted `init-databases.sql` to template with environment variable substitution
  - Created wrapper script using `envsubst` to inject secrets at runtime
  - Eliminates hardcoded passwords from database initialization scripts
- **Environment Configuration Documentation**: Added comprehensive section
  - Clarified purpose of `.env`, `env.sh`, and `.envrc` files
  - Documented template vs. secrets separation strategy
  - Follows 12-factor app methodology

### Technical
- **Best Practices Alignment**: 
  - Follows Docker ecosystem standards for configuration management
  - Improved environment isolation between projects
  - Enhanced script reliability for cron and non-interactive execution
  - Maintained backward compatibility with existing workflows

### Security
- **Eliminated All Hardcoded Passwords**: Complete migration to Docker secrets
  - No plaintext passwords in docker-compose.yml
  - No plaintext passwords in initialization scripts
  - All database credentials managed via Docker secrets
  - All service credentials managed via Docker secrets
  - Secrets properly excluded from version control via .gitignore
  - Comprehensive documentation added for all secret files

## [0.2.0] - 2025-08-27

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