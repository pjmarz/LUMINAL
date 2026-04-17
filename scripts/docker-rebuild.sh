#!/bin/bash
# ===========================================================================
# DOCKER REBUILD SCRIPT (Safe / Non-Destructive)
# ===========================================================================
# Safely updates Docker Compose services by pulling new images first, then
# recreating only the containers whose images actually changed. No `down`
# command is ever issued — running containers are never torn down wholesale.
#
# Designed for HELIOS and VENUS but works with any project that follows the
# same conventions (_common.sh or standalone mode).
#
# Exit codes:
#   0 — full success (all containers healthy)
#   1 — partial failure (some containers unhealthy/restarting after update)
#   2 — complete failure (pull or up failed entirely)
# ===========================================================================

# ---------------------------------------------------------------------------
# Argument parsing (before sourcing _common.sh so --project-dir is available)
# ---------------------------------------------------------------------------
PROJECT_DIR=""
SKIP_PRUNE=false
SKIP_HEALTH_CHECK=false
DRY_RUN=false

usage() {
    echo "Usage: $(basename "$0") [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --project-dir DIR    Project root containing docker-compose.yml"
    echo "                       (default: auto-detected from _common.sh)"
    echo "  --skip-prune         Skip dangling image prune after update"
    echo "  --skip-health-check  Skip the post-update health check"
    echo "  --dry-run            Pull images but do not run 'up' or prune"
    echo "  -h, --help           Show this help message"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --project-dir)
            PROJECT_DIR="$2"
            shift 2
            ;;
        --skip-prune)
            SKIP_PRUNE=true
            shift
            ;;
        --skip-health-check)
            SKIP_HEALTH_CHECK=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Source _common.sh (provides log(), HELIOS_ROOT, LOG_FILE, set -euo pipefail)
# We need HELIOS_NO_ERREXIT because we handle errors ourselves with explicit
# return-code checks — set -e would kill us on the first non-zero.
# ---------------------------------------------------------------------------
HELIOS_NO_ERREXIT=1
HELIOS_START_MSG="Docker Rebuild Script Start (safe mode)"

# _common.sh lives alongside this script in the scripts/ directory.
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${_SCRIPT_DIR}/_common.sh" ]]; then
    source "${_SCRIPT_DIR}/_common.sh"
else
    # Fallback: minimal logging if _common.sh is not available (e.g. testing)
    log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $*"; }
    HELIOS_ROOT="$(cd "${_SCRIPT_DIR}/.." && pwd)"
    LOG_FILE="/dev/null"
fi

# Resolve the effective project directory
if [[ -n "$PROJECT_DIR" ]]; then
    EFFECTIVE_PROJECT_DIR="$PROJECT_DIR"
else
    EFFECTIVE_PROJECT_DIR="$HELIOS_ROOT"
fi

# Validate compose file exists
if [[ ! -f "${EFFECTIVE_PROJECT_DIR}/docker-compose.yml" ]] && \
   [[ ! -f "${EFFECTIVE_PROJECT_DIR}/compose.yml" ]] && \
   [[ ! -f "${EFFECTIVE_PROJECT_DIR}/compose.yaml" ]]; then
    log "ERROR: No docker-compose.yml found in ${EFFECTIVE_PROJECT_DIR}"
    exit 2
fi

PROJECT_NAME="$(basename "$EFFECTIVE_PROJECT_DIR")"
log "Project: ${PROJECT_NAME}"
log "Project root: ${EFFECTIVE_PROJECT_DIR}"
log "Dry run: ${DRY_RUN}"

# ---------------------------------------------------------------------------
# GPU container timeout — NVIDIA GPU containers (plex-helios, plex-venus) can
# take a long time to stop due to NVENC session cleanup. The default 10s
# compose timeout is too short and causes SIGKILL → corrupted transcodes.
# ---------------------------------------------------------------------------
export COMPOSE_HTTP_TIMEOUT=120

# Track overall result
EXIT_CODE=0

