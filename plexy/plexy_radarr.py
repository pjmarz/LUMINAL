"""
title: Plexy Radarr Tool
description: Search and query movies from Radarr for the Plexy media assistant
author: Peter Marino
version: 1.2.0
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """Radarr movie library tools for Plexy."""

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

    def _get_all_movies(self) -> list:
        """Fetch all movies from Radarr."""
        try:
            response = requests.get(
                f"{self.valves.RADARR_URL}/api/v3/movie",
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return []

    def _fuzzy_match(self, query: str, candidates: list, threshold: float = 0.6) -> list:
        """
        Find fuzzy matches for a query in a list of candidates.
        Uses difflib for typo tolerance.
        """
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

    def search_movies_by_title(self, query: str) -> str:
        """
        Search for movies in the library by TITLE ONLY.
        DO NOT use this for actor/actress searches - use plexy_plex_tool search_by_actor() instead.

        :param query: Movie TITLE to search for (NOT an actor name)
        :return: List of matching movies with details
        """
        # Detect if user might be searching for an actor
        common_actor_patterns = ["movies with", "films with", "starring", "featuring", "acted by"]
        query_lower = query.lower()
        
        # Check if query looks like a person's name (two capitalized words)
        words = query.split()
        looks_like_person = (
            len(words) >= 2 and 
            all(w[0].isupper() for w in words if w) and
            not any(pattern in query_lower for pattern in ["the ", "a ", "an "])
        )
        
        if looks_like_person and len(query) > 5:
            return f"'{query}' looks like an actor/person name. For actor searches, please use: 'Use the Plex tool's search_by_actor function to find movies with {query}'"
        
        movies = self._get_all_movies()
        if not movies:
            return "Error: Could not fetch movies from Radarr. Check API connection."

        # Build candidates for fuzzy matching (title -> movie data)
        candidates = [(movie.get("title", ""), movie) for movie in movies]
        fuzzy_matches = self._fuzzy_match(query, candidates, threshold=0.6)
        
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

    def list_movies_by_genre(self, genre: str) -> str:
        """
        List all movies of a specific genre.
        Use this when users ask for movies by genre like "Christmas", "Horror", "Comedy".

        :param genre: Genre name to filter by (e.g., "Christmas", "Action", "Comedy")
        :return: List of movies in that genre
        """
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
        
        movies = self._get_all_movies()
        if not movies:
            return "Error: Could not fetch movies from Radarr."

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

        result = f"Found {len(matches)} '{genre}' movie(s):\n\n"
        for m in sorted(matches, key=lambda x: str(x.get("rating", 0)), reverse=True)[:20]:
            rating_str = f"⭐ {m['rating']}" if m['rating'] != "N/A" else ""
            result += f"• **{m['title']}** ({m['year']}) {rating_str}\n"

        if len(matches) > 20:
            result += f"\n... and {len(matches) - 20} more."

        return result

    def get_movie_details(self, title: str) -> str:
        """
        Get detailed information about a specific movie.
        Use this when users want more info about a particular movie.

        :param title: Exact or partial movie title
        :return: Detailed movie information
        """
        movies = self._get_all_movies()
        if not movies:
            return "Error: Could not fetch movies from Radarr."

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

    def get_recent_movies(self, days: int = 30) -> str:
        """
        Get movies added to the library recently.
        Use this when users ask about new additions or recently added content.

        :param days: Number of days to look back (default 30)
        :return: List of recently added movies
        """
        from datetime import datetime, timedelta
        
        movies = self._get_all_movies()
        if not movies:
            return "Error: Could not fetch movies from Radarr."

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
