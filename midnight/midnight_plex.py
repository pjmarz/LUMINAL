"""
title: Midnight Plex Tool
description: Unified search and library access for Plex Media Server
author: Peter Marino
version: 1.2.0
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """Plex Media Server tools for Midnight."""

    class Valves(BaseModel):
        """Configuration for Plex API connection."""
        PLEX_URL: str = Field(
            default="http://192.168.4.46:32400",
            description="Plex server URL"
        )
        PLEX_TOKEN: str = Field(
            default="",
            description="Plex authentication token"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            "X-Plex-Token": self.valves.PLEX_TOKEN,
            "Accept": "application/json"
        }

    def _fuzzy_match(self, query: str, candidates: list, threshold: float = 0.6) -> list:
        """
        Find fuzzy matches for a query in a list of candidates.
        Uses difflib for typo tolerance.
        
        :param query: Search query (potentially misspelled)
        :param candidates: List of (name, data) tuples to match against
        :param threshold: Minimum similarity ratio (0.0 to 1.0)
        :return: List of matching (name, data, score) tuples, sorted by score
        """
        from difflib import SequenceMatcher
        
        query_lower = query.lower()
        matches = []
        
        for name, data in candidates:
            name_lower = name.lower()
            
            # Direct substring match gets highest score
            if query_lower in name_lower or name_lower in query_lower:
                matches.append((name, data, 1.0))
            else:
                # Calculate similarity ratio
                ratio = SequenceMatcher(None, query_lower, name_lower).ratio()
                if ratio >= threshold:
                    matches.append((name, data, ratio))
        
        # Sort by score descending
        return sorted(matches, key=lambda x: x[2], reverse=True)

    def search_plex(self, query: str) -> str:
        """
        Search across all Plex libraries for movies, TV shows, or other content.
        Use this for unified search when user doesn't specify movie vs TV.
        For actor searches, use search_by_actor() instead for better results.

        :param query: Search term (title, etc.)
        :return: Search results from all libraries
        """
        try:
            response = requests.get(
                f"{self.valves.PLEX_URL}/hubs/search",
                headers=self._get_headers(),
                params={"query": query, "limit": 50},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            hubs = data.get("MediaContainer", {}).get("Hub", [])
            
            if not hubs:
                return f"No results found for '{query}' in Plex."

            result = f"Plex search results for '{query}':\n\n"
            
            for hub in hubs:
                hub_type = hub.get("type", "unknown")
                items = hub.get("Metadata", [])
                
                if not items:
                    continue
                    
                if hub_type == "movie":
                    result += f"**Movies ({len(items)} found):**\n"
                    for item in items[:20]:
                        title = item.get("title", "Unknown")
                        year = item.get("year", "N/A")
                        rating = item.get("rating", "N/A")
                        result += f"  • {title} ({year}) ⭐ {rating}\n"
                    if len(items) > 20:
                        result += f"  ... and {len(items) - 20} more\n"
                        
                elif hub_type == "show":
                    result += f"**TV Shows ({len(items)} found):**\n"
                    for item in items[:15]:
                        title = item.get("title", "Unknown")
                        year = item.get("year", "N/A")
                        result += f"  • {title} ({year})\n"
                        
                elif hub_type == "actor" or hub_type == "director":
                    result += f"**{hub_type.title()}s:**\n"
                    for item in items[:5]:
                        name = item.get("title", "Unknown")
                        result += f"  • {name}\n"

            return result

        except Exception as e:
            return f"Error searching Plex: {str(e)}"

    def search_by_actor(self, actor_name: str) -> str:
        """
        Search for movies and TV shows featuring a specific actor.
        Use this when users ask for content with a specific actor/actress.
        This provides more complete results than general search.

        :param actor_name: Name of the actor to search for
        :return: All movies and shows featuring that actor
        """
        try:
            # Find the actor in Plex
            response = requests.get(
                f"{self.valves.PLEX_URL}/hubs/search",
                headers=self._get_headers(),
                params={"query": actor_name, "limit": 10},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Find actor hub - actors are returned in "Directory" not "Metadata"
            actor_keys = []
            hubs = data.get("MediaContainer", {}).get("Hub", [])
            
            for hub in hubs:
                if hub.get("type") == "actor":
                    items = hub.get("Directory", [])
                    
                    # Build candidates for fuzzy matching
                    candidates = [(item.get("tag", ""), item) for item in items]
                    matches = self._fuzzy_match(actor_name, candidates, threshold=0.65)
                    
                    for name, item, score in matches:
                        actor_keys.append({
                            "key": item.get("key"),
                            "name": name,
                            "section": item.get("librarySectionTitle", "Unknown"),
                            "count": item.get("count", 0)
                        })
                    break

            if not actor_keys:
                return f"Actor '{actor_name}' not found in Plex library. Try checking the spelling."
            
            # Use the best matching actor
            best_match = actor_keys[0]
            matched_name = best_match.get("name", actor_name)

            all_movies = []
            all_shows = []
            
            # Get content from each library section
            for actor_info in actor_keys:
                try:
                    response = requests.get(
                        f"{self.valves.PLEX_URL}{actor_info['key']}",
                        headers=self._get_headers(),
                        timeout=30
                    )
                    response.raise_for_status()
                    data = response.json()

                    items = data.get("MediaContainer", {}).get("Metadata", [])
                    for item in items:
                        if item.get("type") == "movie":
                            all_movies.append(item)
                        elif item.get("type") == "show":
                            all_shows.append(item)
                except:
                    continue  # Skip failed sections silently

            total = len(all_movies) + len(all_shows)
            
            if total == 0:
                return f"No content found featuring {matched_name}."

            # Note if we corrected the name
            correction_note = ""
            if matched_name.lower() != actor_name.lower():
                correction_note = f" *(searched for '{actor_name}')*"
            
            result = f"Content featuring **{matched_name}**{correction_note} ({total} total):\n\n"
            
            if all_movies:
                result += f"**Movies ({len(all_movies)}):**\n"
                for movie in sorted(all_movies, key=lambda x: x.get("year", 0), reverse=True)[:25]:
                    title = movie.get("title", "Unknown")
                    year = movie.get("year", "N/A")
                    rating = movie.get("rating", None)
                    rating_str = f"⭐ {rating:.1f}" if isinstance(rating, (int, float)) else ""
                    result += f"  • {title} ({year}) {rating_str}\n"
                if len(all_movies) > 25:
                    result += f"  ... and {len(all_movies) - 25} more movies\n"
                    
            if all_shows:
                result += f"\n**TV Shows ({len(all_shows)}):**\n"
                for show in all_shows[:10]:
                    title = show.get("title", "Unknown")
                    year = show.get("year", "N/A")
                    result += f"  • {title} ({year})\n"

            return result

        except Exception as e:
            return f"Error searching for actor: {str(e)}"

    def search_by_director(self, director_name: str) -> str:
        """
        Search for movies and TV shows by a specific director.
        Use this when users ask for content directed by someone.

        :param director_name: Name of the director to search for
        :return: All movies and shows directed by that person
        """
        try:
            # Find the director in Plex
            response = requests.get(
                f"{self.valves.PLEX_URL}/hubs/search",
                headers=self._get_headers(),
                params={"query": director_name, "limit": 10},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Find director hub
            director_keys = []
            hubs = data.get("MediaContainer", {}).get("Hub", [])
            
            for hub in hubs:
                if hub.get("type") == "director":
                    items = hub.get("Directory", [])
                    
                    # Build candidates for fuzzy matching
                    candidates = [(item.get("tag", ""), item) for item in items]
                    matches = self._fuzzy_match(director_name, candidates, threshold=0.65)
                    
                    for name, item, score in matches:
                        director_keys.append({
                            "key": item.get("key"),
                            "name": name,
                            "section": item.get("librarySectionTitle", "Unknown"),
                            "count": item.get("count", 0)
                        })
                    break

            if not director_keys:
                return f"Director '{director_name}' not found in Plex library. Try checking the spelling."
            
            # Use the best matching director
            best_match = director_keys[0]
            matched_name = best_match.get("name", director_name)

            all_movies = []
            all_shows = []
            
            # Get content from each library section
            for director_info in director_keys:
                try:
                    response = requests.get(
                        f"{self.valves.PLEX_URL}{director_info['key']}",
                        headers=self._get_headers(),
                        timeout=30
                    )
                    response.raise_for_status()
                    data = response.json()

                    items = data.get("MediaContainer", {}).get("Metadata", [])
                    for item in items:
                        if item.get("type") == "movie":
                            all_movies.append(item)
                        elif item.get("type") == "show":
                            all_shows.append(item)
                except:
                    continue

            total = len(all_movies) + len(all_shows)
            
            if total == 0:
                return f"No content found directed by {matched_name}."

            # Note if we corrected the name
            correction_note = ""
            if matched_name.lower() != director_name.lower():
                correction_note = f" *(searched for '{director_name}')*"
            
            result = f"Content directed by **{matched_name}**{correction_note} ({total} total):\n\n"
            
            if all_movies:
                result += f"**Movies ({len(all_movies)}):**\n"
                for movie in sorted(all_movies, key=lambda x: x.get("year", 0), reverse=True)[:25]:
                    title = movie.get("title", "Unknown")
                    year = movie.get("year", "N/A")
                    rating = movie.get("rating", None)
                    rating_str = f"⭐ {rating:.1f}" if isinstance(rating, (int, float)) else ""
                    result += f"  • {title} ({year}) {rating_str}\n"
                if len(all_movies) > 25:
                    result += f"  ... and {len(all_movies) - 25} more movies\n"
                    
            if all_shows:
                result += f"\n**TV Shows ({len(all_shows)}):**\n"
                for show in all_shows[:10]:
                    title = show.get("title", "Unknown")
                    year = show.get("year", "N/A")
                    result += f"  • {title} ({year})\n"

            return result

        except Exception as e:
            return f"Error searching for director: {str(e)}"

    def get_recently_added(self, limit: int = 15) -> str:
        """
        Get recently added content from Plex.
        Use this when users ask about new additions or what's new.

        :param limit: Maximum number of items to return (default 15)
        :return: Recently added movies and TV episodes
        """
        try:
            response = requests.get(
                f"{self.valves.PLEX_URL}/library/recentlyAdded",
                headers=self._get_headers(),
                params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": limit},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("MediaContainer", {}).get("Metadata", [])
            
            if not items:
                return "No recently added content found."

            result = "Recently added to Plex:\n\n"
            
            for item in items:
                item_type = item.get("type", "unknown")
                title = item.get("title", "Unknown")
                
                if item_type == "movie":
                    year = item.get("year", "N/A")
                    result += f"🎬 **{title}** ({year})\n"
                    
                elif item_type == "episode":
                    show = item.get("grandparentTitle", "Unknown Show")
                    season = item.get("parentIndex", 0)
                    episode = item.get("index", 0)
                    result += f"📺 **{show}** S{season:02d}E{episode:02d} - {title}\n"
                    
                elif item_type == "season":
                    show = item.get("parentTitle", "Unknown Show")
                    season = item.get("index", 0)
                    result += f"📺 **{show}** Season {season}\n"

            return result

        except Exception as e:
            return f"Error fetching recently added: {str(e)}"

    def get_on_deck(self) -> str:
        """
        Get the "On Deck" queue - shows/movies in progress.
        Use this when users ask what they were watching or continue watching.

        :return: List of in-progress content
        """
        try:
            response = requests.get(
                f"{self.valves.PLEX_URL}/library/onDeck",
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("MediaContainer", {}).get("Metadata", [])
            
            if not items:
                return "Nothing currently on deck (no in-progress content)."

            result = "On Deck (continue watching):\n\n"
            
            for item in items[:10]:
                item_type = item.get("type", "unknown")
                title = item.get("title", "Unknown")
                
                if item_type == "movie":
                    year = item.get("year", "N/A")
                    view_offset = item.get("viewOffset", 0) / 60000  # Convert to minutes
                    duration = item.get("duration", 0) / 60000
                    result += f"🎬 **{title}** ({year}) - {view_offset:.0f}/{duration:.0f} min\n"
                    
                elif item_type == "episode":
                    show = item.get("grandparentTitle", "Unknown")
                    season = item.get("parentIndex", 0)
                    episode = item.get("index", 0)
                    result += f"📺 **{show}** S{season:02d}E{episode:02d} - {title}\n"

            return result

        except Exception as e:
            return f"Error fetching on deck: {str(e)}"
