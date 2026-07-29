# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **Closed the LAN admin-spoofing hole on OpenWebUI — for real this time.** 1.6.0 documented a `DOCKER-USER` allowlist as the fix but never deployed it: the chain was empty and `:3000` was published on `0.0.0.0`. Confirmed exploitable from another LAN host — `POST /api/v1/auths/signin` with a forged `Cf-Access-Authenticated-User-Email` returned **HTTP 200 with an admin token**, because `routers/auths.py` reads the email straight out of the header and calls `authenticate_user_by_email` with no source check. That also exposed every plaintext key in `webui.db`. Now closed by `/usr/local/sbin/luminal-firewall.sh` + `luminal-firewall.service` (oneshot, `After=docker.service`, enabled). It matches on `conntrack --ctorigdstport 3000` — the pre-DNAT host port — so the rule survives the container getting a new `172.18.0.x` address, verified across a `docker restart`. Allowlist is charon `192.168.4.172/32` (cloudflared origin) plus `172.16.0.0/12`; everything else is rate-limit-logged and dropped. Validated by temporarily allowlisting glados to prove the RETURN path (200, counters incrementing), then removing it and confirming both glados and virgil time out while `127.0.0.1:3000` still answers. A mirrored `ip6tables` chain is installed as defence-in-depth — v6 is not currently forwarded to the container, so it is inert today.
- **`/var/backups/restic-staging` was world-readable on three hosts.** 0644 files under an all-0755 path chain. Reading the staged `webui.db` **as the `nobody` user** yielded the live Perplexity and Exa API keys, 6 bcrypt password hashes, and a full Immich `pg_dump` defining `public.users`. `restic-pre.sh` now sets `umask 077` and `chmod 0700 "$STAGE"`, and explicitly re-modes the Immich dumps to 0600 — `cp -a` preserves the source's 0644, which `umask` cannot override. Hardened script deployed to dev, glados and virgil (glados/virgil stage `pve-cluster-config.db`); all three re-verified as unreadable by `nobody`. **charon is not reachable by SSH from dev — the same fix still needs applying there.**
- **Qdrant and Ollama are no longer published on `0.0.0.0`.** Both ship without authentication, and the publish covered the LAN *and* the tailnet. Ollama exposed `/api/generate` (compute abuse) plus `/api/pull` and `/api/delete` (model tampering). Both are now `127.0.0.1`-only. In-stack consumers were unaffected (they use docker DNS); Home Assistant runs `network_mode: host` and had its `ollama` config entry repointed from `http://192.168.4.155:11434` to `http://127.0.0.1:11434`. Verified: LAN hosts now fail to connect, loopback and `openwebui -> ollama:11434` both still work.
- **`FORWARDED_ALLOW_IPS` corrected to `192.168.4.172,172.18.0.1`.** It was `172.18.0.1` alone, which is only ever the peer for host-local requests — so the tunnel's `X-Forwarded-*` headers were never trusted. Confirmed empirically that real LAN source IPs arrive un-SNATed (a request from glados logged as `192.168.4.136`), so charon's address is the value that matters.

### Fixed
- **Web search was silently broken.** The live engine was `perplexity` with a **dead key (HTTP 401)**, while `searxng_query_url` sat empty — so the healthy `searxng` service added in 1.6.0 had never actually been used, and compose's `WEB_SEARCH_ENGINE=searxng` was inert PersistentConfig. Switched the live engine to `searxng` and populated its query URL. Verified end-to-end through `POST /api/v1/retrieval/process/web/search`: real results returned and indexed into a fresh collection. Ollama Cloud web search remains configured as an alternative; the dead Perplexity key was left in place rather than deleted.
- **Model pullers would have resurrected the two deleted models.** `ollama-pull-llama` and `ollama-pull-gpt-oss` were still pinned to `llama3.1:8b` and `gpt-oss:20b`, so the next `compose up` would have re-downloaded ~18 GB that was deliberately removed — caught by a `--dry-run` before applying. The chain is now `qwen -> gemma -> embed -> gemma-abliterated`, matching the real model set, with `embeddinggemma:300m` added because `RAG_EMBEDDING_ENGINE=ollama` makes retrieval fail outright without it. Verified the pullers ran as no-ops against the existing models.
- **`webui.url` drift.** Compose set `WEBUI_URL=https://openwebui.welcometomarz.net` but the persisted PersistentConfig value was `""`, so compose was silently ignored. Live value now matches.
- **Home Assistant: disabled the degraded `alexa_devices` integration.** It had been blocking HA bootstrap for ~550,000 s ("Waiting for integrations to complete setup") and failing with `CannotConnect`, running redundantly alongside the working custom `alexa_media`. Its 137 registered entities were referenced by **zero** automations, scripts, scenes, dashboards or config, and all restored states were `unavailable`. Set `disabled_by: user` (reversible from the UI) rather than deleting the entry. Post-restart: zero `alexa_devices` log lines, `alexa_media` still error-free.

