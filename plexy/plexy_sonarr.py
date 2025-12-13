"""
title: Plexy Sonarr Tool
description: Search and query TV shows from Sonarr for the Plexy media assistant
author: Peter Marino
version: 1.2.0
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """Sonarr TV show library tools for Plexy."""

    class Valves(BaseModel):
        """Configuration for Sonarr API connection."""
        SONARR_URL: str = Field(
            default="http://192.168.4.46:8989",
            description="Sonarr server URL"
        )
        SONARR_API_KEY: str = Field(
            default="",
            description="Sonarr API key"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {"X-Api-Key": self.valves.SONARR_API_KEY}

    def _get_all_series(self) -> list:
        """Fetch all TV series from Sonarr."""
        try:
            response = requests.get(
                f"{self.valves.SONARR_URL}/api/v3/series",
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return []

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

    def search_tv_shows(self, query: str) -> str:
        """
        Search for TV shows in the library by title.
        Use this when users ask about specific TV shows or series.

        :param query: TV show title or keyword to search for
        :return: List of matching TV shows with details
        """
        series = self._get_all_series()
        if not series:
            return "Error: Could not fetch TV shows from Sonarr. Check API connection."

        # Build candidates for fuzzy matching
        candidates = [(show.get("title", ""), show) for show in series]
        fuzzy_matches = self._fuzzy_match(query, candidates, threshold=0.6)
        
        matches = []
        for title, show, score in fuzzy_matches[:15]:
            stats = show.get("statistics", {})
            episodes_have = stats.get("episodeFileCount", 0)
            episodes_total = stats.get("episodeCount", 0)
            seasons = len([s for s in show.get("seasons", []) if s.get("seasonNumber", 0) > 0])
            
            matches.append({
                "title": show.get("title"),
                "year": show.get("year", "N/A"),
                "seasons": seasons,
                "episodes": f"{episodes_have}/{episodes_total}",
                "network": show.get("network", "Unknown"),
                "status": show.get("status", "Unknown"),
                "score": score
            })

        if not matches:
            return f"No TV shows found matching '{query}' in the library. Try checking the spelling."

        result = f"Found {len(matches)} TV show(s) matching '{query}':\n\n"
        for s in matches[:15]:
            status_icon = "🟢" if s['status'] == "continuing" else "🔴"
            result += f"• **{s['title']}** ({s['year']}) - {s['seasons']} seasons, {s['episodes']} episodes {status_icon}\n"
            result += f"  Network: {s['network']}\n"

        return result

    def list_shows_by_genre(self, genre: str) -> str:
        """
        List all TV shows of a specific genre.
        Use this when users ask for shows by genre like "sci-fi", "comedy", "drama".

        :param genre: Genre name to filter by
        :return: List of TV shows in that genre
        """
        # Genre synonyms - map common terms to official genre names
        genre_synonyms = {
            "sci-fi": ["science fiction"],
            "scifi": ["science fiction"],
            "sf": ["science fiction"],
            "rom-com": ["romance", "comedy"],
            "romcom": ["romance", "comedy"],
            "sitcom": ["comedy"],
            "scary": ["horror"],
            "spooky": ["horror"],
            "funny": ["comedy"],
            "animated": ["animation"],
            "cartoon": ["animation"],
            "anime": ["animation"],
            "suspense": ["thriller"],
            "detective": ["mystery", "crime"],
            "cop": ["crime"],
            "police": ["crime"],
            "procedural": ["crime", "drama"],
            "medical": ["drama"],
            "legal": ["drama", "crime"],
            "superhero": ["action", "adventure"],
            "kids": ["family", "animation"],
            "children": ["family"],
            "reality": ["reality"],
            "game show": ["game-show"],
            "talk show": ["talk-show"],
            "soap": ["soap"],
            "miniseries": ["mini-series"],
        }
        
        series = self._get_all_series()
        if not series:
            return "Error: Could not fetch TV shows from Sonarr."

        genre_lower = genre.lower().strip()
        
        # Expand genre to include synonyms
        search_genres = [genre_lower]
        if genre_lower in genre_synonyms:
            search_genres.extend(genre_synonyms[genre_lower])
        
        matches = []

        for show in series:
            genres = [g.lower() for g in show.get("genres", [])]
            title_lower = show.get("title", "").lower()
            overview_lower = show.get("overview", "").lower()
            
            # Check if any search genre matches
            matched = False
            for search_genre in search_genres:
                if (search_genre in genres or 
                    search_genre in title_lower or 
                    search_genre in overview_lower):
                    matched = True
                    break
            
            if matched:
                stats = show.get("statistics", {})
                matches.append({
                    "title": show.get("title"),
                    "year": show.get("year", "N/A"),
                    "seasons": stats.get("seasonCount", 0),
                    "episodes": stats.get("episodeFileCount", 0),
                    "status": show.get("status", "unknown"),
                    "network": show.get("network", "Unknown")
                })

        if not matches:
            return f"No '{genre}' TV shows found in the library."

        result = f"Found {len(matches)} '{genre}' TV show(s):\n\n"
        for s in sorted(matches, key=lambda x: x.get("year", 0), reverse=True)[:20]:
            status_icon = "🟢" if s['status'] == "continuing" else "🔴"
            result += f"• **{s['title']}** ({s['year']}) - {s['seasons']} seasons {status_icon}\n"

        if len(matches) > 20:
            result += f"\n... and {len(matches) - 20} more."

        return result

    def get_show_details(self, title: str) -> str:
        """
        Get detailed information about a specific TV show including seasons.
        Use this when users want details about a particular show.

        :param title: Exact or partial TV show title
        :return: Detailed show information with season breakdown
        """
        series = self._get_all_series()
        if not series:
            return "Error: Could not fetch TV shows from Sonarr."

        title_lower = title.lower()
        
        for show in series:
            if title_lower in show.get("title", "").lower():
                year = show.get("year", "N/A")
                network = show.get("network", "Unknown")
                status = show.get("status", "Unknown")
                overview = show.get("overview", "No overview available.")
                genres = ", ".join(show.get("genres", []))
                stats = show.get("statistics", {})
                size_gb = stats.get("sizeOnDisk", 0) / (1024**3)
                
                status_text = "🟢 Continuing" if status == "continuing" else "🔴 Ended"
                
                result = f"""**{show.get('title')}** ({year})

