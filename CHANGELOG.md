# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-05-07

### Added
- **Midnight build pipeline**: `midnight/_shared.py` is the canonical home for `fuzzy_match` and `emit_status`; `midnight/build_tools.py` inlines it into each tool template via the `# {{INLINE_SHARED}}` marker, writing to `midnight/dist/`. The dist/ files are what gets uploaded to OpenWebUI; templates carry the marker. Build is deterministic — re-running produces byte-identical output (verified by self-test).
- **Real async tools (httpx)**: All Midnight tools migrated from blocking `requests` to `httpx.AsyncClient` via `http_get_json` / `http_post_json` helpers. The async signatures from v2.0.0 now match async bodies — calls actually run concurrently inside `asyncio.gather`.
- **Parallel API fan-out**:
  - Plex `search_by_actor` and `search_by_director` now fetch per-section results concurrently. On a 3-section library this drops latency ~3×.
  - Bazarr `check_subtitles`, `get_missing_subtitles`, `get_subtitle_history` parallelize their movies + series queries.
- **UserValves**: Per-user customization now wired into:
  - **Plex**: `DEFAULT_SECTION_FILTER` (`all` | `movies` | `shows`) — narrows `get_recently_added` when caller didn't specify.
  - **Bazarr**: `PREFERRED_LANGUAGES` (e.g. `"en,es"`) — filters missing-subtitle results to those languages.
  - **Seerr**: `AUTO_APPROVE` (bool) — submits requests with `isAutoApproved=true`. Seerr respects this only if the user has the auto-approve permission server-side.
- **Full event-emitter coverage**: All 29 public methods now emit a status event on entry. The "Searching Plex…" / "Fetching SABnzbd queue…" indicators render across the entire tool surface, not just the slow paths.
- **Golden-set evaluator**: `midnight/_goldenset.py` runs 12 reference prompts against OpenWebUI's chat completions API and scores each response on tool dispatch, non-empty, no-error, and absolute-date axes. Output: `midnight/_goldenset_results.md`.

### Changed
- **All 7 Midnight tools versioned to 2.1.0**.
- `midnight/dist/midnight_*.py` is now the canonical upload target (was `midnight/midnight_*.py` directly). README updated with the build workflow.
- Self-test now loads from `midnight/dist/`, mocks `http_get_json` instead of `requests.get`, and includes a build-determinism check (37 checks, <5s).

### Migration notes
- After pulling, run `python3 midnight/build_tools.py` once to regenerate `midnight/dist/`.
- In OpenWebUI: re-upload all 7 `dist/*.py` files. UserValves panes appear automatically in **Account → Tools** for users with access.
- The `requirements:` block now declares `httpx` instead of `requests`. OpenWebUI installs declared deps automatically on tool save.

## [1.4.0] - 2026-05-07

### Added
- **Anti-hallucination error surfacing**: Tool failures now reach the model as visible error strings instead of silent empty results. Bazarr, Radarr, Sonarr, SABnzbd, Seerr, and Tautulli public methods catch and translate transport/HTTP errors. Plex actor/director search accumulates per-section errors and reports partial-success state instead of silently dropping unreachable sections. Tautulli `get_most_watched` now reports per-stat-block errors (no more vacuous "Most watched content (last 30 days):" header on backend failure).
- **Local self-test**: `midnight/_selftest.py` validates the anti-hallucination contract by pointing every Valve at an unreachable host and asserting each public method returns a visible error string. Also covers `_fuzzy_match` and Seerr `_lookup_title` cache logic. Run with `python3 midnight/_selftest.py` (33 checks).
- **OpenWebUI conformance for Midnight tools**:
  - Top-level metadata blocks for all 7 tools now include `required_open_webui_version`, `requirements`, and `licence`.
  - All 29 public methods migrated to `async def` for forward compatibility with OpenWebUI's documented Tool API.
  - `__event_emitter__=None` parameter threaded through every public method. Status events ("Searching Plex…", "Found 12 results") wired on the highest-impact methods (search_by_actor, get_recently_added, list_movies_by_genre, list_shows_by_genre, get_most_watched, check_subtitles, get_download_queue, search_to_request).
  - `__user__` parameter added to Tautulli `get_activity` — sessions matching the OpenWebUI user are now labeled "you".
