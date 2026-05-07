"""
title: Midnight Seerr Tool
author: Peter Marino
description: Media request management via Seerr (formerly Overseerr) for Midnight
required_open_webui_version: 0.4.0
requirements: requests, pydantic
version: 2.0.0
licence: MIT
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


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

    def __init__(self):
        self.valves = self.Valves()
        self._title_cache: dict = {}  # (media_type, tmdb_id) -> title

    async def _emit(self, emitter, description: str, done: bool = False) -> None:
        """Send a status event to OpenWebUI if an emitter is wired."""
        if emitter:
            await emitter({
                "type": "status",
                "data": {"description": description, "done": done},
            })

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            "X-Api-Key": self.valves.SEERR_API_KEY,
            "Content-Type": "application/json"
        }

    def _lookup_title(self, media_type: str, tmdb_id: int) -> Optional[str]:
        """Look up a title for a (media_type, tmdb_id) pair, caching across calls.

        Returns None on lookup failure rather than raising — partial result
        ("Unknown") is preferable to failing the whole listing.
        """
        key = (media_type, tmdb_id)
        if key in self._title_cache:
            return self._title_cache[key]
        try:
            if media_type == "movie":
                details = self._make_request(f"/movie/{tmdb_id}")
                title = details.get("title")
            else:
                details = self._make_request(f"/tv/{tmdb_id}")
                title = details.get("name")
        except Exception:
            return None
        if title:
            self._title_cache[key] = title
        return title

    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        """Make API request to Seerr. Raises on transport/HTTP error."""
        url = f"{self.valves.SEERR_URL}/api/v1{endpoint}"
        if method == "GET":
            response = requests.get(url, headers=self._get_headers(), timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        response.raise_for_status()
        return response.json()

    async def search_to_request(self, query: str, __event_emitter__=None) -> str:
        """
        Search for movies or TV shows that can be requested.
        Use this when users want to request new content not in the library.

        :param query: Movie or TV show title to search for
        :return: List of results that can be requested
        """
        await self._emit(__event_emitter__, f"Searching Seerr for '{query}'…")
        try:
            data = self._make_request(f"/search?query={requests.utils.quote(query)}&page=1")
        except Exception as e:
            await self._emit(__event_emitter__, "Seerr unreachable", done=True)
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
        await self._emit(__event_emitter__, f"Found {len(results)} result(s)", done=True)
        return output

    async def request_movie(self, tmdb_id: int, __event_emitter__=None) -> str:
        """
        Request a movie to be added to the library.
        Use the TMDb ID from search results.

        :param tmdb_id: The Movie Database ID for the movie
        :return: Request status message
        """
        try:
            data = self._make_request("/request", method="POST", data={
                "mediaType": "movie",
                "mediaId": tmdb_id
            })
        except Exception as e:
            return f"Seerr error requesting movie: {e}"

        if data.get("id"):
            return f"✅ Movie request submitted successfully! Request ID: {data['id']}"

        return f"Request submitted but no request ID returned. Raw response: {data}"

    async def request_tv(self, tmdb_id: int, seasons: str = "all", __event_emitter__=None) -> str:
        """
        Request a TV show to be added to the library.
        Use the TMDb ID from search results.

        :param tmdb_id: The Movie Database ID for the TV show
        :param seasons: Which seasons to request - "all" or comma-separated numbers like "1,2,3"
        :return: Request status message
        """
        # First get show details to know available seasons
        try:
            show_data = self._make_request(f"/tv/{tmdb_id}")
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

        try:
            data = self._make_request("/request", method="POST", data={
                "mediaType": "tv",
                "mediaId": tmdb_id,
                "seasons": season_list
            })
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
        try:
            data = self._make_request("/request?take=20&skip=0&filter=pending")
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
            title = self._lookup_title(media_type, tmdb_id) if tmdb_id else None
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
        try:
            data = self._make_request(f"/request?take={count}&skip=0")
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
            title = self._lookup_title(media_type, tmdb_id) if tmdb_id else None
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
