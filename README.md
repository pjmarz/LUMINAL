<div align="center">
  <a href="https://github.com/pjmarz/LUMINAL">
    <img src="./docs/media/LUMINAL.apng" alt="LUMINAL" width="400">
  </a>
</div>

---

> Note: This repository is a showcase of the LUMINAL architecture and user experience. It is not a turnkey deployment and is not intended to be cloned or run as-is.

## 🎯 Overview

LUMINAL is a self-hosted AI automation platform that combines workflow orchestration, local LLM inference, retrieval-augmented generation, and smart-home control into a single Docker-Compose stack running on a Proxmox VM with NVIDIA GPU passthrough.

It exists as a living answer to a question: *how much of a modern AI product stack can run on your own hardware, behind your own auth, with no dependency on commercial inference APIs?* Every choice — local models over hosted APIs, Docker Secrets over `.env` passwords, Zero Trust SSO over local accounts, non-destructive update scripts over `docker compose down`— is an intentional trade-off in favor of self-hosted control, security, and reproducibility.

The marquee feature is **Midnight**, a custom tool-using AI assistant built on OpenWebUI that queries a real media library (Plex, Radarr, Sonarr, Tautulli, Bazarr, SABnzbd, Overseerr) through 7 Python function tools with anti-hallucination prompt engineering baked in.

## 🧩 Architecture

LUMINAL runs as a set of networked Docker containers on a Proxmox VM. The stack layers into roughly four tiers:

- **Edge / Auth** — Cloudflare Access sits in front of the public-facing OpenWebUI endpoint, handling Google OAuth via trusted-header SSO. No local passwords.
- **Interface** — OpenWebUI is the chat frontend. It hosts the Midnight assistant, handles RAG retrieval from Qdrant, and routes all LLM requests to Ollama.
- **Inference & Data** — Ollama serves three LLM models locally with NVIDIA GPU passthrough. Qdrant stores vector embeddings for RAG. n8n provides visual workflow automation — the glue for cross-service logic.
- **Physical World** — Home Assistant (with the companion Matter Server) controls real-world devices over host networking so mDNS/Bonjour discovery works.

