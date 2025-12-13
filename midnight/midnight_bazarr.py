"""
title: Midnight Bazarr Tool
description: Subtitle status and management via Bazarr for Midnight
author: Peter Marino
version: 1.2.0
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """Bazarr subtitle management tools for Midnight."""

    class Valves(BaseModel):
        """Configuration for Bazarr API connection."""
        BAZARR_URL: str = Field(
            default="http://192.168.4.46:6767",
            description="Bazarr server URL"
        )
        BAZARR_API_KEY: str = Field(
            default="",
            description="Bazarr API key"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {"X-API-KEY": self.valves.BAZARR_API_KEY}

    def _fuzzy_match(self, query: str, candidates: list, threshold: float = 0.6) -> list:
        """Find fuzzy matches using difflib for typo tolerance."""
        from difflib import SequenceMatcher
        
        query_lower = query.lower()
        matches = []
        
        for name, data in candidates:
            name_lower = name.lower()
            if query_lower in name_lower or name_lower in query_lower:
                matches.append((name, data, 1.0))
            else:
                ratio = SequenceMatcher(None, query_lower, name_lower).ratio()
                if ratio >= threshold:
                    matches.append((name, data, ratio))
        
        return sorted(matches, key=lambda x: x[2], reverse=True)

    def check_subtitles(self, title: str) -> str:
        """
        Check subtitle status for a movie or TV show.
        Use this when users ask about subtitles for specific content.

        :param title: Movie or TV show title to check subtitles for
        :return: Subtitle status information
        """
        results = []

        # Check movies
        try:
            response = requests.get(
                f"{self.valves.BAZARR_URL}/api/movies",
                headers=self._get_headers(),
                timeout=30
            )
            if response.ok:
                movies = response.json().get("data", [])
                candidates = [(m.get("title", ""), m) for m in movies]
                matches = self._fuzzy_match(title, candidates, threshold=0.6)
                
                for movie_title, movie, score in matches[:5]:
                    missing = movie.get("missing_subtitles", [])
                    existing = movie.get("subtitles", [])
                    
                    result = f"🎬 **{movie.get('title')}**\n"
                    if existing:
                        langs = [s.get("code2", "??") for s in existing]
                        result += f"  ✓ Subtitles: {', '.join(langs)}\n"
                    if missing:
                        langs = [s.get("code2", "??") for s in missing]
                        result += f"  ✗ Missing: {', '.join(langs)}\n"
                    if not existing and not missing:
                        result += "  No subtitle data available\n"
                    results.append(result)
        except:
            pass

        # Check TV shows
        try:
            response = requests.get(
                f"{self.valves.BAZARR_URL}/api/series",
                headers=self._get_headers(),
                timeout=30
            )
            if response.ok:
                series = response.json().get("data", [])
                candidates = [(s.get("title", ""), s) for s in series]
                matches = self._fuzzy_match(title, candidates, threshold=0.6)
                
                for show_title, show, score in matches[:5]:
                    episodes_missing = show.get("episodeMissingCount", 0)
                    episodes_total = show.get("episodeFileCount", 0)
                    
                    result = f"📺 **{show.get('title')}**\n"
                    if episodes_missing > 0:
                        result += f"  ⚠️ {episodes_missing} episodes missing subtitles\n"
                    else:
                        result += f"  ✓ All {episodes_total} episodes have subtitles\n"
                    results.append(result)
        except:
            pass

        if not results:
            return f"No content found matching '{title}' in Bazarr. Try checking the spelling."

        return "Subtitle status:\n\n" + "\n".join(results)

    def get_missing_subtitles(self) -> str:
        """
        Get all content that is missing subtitles.
        Use this when users ask about missing subtitles or what needs subtitles.

        :return: List of movies and shows missing subtitles
        """
        result = "Content missing subtitles:\n\n"
        count = 0

        # Movies missing subtitles
        try:
            response = requests.get(
                f"{self.valves.BAZARR_URL}/api/movies/wanted",
                headers=self._get_headers(),
                params={"length": 20},
                timeout=30
            )
            if response.ok:
                movies = response.json().get("data", [])
                if movies:
                    result += "**Movies:**\n"
                    for movie in movies[:10]:
                        title = movie.get("title", "Unknown")
                        missing = movie.get("missing_subtitles", [])
                        langs = [s.get("code2", "??") for s in missing]
                        result += f"  • {title} (missing: {', '.join(langs)})\n"
                        count += 1
        except:
            pass

        # Episodes missing subtitles
        try:
            response = requests.get(
                f"{self.valves.BAZARR_URL}/api/episodes/wanted",
                headers=self._get_headers(),
                params={"length": 20},
                timeout=30
            )
            if response.ok:
                episodes = response.json().get("data", [])
                if episodes:
                    result += "\n**TV Episodes:**\n"
                    for ep in episodes[:10]:
                        show = ep.get("seriesTitle", "Unknown")
                        season = ep.get("season", 0)
                        episode = ep.get("episode", 0)
                        missing = ep.get("missing_subtitles", [])
                        langs = [s.get("code2", "??") for s in missing]
                        result += f"  • {show} S{season:02d}E{episode:02d} (missing: {', '.join(langs)})\n"
                        count += 1
        except:
            pass

        if count == 0:
            return "✓ No content is missing subtitles!"

        return result

    def get_subtitle_history(self, count: int = 15) -> str:
        """
        Get recent subtitle download history.
        Use this when users ask about recent subtitle activity.

        :param count: Number of recent items to show (default 15)
        :return: Recent subtitle downloads
        """
        try:
            response = requests.get(
                f"{self.valves.BAZARR_URL}/api/history/movies",
                headers=self._get_headers(),
                params={"length": count},
                timeout=30
            )
            movie_history = response.json().get("data", []) if response.ok else []

            response = requests.get(
                f"{self.valves.BAZARR_URL}/api/history/series",
                headers=self._get_headers(),
                params={"length": count},
                timeout=30
            )
            series_history = response.json().get("data", []) if response.ok else []

            if not movie_history and not series_history:
                return "No recent subtitle download history."

            result = "Recent subtitle downloads:\n\n"

            if movie_history:
                result += "**Movies:**\n"
                for item in movie_history[:8]:
                    title = item.get("title", "Unknown")
                    language = item.get("language", {}).get("code2", "??")
                    provider = item.get("provider", "unknown")
                    result += f"  • {title} ({language}) via {provider}\n"

            if series_history:
                result += "\n**TV Episodes:**\n"
                for item in series_history[:8]:
                    show = item.get("seriesTitle", "Unknown")
                    season = item.get("episode", {}).get("season", 0)
                    episode = item.get("episode", {}).get("episode", 0)
                    language = item.get("language", {}).get("code2", "??")
                    result += f"  • {show} S{season:02d}E{episode:02d} ({language})\n"

            return result

        except Exception as e:
            return f"Error fetching subtitle history: {str(e)}"