### Added
- **Ollama Cloud wired into OpenWebUI.** Added an account-level Ollama Cloud API key (`OLLAMA_CLOUD_API_KEY` in `.env`, now `0600`) and exposed `https://ollama.com/v1` as a second OpenAI-compatible connection, so hosted models appear in the picker next to the local ones under a `cloud.` prefix (`cloud.gpt-oss:120b`, `cloud.nemotron-3-ultra`, …). Same key also populates `web.search.ollama_cloud_api_key`, making Ollama selectable as a web-search engine — set but **not** activated, the live engine is unchanged. Verified end-to-end: `POST /api/chat/completions` with `cloud.gpt-oss:120b` routes through OpenWebUI to ollama.com and returns a completion.
- **Cloud connection pinned to the models this account can actually run.** `ollama.com/v1/models` advertises 19 models but 11 return `403 "this model requires a subscription"` on the free tier (all `kimi-*`, `glm-*`, `deepseek-v4-*`, `qwen3.5:397b`, `mistral-large-3:675b`, `minimax-m2.7`). `openai.api_configs["1"].model_ids` in `webui.db` pins the connection to the 8 that work, so the picker only offers models that respond. Clear `model_ids` to auto-list everything if the account is upgraded.

- **Ollama daemon signed in to cloud (device key).** The daemon cannot use the API key — `ollama serve` exposes no API-key env var and authenticates via the device key at `/root/.ollama/id_ed25519` in `luminal_ollama_storage`. That pubkey is now registered to the account as device "luminal", so the daemon reports `signed in as 'pjmarz_'` and `ollama pull <model>-cloud` works. Verified: pulled `gpt-oss:120b-cloud` (registers a pointer, `SIZE` is `-`, no weights on disk), chatted through `:11434`, got a completion with `ollama ps` empty throughout — no VRAM touched, inference ran on Ollama's hardware.

### Changed
- **Local model set refreshed against measured hardware limits.** Benchmarked everything installed on the RTX 2070 SUPER (8 GB VRAM, 4096 ctx, 120 tok): `gemma4:e4b` 74.4 tok/s @ 3.2 GB 100% GPU, `llama3.1:8b` 68.9 tok/s @ 5.3 GB 100% GPU, `qwen3.5:9b` 58.0 tok/s @ 5.6 GB 100% GPU, `gpt-oss:20b` **8.2 tok/s** @ 14 GB split **53% CPU / 47% GPU**. Cloud for comparison: minimax-m3 60.9, gpt-oss:120b 29.4, nemotron-3-ultra 6.8 tok/s at zero local VRAM.
  - Added `qwen3.5:9b`, removed `llama3.1:8b` — same VRAM tier, but adds vision + thinking on top of tools, against a base model from July 2024. **Caveat below: it is not reliably GPU-resident.**
  - Removed `gpt-oss:20b` (13 GB reclaimed). It never fit: half the weights sat on CPU at 8.2 tok/s. `cloud.gpt-oss:120b` is 6x the parameters at 3.6x the speed for zero local resources.
  - Kept `gemma4:e4b`. Despite being 9.6 GB on disk it loads a ~3.2 GB active slice (nested/MatFormer) and is the fastest model on the box — plus Midnight is built on it.