# ---------------------------------------------------------------------------
# ensure_external_networks — creates shared Docker networks if missing.
# These are referenced as `external: true` in compose files.
# ---------------------------------------------------------------------------
ensure_external_networks() {
    log "Ensuring required external networks exist..."

    local networks=("helios_proxy" "helios_console_agent_network")

    for net in "${networks[@]}"; do
        if ! docker network inspect "$net" &>/dev/null; then
            log "Creating missing network: ${net}"
            if docker network create "$net" >> "$LOG_FILE" 2>&1; then
                log "Created network: ${net}"
            else
                log "WARNING: Failed to create network: ${net}"
            fi
        else
            log "Network exists: ${net}"
        fi
    done
}

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# regenerate_nvidia_cdi — regenerate NVIDIA CDI specs if nvidia-ctk is present.
# Driver updates can change library paths (e.g., libnvidia-egl-wayland) which
# invalidates the cached CDI specs, causing GPU containers to fail to start.
# ---------------------------------------------------------------------------
regenerate_nvidia_cdi() {
    if ! command -v nvidia-ctk &>/dev/null; then
        log "nvidia-ctk not found — skipping CDI regeneration"
        return 0
    fi

    log "Regenerating NVIDIA CDI specs..."

    local cdi_dirs=("/etc/cdi" "/var/run/cdi")
    local regenerated=0

    for dir in "${cdi_dirs[@]}"; do
        if [[ -f "${dir}/nvidia.yaml" ]]; then
            if nvidia-ctk cdi generate --output "${dir}/nvidia.yaml" >> "$LOG_FILE" 2>&1; then
                log "Regenerated CDI spec: ${dir}/nvidia.yaml"
                ((regenerated++))
            else
                log "WARNING: Failed to regenerate CDI spec: ${dir}/nvidia.yaml"
            fi
        fi
    done

    if [[ $regenerated -gt 0 ]]; then
        log "Regenerated ${regenerated} CDI spec(s)"
    else
        log "No CDI specs found to regenerate"
    fi
}

# capture_status — log current container state via `docker compose ps`
# ---------------------------------------------------------------------------
capture_status() {
    local label="$1"
    log "--- Container status (${label}) ---"
    docker compose ps 2>&1 | tee -a "$LOG_FILE"
    log "--- End status (${label}) ---"
}

