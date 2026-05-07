"""
title: Midnight Bazarr Tool
author: Peter Marino
description: Subtitle status and management via Bazarr for Midnight
required_open_webui_version: 0.4.0
requirements: httpx, pydantic
version: 2.0.0
licence: MIT
"""

import asyncio
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

    async def check_subtitles(self, title: str, __event_emitter__=None) -> str:
        """
        Check subtitle status for a movie or TV show.
        Use this when users ask about subtitles for specific content.

        :param title: Movie or TV show title to check subtitles for
        :return: Subtitle status information
        """
        await emit_status(__event_emitter__, f"Checking Bazarr for '{title}'…")
        results = []
        errors = []

        # Fan out movies + series queries in parallel
        headers = self._get_headers()
        movies_resp, series_resp = await asyncio.gather(
            http_get_json(f"{self.valves.BAZARR_URL}/api/movies", headers=headers),
            http_get_json(f"{self.valves.BAZARR_URL}/api/series", headers=headers),
            return_exceptions=True,
        )

        # Movies branch
        if isinstance(movies_resp, Exception):
            errors.append(f"Movies query failed: {movies_resp}")
        else:
            movies = movies_resp.get("data", [])
            candidates = [(m.get("title", ""), m) for m in movies]
            for movie_title, movie, score in fuzzy_match(title, candidates, threshold=0.6)[:5]:
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

        # Series branch
        if isinstance(series_resp, Exception):
            errors.append(f"Series query failed: {series_resp}")
        else:
            series = series_resp.get("data", [])
            candidates = [(s.get("title", ""), s) for s in series]
            for show_title, show, score in fuzzy_match(title, candidates, threshold=0.6)[:5]:
                episodes_missing = show.get("episodeMissingCount", 0)
                episodes_total = show.get("episodeFileCount", 0)
                result = f"📺 **{show.get('title')}**\n"
                if episodes_missing > 0:
                    result += f"  ⚠️ {episodes_missing} episodes missing subtitles\n"
                else:
                    result += f"  ✓ All {episodes_total} episodes have subtitles\n"
                results.append(result)

        if errors and not results:
            await emit_status(__event_emitter__, "Bazarr unreachable", done=True)
            return f"Bazarr error: {'; '.join(errors)}"

        if not results:
            await emit_status(__event_emitter__, "No matches", done=True)
            return f"No content found matching '{title}' in Bazarr. Try checking the spelling."

        output = "Subtitle status:\n\n" + "\n".join(results)
        if errors:
            output += f"\n\n⚠️ Partial results — {'; '.join(errors)}"
        await emit_status(__event_emitter__, f"Found {len(results)} result(s)", done=True)
        return output

    async def get_missing_subtitles(self, __event_emitter__=None) -> str:
        """
        Get all content that is missing subtitles.
        Use this when users ask about missing subtitles or what needs subtitles.

        :return: List of movies and shows missing subtitles
        """
        result = "Content missing subtitles:\n\n"
        count = 0
        errors = []

        # Fan out movies-wanted + episodes-wanted queries in parallel
        headers = self._get_headers()
        movies_resp, episodes_resp = await asyncio.gather(
            http_get_json(f"{self.valves.BAZARR_URL}/api/movies/wanted", headers=headers, params={"length": 20}),
            http_get_json(f"{self.valves.BAZARR_URL}/api/episodes/wanted", headers=headers, params={"length": 20}),
            return_exceptions=True,
        )

        if isinstance(movies_resp, Exception):
            errors.append(f"Movies-wanted query failed: {movies_resp}")
        else:
            movies = movies_resp.get("data", [])
            if movies:
                result += "**Movies:**\n"
                for movie in movies[:10]:
                    title = movie.get("title", "Unknown")
                    missing = movie.get("missing_subtitles", [])
                    langs = [s.get("code2", "??") for s in missing]
                    result += f"  • {title} (missing: {', '.join(langs)})\n"
                    count += 1

        if isinstance(episodes_resp, Exception):
            errors.append(f"Episodes-wanted query failed: {episodes_resp}")
        else:
            episodes = episodes_resp.get("data", [])
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

        if errors and count == 0:
            return f"Bazarr error: {'; '.join(errors)}"

        if count == 0:
            return "✓ No content is missing subtitles!"

        if errors:
            result += f"\n⚠️ Partial results — {'; '.join(errors)}"
        return result

    async def get_subtitle_history(self, count: int = 15, __event_emitter__=None) -> str:
        """
        Get recent subtitle download history.
        Use this when users ask about recent subtitle activity.

        :param count: Number of recent items to show (default 15)
        :return: Recent subtitle downloads
        """
        headers = self._get_headers()
        movies_resp, series_resp = await asyncio.gather(
            http_get_json(f"{self.valves.BAZARR_URL}/api/history/movies", headers=headers, params={"length": count}),
            http_get_json(f"{self.valves.BAZARR_URL}/api/history/series", headers=headers, params={"length": count}),
            return_exceptions=True,
        )
        try:
            movie_history = movies_resp.get("data", []) if not isinstance(movies_resp, Exception) else []
            series_history = series_resp.get("data", []) if not isinstance(series_resp, Exception) else []

            if not movie_history and not series_history:
                if isinstance(movies_resp, Exception) and isinstance(series_resp, Exception):
                    return f"Bazarr error: {movies_resp}; {series_resp}"
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