• **Status**: {status_text}
• **Network**: {network}
• **Genres**: {genres}
• **Total Size**: {size_gb:.1f} GB

**Seasons**:
"""
                for season in show.get("seasons", []):
                    snum = season.get("seasonNumber", 0)
                    if snum == 0:
                        continue  # Skip specials
                    s_stats = season.get("statistics", {})
                    s_have = s_stats.get("episodeFileCount", 0)
                    s_total = s_stats.get("totalEpisodeCount", 0)
                    pct = s_stats.get("percentOfEpisodes", 0)
                    icon = "✓" if pct == 100 else "◐" if pct > 0 else "✗"
                    result += f"  Season {snum}: {s_have}/{s_total} episodes {icon}\n"

                result += f"\n**Overview**: {overview[:300]}..."
                return result

        return f"TV show '{title}' not found in library."

    def get_upcoming_episodes(self) -> str:
        """
        Get episodes that are airing soon.
        Use this when users ask what's coming up or new episodes.

        :return: List of upcoming episodes
        """
        try:
            from datetime import datetime, timedelta
            
            start = datetime.now().strftime("%Y-%m-%d")
            end = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            
            response = requests.get(
                f"{self.valves.SONARR_URL}/api/v3/calendar",
                headers=self._get_headers(),
                params={"start": start, "end": end, "includeSeries": "true"},
                timeout=30
            )
            response.raise_for_status()
            episodes = response.json()

            if not episodes:
                return "No upcoming episodes in the next 14 days."

            result = "Upcoming episodes (next 14 days):\n\n"
            for ep in episodes[:15]:
                series_title = ep.get("series", {}).get("title", "Unknown")
                season = ep.get("seasonNumber", 0)
                episode = ep.get("episodeNumber", 0)
                title = ep.get("title", "TBA")
                air_date = ep.get("airDateUtc", "")[:10]
                
                result += f"• **{series_title}** S{season:02d}E{episode:02d} - {title}\n"
                result += f"  Airs: {air_date}\n"

            return result

        except Exception as e:
            return f"Error fetching upcoming episodes: {str(e)}"

    def get_recent_episodes(self, days: int = 7) -> str:
        """
        Get episodes downloaded recently.
        Use this when users ask about new or recently added episodes.

        :param days: Number of days to look back (default 7)
        :return: List of recently downloaded episodes
        """
        try:
            response = requests.get(
                f"{self.valves.SONARR_URL}/api/v3/history",
                headers=self._get_headers(),
                params={"pageSize": 30, "eventType": 3},  # eventType 3 = downloaded
                timeout=30
            )
            response.raise_for_status()
            history = response.json().get("records", [])

            if not history:
                return "No episodes downloaded recently."

            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=days)
            
            result = f"Episodes downloaded in the last {days} days:\n\n"
            count = 0
            
            for record in history:
                date_str = record.get("date", "")
                try:
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if date.replace(tzinfo=None) < cutoff:
                        continue
                except:
                    continue
                    
                series = record.get("series", {}).get("title", "Unknown")
                episode = record.get("episode", {})
                season = episode.get("seasonNumber", 0)
                ep_num = episode.get("episodeNumber", 0)
                title = episode.get("title", "Unknown")
                
                result += f"• **{series}** S{season:02d}E{ep_num:02d} - {title}\n"
                count += 1
                
                if count >= 15:
                    break

            if count == 0:
                return f"No episodes downloaded in the last {days} days."
                
            return result

        except Exception as e:
            return f"Error fetching recent episodes: {str(e)}"