# ---------------------------------------------------------------------------
# pull_images — pull latest images for all services.
# This happens BEFORE any containers are touched so a pull failure is safe.
# ---------------------------------------------------------------------------
pull_images() {
    log "Pulling latest images for all services..."

    if docker compose pull 2>&1 | tee -a "$LOG_FILE"; then
        log "Image pull completed successfully"
        return 0
    else
        log "ERROR: Image pull failed"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# recreate_services — `docker compose up -d --remove-orphans --timeout 30`
# Compose will diff running containers against pulled images and only
# stop/recreate containers whose image (or config) has changed. Containers
# that are already up-to-date are left running — zero downtime for them.
#
# Retries up to 3 times with 15s delay between attempts to handle transient
# failures (e.g., containers stuck in D-state / unkillable kernel sleep).
# ---------------------------------------------------------------------------
recreate_services() {
    log "Recreating services (only changed containers will restart)..."

    local max_attempts=3
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if [[ $attempt -gt 1 ]]; then
            log "Retry attempt ${attempt}/${max_attempts} — waiting 15s before retry..."
            sleep 15
        fi

        log "Service recreation attempt ${attempt}/${max_attempts}..."
        if docker compose up -d --remove-orphans --timeout 30 2>&1 | tee -a "$LOG_FILE"; then
            log "Service recreation completed successfully (attempt ${attempt}/${max_attempts})"
            return 0
        else
            log "WARNING: Service recreation attempt ${attempt}/${max_attempts} failed"
        fi

        ((attempt++))
    done

    log "ERROR: Service recreation failed after ${max_attempts} attempts"
    return 1
}

# ---------------------------------------------------------------------------
# health_check — wait, then inspect for unhealthy / restarting containers.
# Returns 0 if all healthy, 1 if any problems found.
# ---------------------------------------------------------------------------
health_check() {
    local wait_seconds=15
    log "Waiting ${wait_seconds}s for containers to stabilize..."
    sleep "$wait_seconds"

    log "Running post-update health check..."

    local problems=0

    # Check for containers in unhealthy state
    local unhealthy
    unhealthy=$(docker compose ps --format json 2>/dev/null \
        | jq -r 'select(.Health == "unhealthy") | .Name' 2>/dev/null || true)

    if [[ -n "$unhealthy" ]]; then
        log "WARNING: Unhealthy containers detected:"
        while IFS= read -r name; do
            log "  - ${name} (unhealthy)"
            ((problems++))
        done <<< "$unhealthy"
    fi

    # Check for containers in restarting state
    local restarting
    restarting=$(docker compose ps --format json 2>/dev/null \
        | jq -r 'select(.State == "restarting") | .Name' 2>/dev/null || true)

    if [[ -n "$restarting" ]]; then
        log "WARNING: Restarting containers detected:"
        while IFS= read -r name; do
            log "  - ${name} (restarting)"
            ((problems++))
        done <<< "$restarting"
    fi

    # Check for containers that exited (should be running)
    local exited
    exited=$(docker compose ps --format json 2>/dev/null \
        | jq -r 'select(.State == "exited") | .Name' 2>/dev/null || true)

    if [[ -n "$exited" ]]; then
        log "WARNING: Exited containers detected:"
        while IFS= read -r name; do
            log "  - ${name} (exited)"
            ((problems++))
        done <<< "$exited"
    fi

    if [[ "$problems" -eq 0 ]]; then
        log "Health check passed — all containers running"
        return 0
    else
        log "Health check found ${problems} problem(s)"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# prune_dangling — remove only dangling (untagged) images.
# Specifically NOT using `docker image prune -a` which would remove cached
# layers and base images not currently in use, making future pulls slower.
# ---------------------------------------------------------------------------
prune_dangling() {
    log "Pruning dangling (untagged) images..."

    local output
    output=$(docker image prune -f 2>&1)
    local rc=$?
    echo "$output" | tee -a "$LOG_FILE"

    if [[ $rc -eq 0 ]]; then
        local reclaimed
        reclaimed=$(echo "$output" | grep -oP 'Total reclaimed space: \K.*' || echo "0B")
        log "Prune complete — reclaimed ${reclaimed}"
    else
        log "WARNING: Image prune failed (exit code ${rc})"
    fi
}

# ---------------------------------------------------------------------------
# check_plex_update — checks if Plex Media Server has an internal update
# available (separate from the Docker image). If the running version differs
# from the latest available version (PlexPass beta channel if token exists,
# public channel otherwise), restarts the container so the LinuxServer
# entrypoint pulls and installs the new version on boot.
#
# Only runs if a container named "plex*" exists in the current project.
# ---------------------------------------------------------------------------
check_plex_update() {
    log "Checking for Plex internal updates..."

    local plex_containers
    plex_containers=$(docker compose ps --format json 2>/dev/null \
        | jq -r 'select(.Name | test("plex"; "i")) | .Name' 2>/dev/null || true)

    if [[ -z "$plex_containers" ]]; then
        log "No Plex containers in this project — skipping"
        return 0
    fi

    while IFS= read -r container; do
        [[ -z "$container" ]] && continue

        # Skip non-Plex-server containers (e.g., plexautolanguages)
        local host_port
        host_port=$(docker port "$container" 32400/tcp 2>/dev/null | head -1 | cut -d: -f2 || true)
        if [[ -z "$host_port" ]]; then
            log "${container}: not a Plex server (no port 32400) — skipping"
            continue
        fi

        # Check if container uses VERSION=docker (purely image-driven, skip)
        local version_env
        version_env=$(docker exec "$container" printenv VERSION 2>/dev/null || true)
        if [[ "$version_env" == "docker" ]]; then
            log "${container}: VERSION=docker (image-only updates) — skipping internal check"
            continue
        fi

        # Get current running version
        local current_version
        current_version=$(curl -sf "http://localhost:${host_port}/identity" 2>/dev/null \
            | grep -oP 'version="\K[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+-[^"]+' || true)

        if [[ -z "$current_version" ]]; then
            log "WARNING: Cannot reach Plex on port ${host_port} for ${container} — skipping"
            continue
        fi

        # Get Plex token to check PlexPass beta channel
        local plex_token
        plex_token=$(docker exec "$container" grep -oP 'PlexOnlineToken="\K[^"]+' \
            "/config/Library/Application Support/Plex Media Server/Preferences.xml" 2>/dev/null || true)

        # Check both public and PlexPass channels
        local latest_version download_url channel_name

        if [[ -n "$plex_token" ]]; then
            download_url="https://plex.tv/api/downloads/5.json?channel=plexpass&X-Plex-Token=${plex_token}"
            latest_version=$(curl -sf "$download_url" 2>/dev/null \
                | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['computer']['Linux']['version'])" 2>/dev/null || true)
            channel_name="PlexPass"
        fi

        if [[ -z "$latest_version" ]]; then
            download_url="https://plex.tv/api/downloads/5.json"
            latest_version=$(curl -sf "$download_url" 2>/dev/null \
                | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['computer']['Linux']['version'])" 2>/dev/null || true)
            channel_name="public"
        fi

        if [[ -z "$latest_version" ]]; then
            log "WARNING: Cannot fetch latest Plex version — skipping ${container}"
            continue
        fi

        log "${container}: running=${current_version} latest=${latest_version} (${channel_name})"

        if [[ "$current_version" == "$latest_version" ]]; then
            log "${container}: Plex is up to date"
        else
            log "${container}: Plex update available — restarting to apply..."
            if docker restart "$container" >> "$LOG_FILE" 2>&1; then
                local wait=60
                log "Waiting ${wait}s for ${container} to apply update and restart..."
                sleep "$wait"

                local new_version
                new_version=$(curl -sf "http://localhost:${host_port}/identity" 2>/dev/null \
                    | grep -oP 'version="\K[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+-[^"]+' || true)

                if [[ "$new_version" == "$latest_version" ]]; then
                    log "${container}: Updated successfully (${current_version} -> ${new_version})"
                elif [[ -n "$new_version" && "$new_version" != "$current_version" ]]; then
                    log "${container}: Updated (${current_version} -> ${new_version}) — differs from expected ${latest_version} (channel mismatch, OK)"
                elif [[ -n "$new_version" ]]; then
                    log "WARNING: ${container} restarted but version unchanged at ${new_version}"
                else
                    log "WARNING: ${container} not responding after restart — may still be starting"
                fi
            else
                log "ERROR: Failed to restart ${container}"
            fi
        fi
    done <<< "$plex_containers"
}

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------
log "Starting safe rebuild for ${PROJECT_NAME}..."

cd "$EFFECTIVE_PROJECT_DIR" || {
    log "ERROR: Cannot cd to ${EFFECTIVE_PROJECT_DIR}"
    exit 2
}

# Step 1: Ensure external networks
ensure_external_networks

# Step 1.5: Regenerate NVIDIA CDI specs (prevents stale lib path errors after driver updates)
regenerate_nvidia_cdi

# Step 2: Capture pre-update status
capture_status "BEFORE"

# Step 3: Pull images (safe — doesn't touch running containers)
if ! pull_images; then
    log "FATAL: Pull failed — no containers were touched. Aborting."
    exit 2
fi

# Step 4: Dry-run stops here
if [[ "$DRY_RUN" == "true" ]]; then
    log "Dry run — skipping service recreation and prune"
    log "Images have been pulled. Run without --dry-run to apply."
    exit 0
fi

# Step 5: Recreate services (only changed containers restart)
# On failure: downgrade to partial failure and let health check assess damage.
# D-state containers may cause transient compose failures even after retries;
# the actual container state may still be acceptable.
if ! recreate_services; then
    log "WARNING: Service recreation failed after retries — continuing to health check"
    capture_status "AFTER (recreation failed)"
    EXIT_CODE=1
fi

# Step 6: Post-update status
capture_status "AFTER"

# Step 7: Health check
if [[ "$SKIP_HEALTH_CHECK" != "true" ]]; then
    if ! health_check; then
        if [[ $EXIT_CODE -eq 0 ]]; then
            EXIT_CODE=1
        fi
        log "Some containers have issues — review above warnings"
    fi

    # Severity assessment: if recreation failed, check whether the damage is
    # widespread (more than half of containers not running → exit 2) or
    # contained (majority running → stay at exit 1).
    if [[ $EXIT_CODE -ge 1 ]]; then
        total_containers=$(docker compose ps -a --format json 2>/dev/null | jq -r '.Name' 2>/dev/null | wc -l || echo 0)
        running_containers=$(docker compose ps --format json 2>/dev/null \
            | jq -r 'select(.State == "running") | .Name' 2>/dev/null | wc -l || echo 0)

        if [[ $total_containers -gt 0 ]]; then
            failed_containers=$((total_containers - running_containers))
            half=$(( (total_containers + 1) / 2 ))  # ceiling division
            log "Severity assessment: ${running_containers}/${total_containers} containers running (${failed_containers} down)"

            if [[ $failed_containers -ge $half ]]; then
                log "FATAL: ${failed_containers}/${total_containers} containers down — escalating to complete failure (exit 2)"
                EXIT_CODE=2
            else
                log "Majority of containers running (${running_containers}/${total_containers}) — partial failure (exit 1)"
                EXIT_CODE=1
            fi
        fi
    fi
else
    log "Health check skipped (--skip-health-check)"
fi

# Step 7.5: Check for Plex internal updates (only on success)
if [[ $EXIT_CODE -eq 0 ]]; then
    check_plex_update
fi

# Step 8: Prune dangling images (only on success)
if [[ "$SKIP_PRUNE" != "true" ]] && [[ $EXIT_CODE -eq 0 ]]; then
    prune_dangling
elif [[ "$SKIP_PRUNE" == "true" ]]; then
    log "Prune skipped (--skip-prune)"
else
    log "Prune skipped — not pruning after partial failure"
fi

# Step 9: Disk usage summary
log "Docker disk usage:"
docker system df 2>&1 | tee -a "$LOG_FILE"

# Final summary
if [[ $EXIT_CODE -eq 0 ]]; then
    log "Rebuild complete — all services healthy"
elif [[ $EXIT_CODE -eq 1 ]]; then
    log "Rebuild complete with warnings — exit code ${EXIT_CODE}"
else
    log "Rebuild FAILED — exit code ${EXIT_CODE}"
fi

exit $EXIT_CODE
