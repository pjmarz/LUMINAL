"""
title: Midnight Seerr Tool
author: Peter Marino
description: Media request management via Seerr (formerly Overseerr) for Midnight
required_open_webui_version: 0.4.0
requirements: httpx, pydantic
version: 2.1.0
licence: MIT
"""

from typing import Optional
from urllib.parse import quote
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



def _user_auto_approve(user: dict) -> bool:
    """Read AUTO_APPROVE from a user's UserValves dict-or-Pydantic-model."""
    if not user:
        return False
    valves = user.get("valves") if isinstance(user, dict) else None
    if valves is None:
        return False
    if hasattr(valves, "AUTO_APPROVE"):
        return bool(valves.AUTO_APPROVE)
    if isinstance(valves, dict):
        return bool(valves.get("AUTO_APPROVE", False))
    return False


class Tools:
    """Seerr media request management tools for Midnight (Seerr was formerly Overseerr)."""

    class Valves(BaseModel):
        """Configuration for Seerr API connection."""
        SEERR_URL: str = Field(
            default="http://192.168.4.46:5055",
            description="Seerr server URL"
        )
        SEERR_API_KEY: str = Field(
            default="",
            description="Seerr API key"
        )

    class UserValves(BaseModel):
        """Per-user preferences (set in OpenWebUI Account → Tools)."""
        AUTO_APPROVE: bool = Field(
            default=False,
            description="Submit requests with isAutoApproved=true. Seerr respects this only if the user has the auto-approve permission server-side.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self._title_cache: dict = {}  # (media_type, tmdb_id) -> title

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            "X-Api-Key": self.valves.SEERR_API_KEY,
            "Content-Type": "application/json"
        }

    async def _lookup_title(self, media_type: str, tmdb_id: int) -> Optional[str]:
        """Look up a title for a (media_type, tmdb_id) pair, caching across calls.

        Returns None on lookup failure rather than raising — partial result
        ("Unknown") is preferable to failing the whole listing.
        """
        key = (media_type, tmdb_id)
        if key in self._title_cache:
            return self._title_cache[key]
        try:
            if media_type == "movie":
                details = await self._make_request(f"/movie/{tmdb_id}")
                title = details.get("title")
            else:
                details = await self._make_request(f"/tv/{tmdb_id}")
                title = details.get("name")
        except Exception:
            return None
        if title:
            self._title_cache[key] = title
        return title

    async def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        """Make API request to Seerr. Raises on transport/HTTP error."""
        url = f"{self.valves.SEERR_URL}/api/v1{endpoint}"
        if method == "GET":
            return await http_get_json(url, headers=self._get_headers())
        elif method == "POST":
            return await http_post_json(url, headers=self._get_headers(), json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    async def search_to_request(self, query: str, __event_emitter__=None) -> str:
        """
        Search for movies or TV shows that can be requested.
        Use this when users want to request new content not in the library.

        :param query: Movie or TV show title to search for
        :return: List of results that can be requested
        """
        await emit_status(__event_emitter__, f"Searching Seerr for '{query}'…")
        try:
            data = await self._make_request(f"/search?query={quote(query)}&page=1")
        except Exception as e:
            await emit_status(__event_emitter__, "Seerr unreachable", done=True)
            return f"Seerr error: {e}"

        results = data.get("results", [])
        if not results:
            return f"No results found for '{query}' in Seerr."
        
        output = f"Search results for '{query}':\n\n"
        
        for item in results[:10]:
            media_type = item.get("mediaType", "unknown")
            title = item.get("title") or item.get("name", "Unknown")
            year = item.get("releaseDate", "")[:4] if item.get("releaseDate") else ""
            year = year or (item.get("firstAirDate", "")[:4] if item.get("firstAirDate") else "N/A")
            
            # Check request status
            media_info = item.get("mediaInfo")
            if media_info:
                status = media_info.get("status", 0)
                status_map = {
                    1: "🟡 Pending",
                    2: "🟢 Processing", 
                    3: "⚠️ Partially Available",
                    4: "⚠️ Partially Available",
                    5: "✅ Available"
                }
                status_str = status_map.get(status, "❓ Unknown")
            else:
                status_str = "📥 Can Request"
            
            type_emoji = "🎬" if media_type == "movie" else "📺"
            tmdb_id = item.get("id", "")
            
            output += f"{type_emoji} **{title}** ({year}) - {status_str}\n"
            output += f"   ID: {tmdb_id} | Type: {media_type}\n"
        
        output += "\n*To request, use: request_movie(tmdb_id) or request_tv(tmdb_id)*"
        await emit_status(__event_emitter__, f"Found {len(results)} result(s)", done=True)
        return output

    async def request_movie(self, tmdb_id: int, __user__: dict = None, __event_emitter__=None) -> str:
        """
        Request a movie to be added to the library.
        Use the TMDb ID from search results.
        If the user has AUTO_APPROVE=true in UserValves AND the auto-approve
        permission server-side, the request is submitted as auto-approved.

        :param tmdb_id: The Movie Database ID for the movie
        :param __user__: OpenWebUI user context (auto-injected). Used for AUTO_APPROVE.
        :return: Request status message
        """
        await emit_status(__event_emitter__, f"Submitting movie request (TMDb #{tmdb_id})…")
        payload = {"mediaType": "movie", "mediaId": tmdb_id}
        if _user_auto_approve(__user__):
            payload["isAutoApproved"] = True

        try:
            data = await self._make_request("/request", method="POST", data=payload)
        except Exception as e:
            return f"Seerr error requesting movie: {e}"

        if data.get("id"):
            return f"✅ Movie request submitted successfully! Request ID: {data['id']}"

        return f"Request submitted but no request ID returned. Raw response: {data}"

    async def request_tv(self, tmdb_id: int, seasons: str = "all", __user__: dict = None, __event_emitter__=None) -> str:
        """
        Request a TV show to be added to the library.
        Use the TMDb ID from search results.
        If the user has AUTO_APPROVE=true in UserValves AND the auto-approve
        permission server-side, the request is submitted as auto-approved.

        :param tmdb_id: The Movie Database ID for the TV show
        :param seasons: Which seasons to request - "all" or comma-separated numbers like "1,2,3"
        :param __user__: OpenWebUI user context (auto-injected). Used for AUTO_APPROVE.
        :return: Request status message
        """
        await emit_status(__event_emitter__, f"Submitting TV request (TMDb #{tmdb_id})…")
        # First get show details to know available seasons
        try:
            show_data = await self._make_request(f"/tv/{tmdb_id}")
        except Exception as e:
            return f"Seerr error fetching show details: {e}"

        # Build seasons request
        if seasons.lower() == "all":
            season_list = [{"seasonNumber": s.get("seasonNumber")}
                          for s in show_data.get("seasons", [])
                          if s.get("seasonNumber", 0) > 0]
        else:
            try:
                season_nums = [int(s.strip()) for s in seasons.split(",")]
                season_list = [{"seasonNumber": n} for n in season_nums]
            except ValueError:
                return "Invalid seasons format. Use 'all' or comma-separated numbers like '1,2,3'"

        payload = {"mediaType": "tv", "mediaId": tmdb_id, "seasons": season_list}
        if _user_auto_approve(__user__):
            payload["isAutoApproved"] = True

        try:
            data = await self._make_request("/request", method="POST", data=payload)
        except Exception as e:
            return f"Seerr error requesting TV show: {e}"

        if data.get("id"):
            return f"✅ TV show request submitted successfully! Request ID: {data['id']}"

        return f"Request submitted but no request ID returned. Raw response: {data}"

    async def get_pending_requests(self, __event_emitter__=None) -> str:
        """
        Get all pending media requests.
        Use this to see what has been requested but not yet fulfilled.

        :return: List of pending requests
        """
        await emit_status(__event_emitter__, "Fetching pending Seerr requests…")
        try:
            data = await self._make_request("/request?take=20&skip=0&filter=pending")
        except Exception as e:
            return f"Seerr error: {e}"

        results = data.get("results", [])
        if not results:
            return "No pending requests."

        output = f"**Pending Requests ({len(results)}):**\n\n"

        for req in results:
            media = req.get("media", {})
            media_type = req.get("type", "unknown")
            type_emoji = "🎬" if media_type == "movie" else "📺"

            tmdb_id = media.get("tmdbId")
            title = await self._lookup_title(media_type, tmdb_id) if tmdb_id else None
            if not title:
                title = "Unknown"
            
            requested_by = req.get("requestedBy", {}).get("displayName", "Unknown")
            created = req.get("createdAt", "")[:10] if req.get("createdAt") else "N/A"
            
            status = req.get("status", 0)
            status_map = {1: "🟡 Pending", 2: "✅ Approved", 3: "❌ Declined"}
            status_str = status_map.get(status, "❓ Unknown")
            
            output += f"{type_emoji} **{title}** - {status_str}\n"
            output += f"   Requested by: {requested_by} on {created}\n"
        
        return output

    async def get_recent_requests(self, count: int = 10, __event_emitter__=None) -> str:
        """
        Get recent media requests (approved, pending, or declined).
        Use this to see request history.

        :param count: Number of requests to fetch (default 10)
        :return: List of recent requests
        """
        await emit_status(__event_emitter__, f"Fetching last {count} Seerr requests…")
        try:
            data = await self._make_request(f"/request?take={count}&skip=0")
        except Exception as e:
            return f"Seerr error: {e}"

        results = data.get("results", [])
        if not results:
            return "No requests found."

        output = f"**Recent Requests ({len(results)}):**\n\n"

        for req in results:
            media = req.get("media", {})
            media_type = req.get("type", "unknown")
            type_emoji = "🎬" if media_type == "movie" else "📺"

            tmdb_id = media.get("tmdbId")
            title = await self._lookup_title(media_type, tmdb_id) if tmdb_id else None
            if not title:
                title = "Unknown"
            
            requested_by = req.get("requestedBy", {}).get("displayName", "Unknown")
            created = req.get("createdAt", "")[:10] if req.get("createdAt") else "N/A"
            
            status = req.get("status", 0)
            status_map = {1: "🟡 Pending", 2: "✅ Approved", 3: "❌ Declined"}
            status_str = status_map.get(status, "❓ Unknown")
            
            # Check media availability
            media_status = media.get("status", 0)
            if media_status == 5:
                status_str = "📦 Available"
            elif media_status in [3, 4]:
                status_str = "⏳ Downloading"
            
            output += f"{type_emoji} **{title}** - {status_str}\n"
            output += f"   Requested by: {requested_by} on {created}\n"
        
        return output
