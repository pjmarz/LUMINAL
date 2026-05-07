"""
title: Midnight Plex Tool
author: Peter Marino
description: Unified search and library access for Plex Media Server
required_open_webui_version: 0.4.0
requirements: requests, pydantic
version: 2.0.0
licence: MIT
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field

# === BEGIN inlined from midnight/_shared.py — DO NOT EDIT, regenerate via build_tools.py ===
from difflib import SequenceMatcher


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
        self._section_cache = {}

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            "X-Plex-Token": self.valves.PLEX_TOKEN,
            "Accept": "application/json"
        }

    def _get_section_id(self, section_type: str) -> Optional[str]:
        """Get the Plex library section ID for a given type (movie/show)."""
        if section_type in self._section_cache:
            return self._section_cache[section_type]

        try:
            response = requests.get(
                f"{self.valves.PLEX_URL}/library/sections",
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            sections = data.get("MediaContainer", {}).get("Directory", [])

            for section in sections:
                if section.get("type") == section_type:
                    key = section.get("key")
                    if key:
                        self._section_cache[section_type] = key
                        return key
        except Exception:
            return None

        return None

    async def search_plex(self, query: str, __event_emitter__=None) -> str:
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

    async def search_by_actor(self, actor_name: str, __event_emitter__=None) -> str:
        """
        Search for movies and TV shows featuring a specific actor.
        Use this when users ask for content with a specific actor/actress.
        This provides more complete results than general search.

        :param actor_name: Name of the actor to search for
        :return: All movies and shows featuring that actor
        """
        await emit_status(__event_emitter__, f"Searching Plex for actor '{actor_name}'…")
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
                    matches = fuzzy_match(actor_name, candidates, threshold=0.65)
                    
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
            section_errors = []

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
                except Exception as e:
                    section_errors.append(f"{actor_info.get('section', 'Unknown')}: {e}")

            total = len(all_movies) + len(all_shows)

            if total == 0 and section_errors:
                return f"Plex error fetching actor results: {'; '.join(section_errors)}"

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

            if section_errors:
                result += f"\n⚠️ Partial results — {len(section_errors)} section(s) unreachable: {'; '.join(section_errors)}"

            return result

        except Exception as e:
            return f"Error searching for actor: {str(e)}"
        finally:
            await emit_status(__event_emitter__, "Done", done=True)

    async def search_by_director(self, director_name: str, __event_emitter__=None) -> str:
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
                    matches = fuzzy_match(director_name, candidates, threshold=0.65)
                    
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
            section_errors = []

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
                except Exception as e:
                    section_errors.append(f"{director_info.get('section', 'Unknown')}: {e}")

            total = len(all_movies) + len(all_shows)

            if total == 0 and section_errors:
                return f"Plex error fetching director results: {'; '.join(section_errors)}"

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

            if section_errors:
                result += f"\n⚠️ Partial results — {len(section_errors)} section(s) unreachable: {'; '.join(section_errors)}"

            return result

        except Exception as e:
            return f"Error searching for director: {str(e)}"

    async def get_cast(self, title: str, limit: int = 10, __event_emitter__=None) -> str:
        """
        Get the cast of a movie or TV show.
        Use this when users ask "who's in [title]?", "cast of [title]", or "who starred in [title]?".

        :param title: The movie or TV show title (e.g., "2012", "Breaking Bad")
        :param limit: Maximum number of cast members to return (default 10)
        :return: List of actors and their roles in the title
        """
        try:
            # Search for the title in Plex
            response = requests.get(
                f"{self.valves.PLEX_URL}/hubs/search",
                headers=self._get_headers(),
                params={"query": title, "limit": 10},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            hubs = data.get("MediaContainer", {}).get("Hub", [])
            
            # Find the best matching movie or show
            best_match = None
            match_type = None
            
            for hub in hubs:
                hub_type = hub.get("type", "")
                items = hub.get("Metadata", [])
                
                if hub_type in ("movie", "show") and items:
                    # Build candidates for fuzzy matching
                    candidates = [(item.get("title", ""), item) for item in items]
                    matches = fuzzy_match(title, candidates, threshold=0.5)
                    
                    if matches:
                        best_match = matches[0][1]  # Get the item data
                        match_type = hub_type
                        break
            
            if not best_match:
                return f"No movie or TV show found matching '{title}' in Plex library."
            
            # Get the rating key to fetch full metadata with cast
            rating_key = best_match.get("ratingKey")
            if not rating_key:
                return f"Found '{best_match.get('title')}' but couldn't retrieve cast information."
            
            # Fetch full metadata (XML endpoint gives us Role data)
            metadata_response = requests.get(
                f"{self.valves.PLEX_URL}/library/metadata/{rating_key}",
                headers={"X-Plex-Token": self.valves.PLEX_TOKEN, "Accept": "application/json"},
                timeout=30
            )
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            
            item_data = metadata.get("MediaContainer", {}).get("Metadata", [])
            if not item_data:
                return f"Could not retrieve details for '{title}'."
            
            item = item_data[0]
            item_title = item.get("title", title)
            item_year = item.get("year", "N/A")
            roles = item.get("Role", [])
            
            if not roles:
                return f"No cast information available for '{item_title}' ({item_year})."
            
            # Build the result
            type_emoji = "🎬" if match_type == "movie" else "📺"
            result = f"{type_emoji} **Cast of \"{item_title}\" ({item_year}):**\n\n"
            
            for i, role in enumerate(roles[:limit], 1):
                actor_name = role.get("tag", "Unknown Actor")
                character = role.get("role", "Unknown Role")
                result += f"{i}. **{actor_name}** as {character}\n"
            
            if len(roles) > limit:
                result += f"\n*... and {len(roles) - limit} more cast members*"
            
            return result

        except Exception as e:
            return f"Error fetching cast: {str(e)}"

    async def get_recently_added(self, limit: int = 15, media_type: str = "all", __event_emitter__=None) -> str:
        """
        Get recently added content from Plex.
        Use this when users ask about new additions or what's new.

        :param limit: Maximum number of items to return (default 15)
        :param media_type: Filter by type - "movies", "episodes", "shows", or "all" (default "all")
        :return: Recently added movies and/or TV content
        """
        await emit_status(__event_emitter__, f"Fetching recently added {media_type}…")
        try:
            media_type_lower = media_type.lower()
            items = []
            
            # For episodes specifically, query the TV section with type=4 (episode)
            # The generic /library/recentlyAdded only returns seasons, not individual episodes
            if media_type_lower == "episodes":
                section_id = self._get_section_id("show")
                if not section_id:
                    return "Error: Could not find a Plex TV library section for episodes."
                response = requests.get(
                    f"{self.valves.PLEX_URL}/library/sections/{section_id}/recentlyAdded",
                    headers=self._get_headers(),
                    params={"type": 4, "X-Plex-Container-Size": limit},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                items = data.get("MediaContainer", {}).get("Metadata", [])
                
            # For movies specifically, query the Movies section
            elif media_type_lower == "movies":
                section_id = self._get_section_id("movie")
                if not section_id:
                    return "Error: Could not find a Plex movie library section."
                response = requests.get(
                    f"{self.valves.PLEX_URL}/library/sections/{section_id}/recentlyAdded",
                    headers=self._get_headers(),
                    params={"X-Plex-Container-Size": limit},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                items = data.get("MediaContainer", {}).get("Metadata", [])
                
            # For shows/tv/series or "all", use the generic endpoint
            else:
                fetch_limit = limit * 2 if media_type_lower in ("shows", "tv", "series") else limit
                response = requests.get(
                    f"{self.valves.PLEX_URL}/library/recentlyAdded",
                    headers=self._get_headers(),
                    params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": fetch_limit},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                items = data.get("MediaContainer", {}).get("Metadata", [])
                
                # Filter for TV content if requested
                if media_type_lower in ("shows", "tv", "series"):
                    items = [i for i in items if i.get("type") in ("episode", "season", "show")]
            
            # Limit results
            items = items[:limit]
            
            if not items:
                return f"No recently added {media_type} found."

            type_label = {"movies": "movies", "episodes": "episodes", "shows": "TV shows", "tv": "TV shows", "series": "TV shows"}.get(media_type_lower, "content")
            result = f"Recently added {type_label} to Plex:\n\n"
            
            for item in items:
                item_type = item.get("type", "unknown")
                title = item.get("title", "Unknown")
                
                # Format the added date
                added_at = item.get("addedAt", 0)
                if added_at:
                    from datetime import datetime
                    added_date = datetime.fromtimestamp(added_at).strftime("%b %d, %Y")
                else:
                    added_date = "Unknown"
                
                if item_type == "movie":
                    year = item.get("year", "N/A")
                    result += f"🎬 **{title}** ({year}) — added {added_date}\n"
                    
                elif item_type == "episode":
                    show = item.get("grandparentTitle", "Unknown Show")
                    season = item.get("parentIndex", 0)
                    episode = item.get("index", 0)
                    result += f"📺 **{show}** S{season:02d}E{episode:02d} - {title} — added {added_date}\n"
                    
                elif item_type == "season":
                    show = item.get("parentTitle", "Unknown Show")
                    season = item.get("index", 0)
                    result += f"📺 **{show}** Season {season} — added {added_date}\n"

            return result

        except Exception as e:
            return f"Error fetching recently added: {str(e)}"
        finally:
            await emit_status(__event_emitter__, "Done", done=True)

    async def get_on_deck(self, __event_emitter__=None) -> str:
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

    async def get_episode_details(self, episode_title: str, show_name: str = "", __event_emitter__=None) -> str:
        """
        Get detailed information about a specific TV episode including synopsis.
        Use this when users ask "what's this episode about?" or want episode details.
        Tolerant of typos in show_name via fuzzy matching against Plex results.

        :param episode_title: Title of the episode (e.g., "The Pirate Dinner")
        :param show_name: Optional show name to narrow search (e.g., "Landman")
        :return: Episode details including synopsis, air date, duration
        """
        try:
            # Normalize curly quotes to straight quotes (common user input issue)
            episode_title = episode_title.replace("'", "'").replace("'", "'")
            episode_title = episode_title.replace(""", '"').replace(""", '"')
            if show_name:
                show_name = show_name.replace("'", "'").replace("'", "'")

            # Search for the episode in the TV section.
            # Plex's section search is already fuzzy server-side for the query string.
            section_id = self._get_section_id("show")
            if not section_id:
                return "Error: Could not find a Plex TV library section."
            response = requests.get(
                f"{self.valves.PLEX_URL}/library/sections/{section_id}/search",
                headers=self._get_headers(),
                params={"type": 4, "query": episode_title},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("MediaContainer", {}).get("Metadata", [])

            if not items:
                return f"No episode found matching '{episode_title}'."

            # If show_name provided, fuzzy-match against grandparentTitle so typos
            # ("BoBs Burgers", "Better Caul Saul") still find the right show.
            corrected_show = ""
            if show_name:
                candidates = [(i.get("grandparentTitle", ""), i) for i in items]
                matches = fuzzy_match(show_name, candidates, threshold=0.6)
                items = [item for _, item, _ in matches]
                if matches and matches[0][0].lower() != show_name.lower():
                    corrected_show = matches[0][0]

            if not items:
                return f"No episode '{episode_title}' found for show '{show_name}'."

            # Use the best match (first result)
            ep = items[0]
            
            show = ep.get("grandparentTitle", "Unknown Show")
            season = ep.get("parentIndex", 0)
            episode_num = ep.get("index", 0)
            title = ep.get("title", "Unknown")
            summary = ep.get("summary", "No synopsis available.")
            duration_ms = ep.get("duration", 0)
            duration_min = duration_ms // 60000 if duration_ms else 0
            air_date = ep.get("originallyAvailableAt", "Unknown")
            rating = ep.get("rating", None)
            
            result = f"**{show}** - S{season:02d}E{episode_num:02d}: {title}\n\n"
            if corrected_show:
                result += f"*(matched show '{corrected_show}', you searched for '{show_name}')*\n\n"
            result += f"📅 **Air Date:** {air_date}\n"
            result += f"⏱️ **Duration:** {duration_min} minutes\n"
            if rating:
                result += f"⭐ **Rating:** {rating:.1f}\n"
            result += f"\n**Synopsis:**\n{summary}"

            return result

        except Exception as e:
            return f"Error fetching episode details: {str(e)}"
