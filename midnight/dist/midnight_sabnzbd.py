"""
title: Midnight SABnzbd Tool
author: Peter Marino
description: Download queue and history via SABnzbd for Midnight
required_open_webui_version: 0.4.0
requirements: httpx, pydantic
version: 2.1.0
licence: MIT
"""

from typing import Optional
from pydantic import BaseModel, Field

# === BEGIN inlined from midnight/_shared.py — DO NOT EDIT, regenerate via build_tools.py ===
from difflib import SequenceMatcher

import httpx


async def http_get_json(
    url: str,
    *,
    headers: dict = None,
    params: dict = None,
    timeout: float = 30.0,
) -> dict:
    """Async GET that returns parsed JSON. Raises on transport/HTTP error.

    Per-call AsyncClient is the simple choice — slight overhead vs a
    long-lived client, but no lifecycle management. For methods that fan out
    to multiple endpoints, dispatch with asyncio.gather() to parallelize.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


async def http_post_json(
    url: str,
    *,
    headers: dict = None,
    json: dict = None,
    timeout: float = 30.0,
) -> dict:
    """Async POST with JSON body. Returns parsed JSON. Raises on error."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=json)
        response.raise_for_status()
        return response.json()


def fuzzy_match(query: str, candidates: list, threshold: float = 0.6) -> list:
    """
    Find fuzzy matches for a query in a list of candidates. Typo-tolerant.

    :param query: Search query (potentially misspelled)
    :param candidates: List of (name, data) tuples to match against
    :param threshold: Minimum similarity ratio (0.0 to 1.0)
    :return: List of matching (name, data, score) tuples, sorted by score desc
    """
    query_lower = query.lower()
    matches = []
    for name, data in candidates:
        name_lower = name.lower()
        # Substring match in either direction scores 1.0
        if query_lower in name_lower or name_lower in query_lower:
            matches.append((name, data, 1.0))
        else:
            ratio = SequenceMatcher(None, query_lower, name_lower).ratio()
            if ratio >= threshold:
                matches.append((name, data, ratio))
    return sorted(matches, key=lambda x: x[2], reverse=True)


async def emit_status(emitter, description: str, done: bool = False) -> None:
    """
    Send an OpenWebUI status event if an emitter is wired.

    Always pair a `done=False` open with a `done=True` close (use try/finally)
    or the OpenWebUI shimmer animation will hang.

    :param emitter: __event_emitter__ injected by OpenWebUI, or None
    :param description: Status text shown to the user
    :param done: True when the operation has finished (success OR failure)
    """
    if emitter:
        await emitter({
            "type": "status",
            "data": {"description": description, "done": done},
        })
# === END inlined from midnight/_shared.py ===



class Tools:
    """SABnzbd download management tools for Midnight."""

    class Valves(BaseModel):
        """Configuration for SABnzbd API connection."""
        SABNZBD_URL: str = Field(
            default="http://192.168.4.46:8080",
            description="SABnzbd server URL"
        )
        SABNZBD_API_KEY: str = Field(
            default="",
            description="SABnzbd API key"
        )

    def __init__(self):
        self.valves = self.Valves()

    async def _api_call(self, mode: str, params: dict = None) -> dict:
        """Make SABnzbd API call. Raises on transport/HTTP error."""
        all_params = {
            "apikey": self.valves.SABNZBD_API_KEY,
            "mode": mode,
            "output": "json"
        }
        if params:
            all_params.update(params)

        return await http_get_json(
            f"{self.valves.SABNZBD_URL}/api",
            params=all_params,
        )

    async def get_download_queue(self, __event_emitter__=None) -> str:
        """
        Get current download queue from SABnzbd.
        Use this when users ask about pending downloads, what's downloading, or queue status.

        :return: Current download queue with progress
        """
        await emit_status(__event_emitter__, "Fetching SABnzbd queue…")
        try:
            data = await self._api_call("queue")
        except Exception as e:
            await emit_status(__event_emitter__, "SABnzbd unreachable", done=True)
            return f"SABnzbd error: {e}"

        queue = data.get("queue", {})
        slots = queue.get("slots", [])
        speed = queue.get("speed", "0")
        timeleft = queue.get("timeleft", "0:00:00")
        paused = queue.get("paused", False)

        if not slots:
            status = "⏸️ Paused" if paused else "💤 Idle"
            return f"Download queue is empty. Status: {status}"

        status_icon = "⏸️" if paused else "⬇️"
        result = f"{status_icon} **{len(slots)} item(s) in queue** | Speed: {speed}/s | ETA: {timeleft}\n\n"

        for slot in slots[:10]:
            filename = slot.get("filename", "Unknown")
            percentage = slot.get("percentage", "0")
            size = slot.get("size", "0 MB")
            timeleft = slot.get("timeleft", "Unknown")
            status = slot.get("status", "Unknown")
            
            # Make filename readable
            display_name = filename[:50] + "..." if len(filename) > 50 else filename
            
            if status == "Downloading":
                result += f"⬇️ **{display_name}**\n"
                result += f"   {percentage}% of {size} | ETA: {timeleft}\n"
            else:
                result += f"⏳ **{display_name}** - {status}\n"
                result += f"   {size}\n"

        if len(slots) > 10:
            result += f"\n... and {len(slots) - 10} more items in queue."

        await emit_status(__event_emitter__, f"{len(slots)} item(s) in queue", done=True)
        return result

    async def get_download_history(self, count: int = 15, __event_emitter__=None) -> str:
        """
        Get recent download history from SABnzbd.
        Use this when users ask about completed downloads or what was downloaded.

        :param count: Number of history items to show (default 15)
        :return: Recent download history
        """
        await emit_status(__event_emitter__, "Fetching SABnzbd download history…")
        try:
            data = await self._api_call("history", {"limit": count})
        except Exception as e:
            return f"SABnzbd error: {e}"

        history = data.get("history", {})
        slots = history.get("slots", [])

        if not slots:
            return "No download history available."

        result = "Recent downloads:\n\n"

        from datetime import datetime
        for slot in slots:
            name = slot.get("name", "Unknown")
            status = slot.get("status", "Unknown")
            size = slot.get("size", "0 MB")
            completed = slot.get("completed", 0)

            try:
                completed_date = datetime.fromtimestamp(completed).strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError, OSError):
                completed_date = "unknown date"
            
            # Truncate long names
            display_name = name[:45] + "..." if len(name) > 45 else name
            
            if status == "Completed":
                result += f"✓ **{display_name}**\n"
                result += f"   {size} | Completed: {completed_date}\n"
            elif status == "Failed":
                result += f"✗ **{display_name}** - Failed\n"
            else:
                result += f"? **{display_name}** - {status}\n"

        return result
