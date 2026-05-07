"""
title: Midnight Radarr Tool
author: Peter Marino
description: Search and query movies from Radarr for the Midnight media assistant
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
    """Radarr movie library tools for Midnight."""

    class Valves(BaseModel):
        """Configuration for Radarr API connection."""
        RADARR_URL: str = Field(
            default="http://192.168.4.46:7878",
            description="Radarr server URL"
        )
        RADARR_API_KEY: str = Field(
            default="",
            description="Radarr API key"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {"X-Api-Key": self.valves.RADARR_API_KEY}

    async def _get_all_movies(self) -> list:
        """Fetch all movies from Radarr. Raises on transport/HTTP error."""
        return await http_get_json(
            f"{self.valves.RADARR_URL}/api/v3/movie",
            headers=self._get_headers(),
        )

    async def search_movies_by_title(self, query: str, __event_emitter__=None) -> str:
        """
        Search for movies in the library by TITLE ONLY.
        DO NOT use this for actor/actress searches - use midnight_plex_tool search_by_actor() instead.

        :param query: Movie TITLE to search for (NOT an actor name)
        :return: List of matching movies with details
        """
        await emit_status(__event_emitter__, f"Searching Radarr for '{query}'…")
        query_lower = query.lower().strip()
        
        # Only flag as actor search if query contains explicit actor patterns
        actor_patterns = ["movies with", "films with", "starring", "featuring", "acted by", "with actor", "with actress"]
        is_actor_query = any(pattern in query_lower for pattern in actor_patterns)
        
        if is_actor_query:
            # Extract the actor name (everything after the pattern)
            actor_name = query
            for pattern in actor_patterns:
                if pattern in query_lower:
                    idx = query_lower.find(pattern)
                    actor_name = query[idx + len(pattern):].strip()
                    break
            return f"For actor searches, please use the Plex tool's search_by_actor function to find movies with '{actor_name}'"
        
        try:
            movies = await self._get_all_movies()
        except Exception as e:
            return f"Radarr error: {e}"

        if not movies:
            return "Radarr returned no movies. The library may be empty."

        # Build candidates for fuzzy matching (title -> movie data)
        candidates = [(movie.get("title", ""), movie) for movie in movies]
        fuzzy_matches = fuzzy_match(query, candidates, threshold=0.6)
        
        matches = []
        for title, movie, score in fuzzy_matches[:20]:  # Limit fuzzy results
            year = movie.get("year", "N/A")
            rating = movie.get("ratings", {}).get("imdb", {}).get("value", "N/A")
            has_file = movie.get("hasFile", False)
            status = "✓ Downloaded" if has_file else "✗ Missing"
            
            matches.append({
                "title": movie.get("title"),
                "year": year,
                "rating": rating,
                "status": status,
                "score": score
            })

        if not matches:
            return f"No movies found matching '{query}' in the library. Try checking the spelling."

        # Format results
        result = f"Found {len(matches)} movie(s) matching '{query}':\n\n"
        for m in matches[:15]:  # Limit to 15 results
            rating_str = f"⭐ {m['rating']}" if m['rating'] != "N/A" else ""
            result += f"• **{m['title']}** ({m['year']}) {rating_str} - {m['status']}\n"

        if len(matches) > 15:
            result += f"\n... and {len(matches) - 15} more."

        return result

    async def list_movies_by_genre(self, genre: str, __event_emitter__=None) -> str:
        """
        List all movies of a specific genre.
        Use this when users ask for movies by genre like "Christmas", "Horror", "Comedy".

        :param genre: Genre name to filter by (e.g., "Christmas", "Action", "Comedy")
        :return: List of movies in that genre
        """
        await emit_status(__event_emitter__, f"Filtering Radarr library by genre '{genre}'…")
        # Genre synonyms - map common terms to official genre names
        genre_synonyms = {
            "sci-fi": ["science fiction"],
            "scifi": ["science fiction"],
            "sf": ["science fiction"],
            "rom-com": ["romance", "comedy"],
            "romcom": ["romance", "comedy"],
            "romantic comedy": ["romance", "comedy"],
            "xmas": ["christmas"],
            "holiday": ["christmas"],
            "scary": ["horror"],
            "spooky": ["horror"],
            "funny": ["comedy"],
            "action-adventure": ["action", "adventure"],
            "period": ["history"],
            "historical": ["history"],
            "war film": ["war"],
            "animated": ["animation"],
            "cartoon": ["animation"],
            "suspense": ["thriller"],
            "whodunit": ["mystery"],
            "detective": ["mystery", "crime"],
            "cop": ["crime"],
            "police": ["crime"],
            "love story": ["romance"],
            "romantic": ["romance"],
            "superhero": ["action", "adventure"],
            "comic book": ["action", "adventure"],
            "kids": ["family", "animation"],
            "children": ["family"],
            "musical": ["music"],
            "doc": ["documentary"],
            "true story": ["documentary", "history"],
        }
        
        try:
            movies = await self._get_all_movies()
        except Exception as e:
            return f"Radarr error: {e}"

        if not movies:
            return "Radarr returned no movies. The library may be empty."

        genre_lower = genre.lower().strip()
        
        # Expand genre to include synonyms
        search_genres = [genre_lower]
        if genre_lower in genre_synonyms:
            search_genres.extend(genre_synonyms[genre_lower])
        
        matches = []

        for movie in movies:
            genres = [g.lower() for g in movie.get("genres", [])]
            title_lower = movie.get("title", "").lower()
            overview_lower = movie.get("overview", "").lower()
            
            # Check if any search genre matches
            matched = False
            for search_genre in search_genres:
                if (search_genre in genres or 
                    search_genre in title_lower or 
                    search_genre in overview_lower):
                    matched = True
                    break
            
            if matched and movie.get("hasFile", False):
                matches.append({
                    "title": movie.get("title"),
                    "year": movie.get("year", "N/A"),
                    "rating": movie.get("ratings", {}).get("imdb", {}).get("value", "N/A")
                })

        if not matches:
            return f"No '{genre}' movies found in the downloaded library."

        def rating_value(value: object) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        result = f"Found {len(matches)} '{genre}' movie(s):\n\n"
        for m in sorted(matches, key=lambda x: rating_value(x.get("rating")), reverse=True)[:20]:
            rating_str = f"⭐ {m['rating']}" if m['rating'] != "N/A" else ""
            result += f"• **{m['title']}** ({m['year']}) {rating_str}\n"

        if len(matches) > 20:
            result += f"\n... and {len(matches) - 20} more."

        await emit_status(__event_emitter__, f"Found {len(matches)} match(es)", done=True)
        return result

    async def get_movie_details(self, title: str, __event_emitter__=None) -> str:
        """
        Get detailed information about a specific movie.
        Use this when users want more info about a particular movie.

        :param title: Exact or partial movie title
        :return: Detailed movie information
        """
        await emit_status(__event_emitter__, f"Fetching details for '{title}'…")
        try:
            movies = await self._get_all_movies()
        except Exception as e:
            return f"Radarr error: {e}"

        if not movies:
            return "Radarr returned no movies. The library may be empty."

        # Strip year from query if present (e.g., "Movie Title (2024)" -> "Movie Title")
        import re
        title_clean = re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()
        title_lower = title_clean.lower()
        
        # Find best match
        for movie in movies:
            movie_title = movie.get("title", "").lower()
            # Match if query in title OR title in query (bidirectional)
            if title_lower in movie_title or movie_title in title_lower:
                year = movie.get("year", "N/A")
                runtime = movie.get("runtime", 0)
                genres = ", ".join(movie.get("genres", []))
                rating = movie.get("ratings", {}).get("imdb", {}).get("value", "N/A")
                overview = movie.get("overview", "No overview available.")
                has_file = movie.get("hasFile", False)
                status = "✓ Downloaded" if has_file else "✗ Not downloaded"
                size_gb = movie.get("sizeOnDisk", 0) / (1024**3)

                return f"""**{movie.get('title')}** ({year})