Midnight, specifically, talks to a sibling media stack ([HELIOS](https://github.com/pjmarz/HELIOS)) over HTTP APIs — LUMINAL is the brain, HELIOS is the library.

### System Components

<table>
  <thead>
    <tr>
      <th>Category</th>
      <th colspan="2">Service</th>
      <th>Role in the system</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="3"><b>🤖 AI Services</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/n8n.png" width="32" height="32" alt="n8n"></td>
      <td><b><a href="https://github.com/n8n-io/n8n">n8n</a></b></td>
      <td>Visual workflow engine — glues services together for automation</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/open-webui.png" width="32" height="32" alt="OpenWebUI"></td>
      <td><b><a href="https://github.com/open-webui/open-webui">OpenWebUI</a></b></td>
      <td>Chat interface + tool runtime; hosts Midnight, handles RAG</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/ollama.png" width="32" height="32" alt="Ollama"></td>
      <td><b><a href="https://github.com/ollama/ollama">Ollama</a></b></td>
      <td>Local LLM inference server with GPU acceleration</td>
    </tr>
    <tr>
      <td rowspan="2"><b>🧠 AI Infrastructure</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/qdrant.png" width="32" height="32" alt="Qdrant"></td>
      <td><b><a href="https://github.com/qdrant/qdrant">Qdrant</a></b></td>
      <td>Vector DB backing OpenWebUI's retrieval-augmented generation</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/docker.png" width="36" height="24" alt="Docker"></td>
      <td><b><a href="https://www.docker.com/">Docker</a></b></td>
      <td>Containerization + named-volume persistence + GPU passthrough</td>
    </tr>
    <tr>
      <td rowspan="2"><b>🏠 Home Automation</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/home-assistant.png" width="32" height="32" alt="Home Assistant"></td>
      <td><b><a href="https://www.home-assistant.io/">Home Assistant</a></b></td>
      <td>Device control hub — runs on host network for device discovery</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/matter.png" width="32" height="32" alt="Matter Server"></td>
      <td><b><a href="https://github.com/home-assistant-libs/python-matter-server">Matter Server</a></b></td>
      <td>Matter protocol bridge for Home Assistant</td>
    </tr>
    <tr>
      <td rowspan="1"><b>🔐 Security</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/cloudflare.png" width="32" height="32" alt="Cloudflare"></td>
      <td><b><a href="https://www.cloudflare.com/zero-trust/">Cloudflare Access</a></b></td>
      <td>Zero Trust SSO — Google OAuth in front of OpenWebUI</td>
    </tr>
  </tbody>
</table>

## 🧠 AI Models

Three models are pulled automatically on first boot and cached in a persistent volume. Each plays a different role:

- **`llama3.1:8b`** (4.9 GB) — fast, capable general-purpose model for lightweight chat and quick tool calls.
- **`gemma4:e4b`** (9.6 GB) — frontier-level multimodal model with native tool use. Powers Midnight.
- **`gpt-oss:20b`** (~20 GB) — heavier reasoning model when raw capability matters more than latency.

All three run locally on the same Ollama instance with shared GPU access.

## 🌙 Midnight Media Assistant

**Midnight** is a custom AI assistant built on top of OpenWebUI that provides intelligent access to a real media library. It demonstrates prompt engineering, function-tool integration, and RAG working together to produce an assistant that queries live data instead of hallucinating it.

### Architecture

| Component | Description |
|-----------|-------------|
| **Base Model** | gemma4:e4b via Ollama |
| **Interface** | OpenWebUI with custom system prompt |
| **Tools** | 7 Python-based function tools |
| **Knowledge** | RAG-enabled reference documentation |

### Custom Tools (`midnight/`)

| Tool | Purpose |
|------|---------|
| `midnight_plex_tool` | Search library, get recently added, episode details, actor/director search, cast lookup |
| `midnight_radarr_tool` | Movie details, genres, synopses |
| `midnight_sonarr_tool` | TV show details, upcoming episodes |
| `midnight_tautulli_tool` | Watch history, current activity, most watched |
| `midnight_bazarr_tool` | Subtitle status and history |
| `midnight_sabnzbd_tool` | Download queue and history |
| `midnight_overseerr_tool` | Content requests and search |

### Key Features

- **Real-time library queries** — Midnight never guesses; it always calls tools against live APIs
- **Anti-hallucination rules** — explicit prompt engineering prevents made-up titles, dates, or cast
- **Quote normalization** — handles curly quotes and special characters in search terms
- **Episode synopses** — full plot summaries pulled directly from Plex
- **Multi-service integration** — seamless routing across Plex, Radarr, Sonarr, and the rest
- **Date accuracy** — returns the actual "added on" date from Plex, not the file's download timestamp

### Example queries Midnight handles

```
"What movies do we have with Tom Hanks?"
"What's new in the library?"
"What's the Bob's Burgers episode 'It's a Stunterful Life' about?"
"Show me Christmas movies"
"What's currently downloading?"
"Who's watching right now?"
```

See [`midnight/README.md`](midnight/README.md) for full documentation and system prompt.

## 🏗️ Design Decisions

The interesting part of any self-hosted system isn't *what* runs — it's *why* it runs the way it does. These are the decisions that shaped LUMINAL.

### Zero Trust auth via Cloudflare Access

OpenWebUI doesn't manage its own passwords. Cloudflare Access intercepts every request, redirects to Google sign-in, and passes the authenticated email to OpenWebUI via a trusted header (`Cf-Access-Authenticated-User-Email`). OpenWebUI auto-provisions the user from that header. This shifts authentication to an identity provider that already does it well, removes local-password attack surface, and centralizes access policy in Cloudflare's dashboard.

### Docker Secrets over plaintext env vars

All credentials (n8n encryption key, JWT secret, OpenWebUI session key) are mounted into containers as files via Docker Secrets, not exposed as environment variables. `env` listings, process dumps, and compose logs stay clean. The plaintext files live only in a tightly-permissioned system directory, never in the repo.

### Centralized config at `/etc/LUMINAL/` + direnv

Environment variables and secrets live at `/etc/LUMINAL/env.sh` and `/etc/LUMINAL/secrets/` — symlinked into the project root and excluded from git. `direnv` auto-loads this environment whenever the working directory is entered, so interactive shells, cron jobs, and Docker Compose all see the same values without manual sourcing. One source of truth, zero risk of committing secrets, isolated from the repo.

### External named volumes for persistence

Every stateful service (n8n workflows, Ollama model cache, Qdrant indices, OpenWebUI chat history, Home Assistant config) writes to an externally-declared Docker named volume. Containers can be destroyed and recreated without touching data. Migrations and upgrades become routine instead of risky.

### Safe, non-destructive updates via `docker-rebuild.sh`

Rather than `docker compose down && up`, the rebuild script pulls new images first and then uses `docker compose up -d` so only containers whose images actually changed get recreated. Unchanged services stay running. It adds a post-update health check that distinguishes unexpected failures from intentional one-shot init containers (the Ollama model-pullers), retries transient failures, and returns severity-based exit codes (0/1/2) suitable for cron alerting. A dry-run mode lets you see what *would* change without touching anything.

### Anti-hallucination prompt engineering for Midnight

Midnight's system prompt is structured around the assumption that the model *will* hallucinate if allowed to. Every query must go through a tool call — the prompt explicitly forbids answering from model knowledge when a tool is available. Quote normalization handles curly quotes in user input. RAG with `MIDNIGHT_REFERENCE.md` grounds tool selection. The result is an assistant that says "I don't see that in the library" instead of inventing a plausible-sounding fake result.

### GPU passthrough for local inference

Ollama and OpenWebUI both declare NVIDIA GPU reservations in their compose services. Model inference runs at hardware speed with no per-token API cost, no rate limits, and no data leaving the network.

## 📚 Technical Skills Demonstrated

- **Infrastructure & DevOps** — Docker Compose patterns, GPU passthrough, external volume management, safe update tooling, centralized environment/secrets
- **AI & Data Engineering** — local LLM deployment, vector-DB-backed RAG, tool-using agents, anti-hallucination prompt design
- **Security Engineering** — Zero Trust SSO via Cloudflare Access, Docker Secrets, no plaintext credentials, repo-safe configuration
- **Software Integration** — 7 Python function tools against 7 different APIs (Plex, Radarr, Sonarr, Tautulli, Bazarr, SABnzbd, Overseerr)
- **Operational Tooling** — bash automation with health checks, retry logic, severity-based exit codes

## 📜 Technical Evolution

For a version-by-version log of how LUMINAL evolved — including the move to Docker Secrets, the Midnight launch, and the Cloudflare Access migration — see [CHANGELOG.md](./CHANGELOG.md).

---

<div align="center">
  <img src="./docs/media/moon.apng" alt="Moon Logo" width="200">
</div>
