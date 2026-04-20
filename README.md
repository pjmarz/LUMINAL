<div align="center">
  <a href="https://github.com/pjmarz/LUMINAL">
    <img src="./docs/media/LUMINAL.apng" alt="LUMINAL" width="400">
  </a>
</div>

---

> Note: this repo is a showcase of the LUMINAL setup. It's not a turnkey deployment and isn't meant to be cloned and run as-is.

## 🎯 Overview

LUMINAL is a self-hosted AI stack. It runs on a Proxmox VM with an NVIDIA GPU and stitches together workflow automation, local LLM inference, RAG, and smart-home control in one Docker Compose project.

The goal: run a real AI product entirely on self-hosted hardware. Models, auth, data, everything. No hosted inference APIs, no commercial accounts, nothing leaving the network.

Midnight is a custom assistant written on top of OpenWebUI that talks to the [HELIOS](https://github.com/pjmarz/HELIOS) media library through 7 Python tools (Plex, Radarr, Sonarr, Tautulli, Bazarr, SABnzbd, Overseerr). It answers questions by calling live APIs instead of making stuff up.

## 🧩 Architecture

Everything runs as Docker containers on a Proxmox VM. The stack breaks down like this:

- **Auth** — Cloudflare Access sits in front. Google OAuth via trusted headers. No local passwords.
- **Interface** — OpenWebUI is the frontend. It hosts Midnight, does RAG against Qdrant, and sends LLM calls to Ollama.
- **Inference & data** — Ollama runs three local LLMs with GPU passthrough. Qdrant holds the RAG vectors. n8n handles visual workflow automation.
- **Physical world** — Home Assistant plus Matter Server, both on host networking so mDNS device discovery works.

Midnight talks to a separate media stack ([HELIOS](https://github.com/pjmarz/HELIOS)) over HTTP APIs. LUMINAL is the brain, HELIOS is the library.

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
      <td>Visual workflow engine. Glue for cross-service automation.</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/open-webui.png" width="32" height="32" alt="OpenWebUI"></td>
      <td><b><a href="https://github.com/open-webui/open-webui">OpenWebUI</a></b></td>
      <td>Chat interface and tool runtime. Hosts Midnight, handles RAG.</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/ollama.png" width="32" height="32" alt="Ollama"></td>
      <td><b><a href="https://github.com/ollama/ollama">Ollama</a></b></td>
      <td>Local LLM inference with GPU acceleration.</td>
    </tr>
    <tr>
      <td rowspan="2"><b>🧠 AI Infrastructure</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/qdrant.png" width="32" height="32" alt="Qdrant"></td>
      <td><b><a href="https://github.com/qdrant/qdrant">Qdrant</a></b></td>
      <td>Vector DB for OpenWebUI's RAG.</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/docker.png" width="36" height="24" alt="Docker"></td>
      <td><b><a href="https://www.docker.com/">Docker</a></b></td>
      <td>Containers, named volumes, GPU passthrough.</td>
    </tr>
    <tr>
      <td rowspan="2"><b>🏠 Home Automation</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/home-assistant.png" width="32" height="32" alt="Home Assistant"></td>
      <td><b><a href="https://www.home-assistant.io/">Home Assistant</a></b></td>
      <td>Device control hub. Runs on host network for discovery.</td>
    </tr>
    <tr>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/matter.png" width="32" height="32" alt="Matter Server"></td>
      <td><b><a href="https://github.com/home-assistant-libs/python-matter-server">Matter Server</a></b></td>
      <td>Matter protocol bridge for HA.</td>
    </tr>
    <tr>
      <td rowspan="1"><b>🔐 Security</b></td>
      <td align="center"><img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/cloudflare.png" width="32" height="32" alt="Cloudflare"></td>
      <td><b><a href="https://www.cloudflare.com/zero-trust/">Cloudflare Access</a></b></td>
      <td>Zero Trust SSO. Google OAuth in front of OpenWebUI.</td>
    </tr>
  </tbody>
</table>

## 🧠 AI Models

Three models get pulled on first boot and cached on disk. Each does something different:

- `llama3.1:8b` (4.9 GB) — fast general-purpose model. Good for quick chat and simple tool calls.
- `gemma4:e4b` (9.6 GB) — multimodal with native tool use. This is what Midnight runs on.
- `gpt-oss:20b` (~20 GB) — heavier reasoning when capability matters more than latency.

All three share one Ollama instance and one GPU.

## 🌙 Midnight Media Assistant

**Midnight** is a custom AI assistant built on top of OpenWebUI that queries the HELIOS media library. It uses function tools for everything. No question gets answered from what the model "knows" if a tool could answer from live data.

### Setup

| Component | Description |
|-----------|-------------|
| **Base Model** | gemma4:e4b via Ollama |
| **Interface** | OpenWebUI with a custom system prompt |
| **Tools** | 7 Python function tools |
| **Knowledge** | RAG-indexed reference docs |

### Tools (`midnight/`)

| Tool | What it does |
|------|---------|
| `midnight_plex_tool` | Library search, recently added, episode details, cast, actor/director lookup |
| `midnight_radarr_tool` | Movie details, genres, synopses |
| `midnight_sonarr_tool` | TV show details, upcoming episodes |
| `midnight_tautulli_tool` | Watch history, current activity, most watched |
| `midnight_bazarr_tool` | Subtitle status and history |
| `midnight_sabnzbd_tool` | Download queue and history |
| `midnight_overseerr_tool` | Content requests and search |

### How it behaves

- Always calls a tool. Never answers a library question from model knowledge.
- Normalizes curly quotes and special characters before sending to APIs.
- Pulls real episode synopses from Plex instead of guessing plot summaries.
- Returns the actual Plex "added on" date, not the file's download timestamp.
- Says "I don't see that in the library" when something isn't there, instead of inventing a plausible answer.

### Sample prompts

```
"What movies do we have with Tom Hanks?"
"What's new in the library?"
"What's the Bob's Burgers episode 'It's a Stunterful Life' about?"
"Show me Christmas movies"
"What's currently downloading?"
"Who's watching right now?"
```

See [`midnight/README.md`](midnight/README.md) for the full system prompt and tool docs.

## 🏗️ Design Decisions

Why things are set up the way they are.

### Cloudflare Access instead of local accounts

OpenWebUI doesn't have its own login. Cloudflare Access sits in front, redirects to Google, and passes the authenticated email via a trusted header (`Cf-Access-Authenticated-User-Email`). OpenWebUI auto-creates the user from that header. No local passwords to manage, and access policy lives in one place instead of scattered across services.

### Docker Secrets, not env vars

Credentials (n8n encryption key, JWT secret, OpenWebUI session key) are mounted as files via Docker Secrets. They don't show up in `env`, process dumps, or compose logs. The plaintext files live in a locked-down system directory outside the repo.

### Centralized config at `/etc/LUMINAL/`

The real `env.sh` and `secrets/` directory live at `/etc/LUMINAL/`, symlinked into the project and gitignored. `direnv` picks them up on `cd` into the project, so interactive shells, cron jobs, and Docker Compose all see the same values without explicit sourcing. The pattern came after almost committing secrets one too many times.

### External named volumes

Every piece of persistent state (n8n workflows, Ollama model cache, Qdrant indices, chat history, HA config) lives in an external Docker named volume. Containers get torn down and recreated without losing anything. Upgrades stop feeling risky.

### Non-destructive rebuild script

`scripts/docker-rebuild.sh` pulls new images first, then runs `docker compose up -d` so only the services whose images actually changed get recreated. Everything else keeps running. It also runs a health check that skips the one-shot Ollama pullers (they're supposed to exit), retries transient failures, and returns 0/1/2 exit codes so cron can alert properly. `--dry-run` shows what would change without touching anything.

### Anti-hallucination prompt engineering

Midnight's system prompt assumes the model will hallucinate if allowed to. Every question has to go through a tool call. The prompt explicitly bans answering from model knowledge when a tool could answer instead. It normalizes curly quotes in input and uses RAG against `MIDNIGHT_REFERENCE.md` to pick the right tool. Trade-off: Midnight is occasionally too strict and refuses things it could reasonably answer. Better than made-up movie titles.

### GPU passthrough for inference

Ollama and OpenWebUI both reserve an NVIDIA GPU in the compose file. Inference runs at hardware speed. No API costs, no rate limits, nothing leaving the box.

## 📜 Changelog

Version history and evolution in [CHANGELOG.md](./CHANGELOG.md).

---

<div align="center">
  <img src="./docs/media/moon.apng" alt="Moon Logo" width="200">
</div>
