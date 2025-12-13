"""
title: Midnight Overseerr Tool
description: Media request management via Overseerr for Midnight
author: Peter Marino
version: 1.0.0
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """Overseerr media request management tools for Midnight."""

    class Valves(BaseModel):
        """Configuration for Overseerr API connection."""
        OVERSEERR_URL: str = Field(
            default="http://192.168.4.46:5055",
            description="Overseerr server URL"
        )
        OVERSEERR_API_KEY: str = Field(
            default="",
            description="Overseerr API key"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            "X-Api-Key": self.valves.OVERSEERR_API_KEY,
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        """Make API request to Overseerr."""
        try:
            url = f"{self.valves.OVERSEERR_URL}/api/v1{endpoint}"
            if method == "GET":
                response = requests.get(url, headers=self._get_headers(), timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def search_to_request(self, query: str) -> str:
        """
        Search for movies or TV shows that can be requested.
        Use this when users want to request new content not in the library.

        :param query: Movie or TV show title to search for
        :return: List of results that can be requested
        """
        data = self._make_request(f"/search?query={requests.utils.quote(query)}&page=1")
        
        if "error" in data:
            return f"Error searching Overseerr: {data['error']}"
        
        results = data.get("results", [])
        if not results:
            return f"No results found for '{query}' in Overseerr."
        
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
        return output

    def request_movie(self, tmdb_id: int) -> str:
        """
        Request a movie to be added to the library.
        Use the TMDb ID from search results.

        :param tmdb_id: The Movie Database ID for the movie
        :return: Request status message
        """
        data = self._make_request("/request", method="POST", data={
            "mediaType": "movie",
            "mediaId": tmdb_id
        })
        
        if "error" in data:
            return f"Error requesting movie: {data['error']}"
        
        if data.get("id"):
            return f"✅ Movie request submitted successfully! Request ID: {data['id']}"
        
        return f"Request submitted. Status: {data}"

    def request_tv(self, tmdb_id: int, seasons: str = "all") -> str:
        """
        Request a TV show to be added to the library.
        Use the TMDb ID from search results.

        :param tmdb_id: The Movie Database ID for the TV show
        :param seasons: Which seasons to request - "all" or comma-separated numbers like "1,2,3"
        :return: Request status message
        """
        # First get show details to know available seasons
        show_data = self._make_request(f"/tv/{tmdb_id}")
        
        if "error" in show_data:
            return f"Error fetching show details: {show_data['error']}"
        
        # Build seasons request
        if seasons.lower() == "all":
            season_list = [{"seasonNumber": s.get("seasonNumber")} 
                          for s in show_data.get("seasons", []) 
                          if s.get("seasonNumber", 0) > 0]
        else:
            try:
                season_nums = [int(s.strip()) for s in seasons.split(",")]
                season_list = [{"seasonNumber": n} for n in season_nums]
            except:
                return "Invalid seasons format. Use 'all' or comma-separated numbers like '1,2,3'"
        
        data = self._make_request("/request", method="POST", data={
            "mediaType": "tv",
            "mediaId": tmdb_id,
            "seasons": season_list
        })
        
        if "error" in data:
            return f"Error requesting TV show: {data['error']}"
        
        if data.get("id"):
            return f"✅ TV show request submitted successfully! Request ID: {data['id']}"
        
        return f"Request submitted. Status: {data}"

    def get_pending_requests(self) -> str:
        """
        Get all pending media requests.
        Use this to see what has been requested but not yet fulfilled.

        :return: List of pending requests
        """
        data = self._make_request("/request?take=20&skip=0&filter=pending")
        
        if "error" in data:
            return f"Error fetching requests: {data['error']}"
        
        results = data.get("results", [])
        if not results:
            return "No pending requests."
        
        output = f"**Pending Requests ({len(results)}):**\n\n"
        
        for req in results:
            media = req.get("media", {})
            title = media.get("title") or media.get("name", "Unknown")
            media_type = req.get("type", "unknown")
            type_emoji = "🎬" if media_type == "movie" else "📺"
            
            requested_by = req.get("requestedBy", {}).get("displayName", "Unknown")
            created = req.get("createdAt", "")[:10] if req.get("createdAt") else "N/A"
            
            status = req.get("status", 0)
            status_map = {1: "🟡 Pending", 2: "✅ Approved", 3: "❌ Declined"}
            status_str = status_map.get(status, "❓ Unknown")
            
            output += f"{type_emoji} **{title}** - {status_str}\n"
            output += f"   Requested by: {requested_by} on {created}\n"
        
        return output

    def get_recent_requests(self, count: int = 10) -> str:
        """
        Get recent media requests (approved, pending, or declined).
        Use this to see request history.

        :param count: Number of requests to fetch (default 10)
        :return: List of recent requests
        """
        data = self._make_request(f"/request?take={count}&skip=0")
        
        if "error" in data:
            return f"Error fetching requests: {data['error']}"
        
        results = data.get("results", [])
        if not results:
            return "No requests found."
        
        output = f"**Recent Requests ({len(results)}):**\n\n"
        
        for req in results:
            media = req.get("media", {})
            title = media.get("title") or media.get("name", "Unknown")
            media_type = req.get("type", "unknown")
            type_emoji = "🎬" if media_type == "movie" else "📺"
            
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