- **Knowledge retrieval guidance**: System prompt now explicitly instructs the model to call `query_knowledge_files` before tool selection. Required because Native function calling does NOT auto-inject attached Knowledge documents.
- **Fuzzy show-name matching**: Plex `get_episode_details` now fuzzy-matches `show_name` against returned grandparentTitle, so typos like "BoBs Burgers" still resolve. The Plex `_fuzzy_match` is now annotated as the canonical implementation; copies in radarr/sonarr/bazarr carry sync notes.

### Changed
- **Seerr rebrand**: `midnight_overseerr.py` renamed to `midnight_seerr.py`. Valves renamed (`OVERSEERR_URL` → `SEERR_URL`, `OVERSEERR_API_KEY` → `SEERR_API_KEY`). All docs updated. Existing OpenWebUI tool installations need to re-upload as `midnight_seerr_tool` and re-enter Valve config (copy URL + API key first).
- **Seerr request listings**: `get_pending_requests` and `get_recent_requests` now use a `_lookup_title` helper with an in-memory `_title_cache`, eliminating the N+1 detail calls per request listing (20 pending requests previously triggered ~21 HTTP calls).
- **Midnight model parameters** (`midnight/README.md`):
  - `keep_alive`: `5m` → `30m` (drops first-call latency from ~3s to ~50ms while gemma4:e4b stays resident).
  - `max_tokens`: `2048` → `4096` (long movie/show lists routinely exceed 2048 tokens in markdown).
  - Added `top_k=64`, `top_p=0.95`, `min_p=0.0` to match Google's documented Gemma optimums.
  - `temperature` kept at `0.4` (intentional divergence from Google's `1.0` default — trades exploration for tool-selection determinism in this assistant).

### Fixed
- Bazarr `check_subtitles` and `get_missing_subtitles` no longer swallow API errors with bare `except: pass` — they now accumulate per-endpoint errors and report partial-success state.
- SABnzbd `get_download_history` no longer drops rows on datetime-parse failure; missing dates render as "unknown date" instead.
- Seerr `_make_request` no longer mixes `{"error": ...}` dicts into success paths; callers raise/return cleanly.
- **OpenWebUI container TZ propagation**: `docker-compose.yml` now passes `TZ=${TZ}` to the openwebui service the same way it already does for n8n and home-assistant. Without it, the Python `datetime.fromtimestamp()` calls inside the Midnight Plex tool rendered Plex `addedAt` timestamps in UTC, causing chat dates to drift by one calendar day for items added near UTC midnight (e.g. evening EDT). Verified by side-by-side diff against the live tool output before/after the fix.

## [1.3.0] - 2026-04-17

### Added
- **Matter Server Service**: Added `python-matter-server` container for Home Assistant Matter protocol integration
  - Required for Matter/Thread device control in Docker environments
  - Runs on host network to communicate with Home Assistant
  - Persistent storage via `luminal_matter_storage` volume
- **Ollama DNS Configuration**: Added explicit DNS entries (`192.168.4.1`, `1.1.1.1`) to Ollama service for reliable model pulls
- **`update-ollama-models.sh`**: New maintenance script to update all configured Ollama models to latest versions
  - Sources environment from `.env`, verifies Ollama is running before pulling
  - Logs to `logs/update-ollama-models.log`

### Changed
- **Gemma Model Upgrade**: Upgraded from `gemma3:12b` (8.1GB) to `gemma4:e4b` (9.6GB)
  - Frontier-level multimodal model with native tool use
  - Now the base model for Midnight Media Assistant
- **`docker-rebuild.sh` Rewrite**: Complete rewrite with safe, non-destructive update logic
  - Pulls images before touching any running containers
  - Only recreates containers whose images actually changed (zero downtime for unchanged services)
  - HELIOS/VENUS compatible via `_common.sh` with standalone fallback for LUMINAL
  - New flags: `--dry-run`, `--skip-prune`, `--skip-health-check`, `--project-dir`
  - Post-update health check: detects unhealthy, restarting, and exited containers
  - Severity-based exit codes: 0=success, 1=partial failure, 2=complete failure
  - 3-retry logic with 15s delays for transient failures
  - Plex internal update check (`check_plex_update`) for projects with Plex containers
  - NVIDIA CDI spec regeneration after driver updates
  - `ensure_external_networks` helper for shared Docker networks

### Removed
- **`ollama-pull-translategemma` Service**: Removed dedicated translation model puller
  - `translategemma:12b` translation model is no longer part of the default stack

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