- **Added `huihui_ai/gemma-4-abliterated:e4b`** (9.6 GB) as the uncensored option, chosen because it inherits gemma4's nested architecture and so loads the same **3.2 GB active slice** — the only abliterated model that keeps real headroom under the ARK GPU contention described below. Clean back-to-back benchmark on a quiet GPU, all four models 100% GPU-resident:

  | Model | tok/s | Loaded |
  |---|---|---|
  | `gemma4:e4b` | 75.0 | 3.2 GB |
  | `huihui_ai/gemma-4-abliterated:e4b` | 74.9 | 3.2 GB |
  | `qwen3.5:9b` | 58.2 | 5.6 GB |
  | `huihui_ai/qwen3.5-abliterated:9b` | 58.4 | 5.6 GB |

  Abliteration costs nothing measurable in throughput or VRAM at either size. **Tool calling survives it** — both gemma4 variants emitted an identical `get_weather{"city":"Boston","unit":"celsius"}` call, so this is not disqualified for Midnight-style pipelines on tool-use grounds. Refusal behaviour does differ as advertised: asked to explain the LAN trusted-header bypass against our *own* OpenWebUI in order to verify the firewall fix, stock `gemma4:e4b` refused outright ("violates the safety guidelines"), while the abliterated build answered the question. `huihui_ai` is the established publisher in this space (460–770K pulls); the long tail of `*-abliterated` uploads on ollama.com has 3-digit pull counts and no provenance.