• **Status**: {status}
• **Runtime**: {runtime} minutes
• **Genres**: {genres}
• **Rating**: ⭐ {rating}/10
• **Size**: {size_gb:.1f} GB

**Overview**: {overview}"""

        return f"Movie '{title}' not found in library."

    async def get_recent_movies(self, days: int = 30, __event_emitter__=None) -> str:
        """
        Get movies added to the library recently.
        Use this when users ask about new additions or recently added content.

        :param days: Number of days to look back (default 30)
        :return: List of recently added movies
        """
        await emit_status(__event_emitter__, f"Scanning Radarr for movies in last {days} days…")
        from datetime import datetime, timedelta

        try:
            movies = await self._get_all_movies()
        except Exception as e:
            return f"Radarr error: {e}"

        if not movies:
            return "Radarr returned no movies. The library may be empty."

        cutoff = datetime.now() - timedelta(days=days)
        recent = []

        for movie in movies:
            if not movie.get("hasFile"):
                continue
                
            added_str = movie.get("movieFile", {}).get("dateAdded", "")
            if added_str:
                try:
                    added_date = datetime.fromisoformat(added_str.replace("Z", "+00:00"))
                    if added_date.replace(tzinfo=None) > cutoff:
                        recent.append({
                            "title": movie.get("title"),
                            "year": movie.get("year"),
                            "added": added_date.strftime("%Y-%m-%d")
                        })
                except:
                    pass

        if not recent:
            return f"No movies added in the last {days} days."

        recent.sort(key=lambda x: x["added"], reverse=True)
        
        result = f"Movies added in the last {days} days:\n\n"
        for m in recent[:15]:
            result += f"• **{m['title']}** ({m['year']}) - Added {m['added']}\n"

        return result