- **RAG embeddings moved to Ollama.** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, in-process) → `embeddinggemma:300m` (768-dim, 621 MB, on the GPU via Ollama). Reranking stays on `BAAI/bge-reranker-v2-m3` in-process — Ollama exposes no rerank endpoint. The three 384-dim Qdrant collections were snapshotted (`/qdrant/snapshots/`) then dropped so they recreate at the new width; only 295 points were lost, all low-value (262 were ephemeral web-search cache, and 33 were `MIDNIGHT_REFERENCE.md` + 4 images — that doc's embeddings being gone is a feature per 1.5.1). Verified end-to-end via `POST /api/v1/retrieval/process/text`: collection recreated at `dim=768`.

### Backups
- **The Immich originals now have a backup at all — this was the largest unprotected dataset in the lab.** `/mnt/immich/library/upload` (~228 G, irreplaceable) lives on a separate 5 T disk that PVE excludes from vzdump (`scsi2: ...,backup=0`) and that was absent from restic's include list. Only the Immich Postgres dump was protected, i.e. metadata without a single photo. Added the path to `restic-run.sh`'s `dev` includes. It **must** be named explicitly: it is its own filesystem and `--one-file-system` stops traversal crossing into it, so it was unreachable via `/` or `/mnt`. Confirmed by experiment that `--one-file-system` does *not* skip an explicitly-named cross-filesystem target (dry-run against `/mnt/immich/library/profile` on `/dev/sdb1` reported 3 files / 445 KiB would be added). Deliberately excluded `encoded-video` (49 G) and `thumbs` (25 G) — Immich regenerates both. virgil has 2.5 T free on `/mnt/hermes`, so the ~228 G seed fits; it lands on the next nightly 23:00 run.
- **`luminal_qdrant_storage` added to the daily off-host restic includes.** It was previously only in the weekly same-host vzdump.
- Verified while here, and worth recording because it contradicts older notes: **the nightly off-host restic backup is live and healthy** — 23:00 daily, `dev -> sftp:virgil:/mnt/hermes/restic/dev`, seven consecutive snapshots present, with `restic-pre.sh` staging consistent dumps of the hot SQLite DBs first. It is push-driven from charon over SSH, which is why nothing appears in dev's own crontab and why in-VM checks kept concluding "no backups".

### Notes
- **LUMINAL and ARK contend for the same 8 GB GPU — this is the real ceiling on local model size.** `immich_machine_learning` (ARK, `:release-cuda`) holds **~1.15 GB of VRAM** whenever it is working, and for `MACHINE_LEARNING_MODEL_TTL` (Immich default 300s) afterwards; ARK sets no override. Measured effect on `qwen3.5:9b`, same model and prompt: **58.0 tok/s at 100% GPU** with the GPU quiet vs **17.7 tok/s at a 21%/79% CPU/GPU split** with Immich resident — a 3.3x swing depending on whether Immich happens to be indexing photos. A ~9B model at Q4 sits right on the edge of what is left over; `gemma4:e4b` at a 3.2 GB active slice has real headroom and never spills. Treat 9B as "fast when the GPU is quiet", not as a dependable floor. Levers if that matters: run Immich ML on CPU (`MACHINE_LEARNING_DEVICE`), stay at/below the ~3 GB active-weight class, or move Ollama to docker-virgil's RTX 5070 (12 GB, but that is the Plex transcode GPU).
- **A transient DNS blip permanently poisons OpenWebUI's Ollama connection until restart.** `send_get_request` in `routers/ollama.py` uses a process-lifetime shared `aiohttp` session; when one model-list fetch failed with `Cannot connect to host ollama:11434 [Timeout while contacting DNS servers]`, **every** subsequent fetch failed the same way and all local models silently vanished from `/api/models` — leaving only the `cloud.*` connection and custom models, with chat returning `{"detail":"Model not found"}`. `?refresh=true` did not recover it. Meanwhile a fresh `aiohttp` session inside the same container resolved `ollama` in 0.0s, and `socket.getaddrinfo` was fine, so this is the shared session's resolver state, not host DNS (charon answered all probes). `docker restart openwebui` restored all 14 models. Worth knowing because the failure is silent and looks like the models were deleted.

- **Cloud chat models route through the `cloud.*` connection, not `-cloud` tags.** Both paths reach the same models, so the `gpt-oss:120b-cloud` pull used for verification was removed again to keep one obvious route per model. The `cloud.` prefix also stays honest about egress: OpenWebUI labels `-cloud` models `connection_type: local` (they arrive via the Ollama connection), giving no UI signal that the request leaves the network. The device key stays registered for CLI use — `ollama pull`/`run` with a `-cloud` tag, and `ollama push`.
- `OPENAI_API_BASE_URLS` / `OPENAI_API_KEYS` in the compose file are PersistentConfig: OpenWebUI reads them only when the corresponding key is absent from `webui.db` (i.e. on a fresh `openwebui_storage` volume). The live values are the `openai.*` rows in that DB — the compose entries exist so a rebuild-from-empty reproduces this setup.
- Pre-existing drift spotted while working here, **not** changed: `webui.db` has `web.search.engine = "perplexity"` with a real Perplexity key and an empty `web.search.searxng_query_url`, while the compose file still declares `WEB_SEARCH_ENGINE=searxng` + `SEARXNG_QUERY_URL`. The DB wins, so the `searxng` service added in 1.6.0 is currently unused.

## [1.6.0] - 2026-06-07

### Security
- **Documented the OpenWebUI trusted-header exposure.** The container publishes port 3000 on the LAN while trusting `Cf-Access-Authenticated-User-Email`, which OpenWebUI honors regardless of source IP — so a direct hit from the LAN could spoof the header and log in as any user, including admin. Because cloudflared runs on a separate host and reaches OpenWebUI over the network, a loopback bind isn't viable (it 502s the tunnel); the gap is closed instead by restricting port 3000 to the tunnel host at the firewall (a `DOCKER-USER` allowlist, since Docker bypasses ufw). Added `FORWARDED_ALLOW_IPS` as defense-in-depth and corrected the inaccurate v1.2.0 note that claimed "direct IP access disabled when trusted headers configured" — nothing disabled it. Per [OpenWebUI's hardening guidance](https://docs.openwebui.com/getting-started/advanced-topics/hardening/).

### Added
- **SearXNG web-search backend.** Web search was enabled in OpenWebUI but pointed at an engine that didn't exist — there was no SearXNG service and no `SEARXNG_QUERY_URL`, so queries went nowhere. Added a `searxng` service (internal-only, no published port) on `luminal_default`, wired `SEARXNG_QUERY_URL`, and enabled SearXNG's `json` output format (off by default, required by OpenWebUI). New `luminal_searxng_storage` external volume holds its `settings.yml` + secret key. Verified the JSON endpoint returns 200 end-to-end.
- **Container healthchecks across the whole stack + dependency gating.** Added healthchecks to `ollama` (`ollama ps`), `qdrant` (`bash`/`/dev/tcp` — the image ships no `curl`/`wget`/`nc`), `n8n` (`/healthz/readiness`), `searxng` (`/healthz`), `homeassistant` (`curl :8123`), and `matter-server` (`curl :5580`). OpenWebUI's image-baked healthcheck is left intact. The model pullers and OpenWebUI now gate on `condition: service_healthy` / `service_completed_successfully`, replacing the `sleep 3/6/9` readiness hacks with real ordering. `docker-rebuild.sh`'s post-update health check now gets a true signal from every service, not just OpenWebUI.

### Changed
- **OpenWebUI now runs the `:cuda` image.** The previous `:latest` image is CPU-only and silently ignored the GPU reservation in the compose file. The `:cuda` build GPU-accelerates the RAG path (embeddings, reranking, Whisper STT) — verified the container sees the GPU. OpenWebUI still does not run LLM inference; that remains Ollama's job.
- **Web-search env vars renamed** from the deprecated `ENABLE_RAG_WEB_SEARCH` / `RAG_WEB_SEARCH_ENGINE` to the current `ENABLE_WEB_SEARCH` / `WEB_SEARCH_ENGINE`.
- **`env.sh` model pin corrected** from the stale `gemma3:12b` to `gemma4:e4b`, matching `.env` and the documented Midnight base model (a fresh `compose up` from a direnv shell would otherwise have pulled the old model).

### Fixed
- **n8n Execute Command node never actually re-enabled.** The compose used `N8N_NODES_INCLUDE=n8n-nodes-base.executeCommand`, which is not a real n8n variable, and n8n 2.0's default-disabled nodes can't be re-enabled via an include anyway. Replaced with `NODES_EXCLUDE=["n8n-nodes-base.localFileTrigger"]`, which clears Execute Command from the default blocklist while keeping the Local File Trigger node blocked.
- **README accuracy:** OpenWebUI does not run inference (Ollama does); `gpt-oss:20b` is ~13 GB on disk, not ~20 GB. Removed two env vars that no service reads (`LOG_LEVEL`, `HOMEASSISTANT_PORT`).

## [1.5.1] - 2026-05-07

### Fixed
- **Knowledge collection was poisoning Midnight responses.** Live golden-set runs revealed gemma4:e4b was citing example values (literally the "Premium Rush — Dec 13, 2025" line from `MIDNIGHT_REFERENCE.md`) as if they were live library data, instead of calling tools. Even after unbinding the doc from the model's `meta.knowledge`, OpenWebUI's RAG layer continued auto-injecting chunks from the underlying collection. Resolution: deleted the "Midnight Docs" Knowledge collection via `DELETE /api/v1/knowledge/<id>/delete`. Goldenset jumped from 27/38 → 36/38 on identical prompts. The reference doc still lives on disk at [midnight/MIDNIGHT_REFERENCE.md](midnight/MIDNIGHT_REFERENCE.md) for human readers but is no longer fed to the model.
- **`MIDNIGHT_REFERENCE.md` example data sanitized.** Concrete title/date placeholders ("Premium Rush 2012 — Dec 13, 2025", "John Cusack as Jackson Curtis") replaced with `<MOVIE_TITLE>` / `<DATE>` / `<ACTOR_NAME>` shape markers. Header now explicitly warns: "Any concrete value below is a synthetic placeholder. NEVER cite a value from this document as if it came from the user's library."
- **`_goldenset.py` capture gap.** gemma4 in tool-use mode sometimes emits all output via `delta.reasoning_content` instead of `delta.content`. The streaming aggregator now captures both, so reasoning-only responses no longer scored as `nonempty=False`.

### Changed
- **System prompt cleanup**: removed the now-dead "Knowledge retrieval (Native function calling). Call `query_knowledge_files` to retrieve from MIDNIGHT_REFERENCE.md…" paragraph. With the Knowledge collection deleted, that instruction was both useless and risked re-introducing the poisoning behavior if Knowledge was ever re-bound. Source-of-truth at [midnight/README.md](midnight/README.md) now matches what's deployed in OpenWebUI.
- **OpenWebUI model params bumped to v2.1.0 spec via API**: `keep_alive` 5m → 30m, `max_tokens` 2048 → 4096, added `top_k=64`, `top_p=0.95`, `min_p=0.0`. Previously these were documented in the README but not actually applied to the running model.

### Validation
- **Golden set baseline established at 36/38 axes (95%)** across three sequential runs (35, 36, 35). The two persistent failures are both `get_recently_added` queries (#4 "What's new?" and #11 "When was Premium Rush added?") where gemma4:e4b emits a planning trace via `reasoning_content` but never invokes the tool. This is intermittent model behavior, not a Midnight defect — the other 10 prompts execute reliably. Result snapshot committed at [midnight/_goldenset_results.md](midnight/_goldenset_results.md).

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
  - Direct IP access must be blocked at the network layer — the trusted email header is honored regardless of source IP, so the OpenWebUI port is bound to loopback behind the tunnel (corrected in 1.5.x; the original "disabled when trusted headers configured" wording was inaccurate)
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