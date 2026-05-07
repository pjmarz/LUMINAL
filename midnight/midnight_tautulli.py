"""
title: Midnight Tautulli Tool
author: Peter Marino
description: Viewing analytics and activity monitoring via Tautulli
required_open_webui_version: 0.4.0
requirements: requests, pydantic
version: 2.0.0
licence: MIT
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """Tautulli analytics tools for Midnight."""

    class Valves(BaseModel):
        """Configuration for Tautulli API connection."""
        TAUTULLI_URL: str = Field(
            default="http://192.168.4.46:8181",
            description="Tautulli server URL"
        )
        TAUTULLI_API_KEY: str = Field(
            default="",
            description="Tautulli API key"
        )

    def __init__(self):
        self.valves = self.Valves()

    async def _emit(self, emitter, description: str, done: bool = False) -> None:
        """Send a status event to OpenWebUI if an emitter is wired."""
        if emitter:
            await emitter({
                "type": "status",
                "data": {"description": description, "done": done},
            })

    def _api_call(self, cmd: str, params: dict = None) -> dict:
        """Make Tautulli API call. Raises on transport/HTTP error."""
        all_params = {
            "apikey": self.valves.TAUTULLI_API_KEY,
            "cmd": cmd
        }
        if params:
            all_params.update(params)

        response = requests.get(
            f"{self.valves.TAUTULLI_URL}/api/v2",
            params=all_params,
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("response", {}).get("data", {})

    async def get_activity(self, __user__: dict = None, __event_emitter__=None) -> str:
        """
        Get current Plex activity - who's watching what right now.
        Use this when users ask who's watching, what's playing, or current streams.
        If the active user matches a session's friendly_name, it is highlighted as "you".

        :param __user__: OpenWebUI user context (auto-injected). Used to label "your" stream.
        :return: Current streaming activity
        """
        try:
            data = self._api_call("get_activity")
        except Exception as e:
            return f"Tautulli error: {e}"

        if not data:
            return "Tautulli returned no activity data."

        sessions = data.get("sessions", [])
        stream_count = data.get("stream_count", 0)

        if stream_count == 0:
            return "🔴 No one is currently watching anything on Plex."

        # Resolve the active user's display name for "you" highlighting
        active_user = ""
        if __user__:
            active_user = (
                __user__.get("name")
                or __user__.get("email", "").split("@")[0]
                or ""
            ).lower()

        result = f"🟢 **{stream_count} active stream(s)**:\n\n"

        for session in sessions:
            user = session.get("friendly_name", "Unknown")
            title = session.get("title", "Unknown")
            media_type = session.get("media_type", "unknown")
            state = session.get("state", "unknown")
            player = session.get("player", "Unknown device")
            progress = session.get("progress_percent", 0)

            state_icon = "▶️" if state == "playing" else "⏸️"

            user_label = f"**{user}**"
            if active_user and active_user in user.lower():
                user_label = f"**you** ({user})"

            if media_type == "movie":
                year = session.get("year", "")
                result += f"{state_icon} {user_label} watching **{title}** ({year})\n"
            elif media_type == "episode":
                show = session.get("grandparent_title", "Unknown")
                season = session.get("parent_media_index", 0)
                episode = session.get("media_index", 0)
                result += f"{state_icon} {user_label} watching **{show}** S{season:02d}E{episode:02d}\n"
            else:
                result += f"{state_icon} {user_label} playing **{title}**\n"

            result += f"   📱 {player} | {progress}% complete\n"

        return result

    async def get_watch_history(self, count: int = 15, __event_emitter__=None) -> str:
        """
        Get recent watch history from Plex.
        Use this when users ask what was watched recently or viewing history.

        :param count: Number of history items to show (default 15)
        :return: Recent watch history
        """
        try:
            data = self._api_call("get_history", {"length": count})
        except Exception as e:
            return f"Tautulli error: {e}"

        if not data:
            return "Tautulli returned no history data."

        history = data.get("data", [])
        
        if not history:
            return "No watch history available."

        result = "Recent watch history:\n\n"

        for item in history:
            user = item.get("friendly_name", "Unknown")
            title = item.get("title", "Unknown")
            media_type = item.get("media_type", "unknown")
            watched = item.get("date", "")
            
            if media_type == "movie":
                year = item.get("year", "")
                result += f"🎬 **{user}** watched **{title}** ({year})\n"
            elif media_type == "episode":
                show = item.get("grandparent_title", "Unknown")
                season = item.get("parent_media_index", 0)
                episode = item.get("media_index", 0)
                result += f"📺 **{user}** watched **{show}** S{season:02d}E{episode:02d}\n"
            else:
                result += f"🎵 **{user}** played **{title}**\n"

        return result

    async def get_most_watched(self, days: int = 30, __event_emitter__=None) -> str:
        """
        Get most watched content statistics.
        Use this when users ask about popular content, top watched, or stats.

        :param days: Time period in days (default 30)
        :return: Most watched movies and shows
        """
        await self._emit(__event_emitter__, f"Computing most-watched stats for last {days} days…")
        result = f"Most watched content (last {days} days):\n\n"
        sections_added = 0
        errors = []

        for stat_id, header in (
            ("top_movies", "**Top Movies:**"),
            ("top_tv", "**Top TV Shows:**"),
            ("top_users", "**Most Active Users:**"),
        ):
            try:
                data = self._api_call("get_home_stats", {
                    "stat_id": stat_id,
                    "stats_count": 5,
                    "time_range": days,
                })
            except Exception as e:
                errors.append(f"{stat_id}: {e}")
                continue

            rows = data.get("rows") if data else None
            if not rows:
                continue

            result += ("\n" if sections_added else "") + header + "\n"
            sections_added += 1
            for i, item in enumerate(rows[:5], 1):
                if stat_id == "top_movies":
                    title = item.get("title", "Unknown")
                    year = item.get("year", "")
                    plays = item.get("total_plays", 0)
                    year_str = f" ({year})" if year else ""
                    result += f"  {i}. {title}{year_str} ({plays} plays)\n"
                elif stat_id == "top_tv":
                    title = item.get("title", "Unknown")
                    plays = item.get("total_plays", 0)
                    result += f"  {i}. {title} ({plays} plays)\n"
                else:
                    user = item.get("friendly_name", "Unknown")
                    plays = item.get("total_plays", 0)
                    result += f"  {i}. {user} ({plays} plays)\n"

        if errors and sections_added == 0:
            await self._emit(__event_emitter__, "Tautulli unreachable", done=True)
            return f"Tautulli error: {'; '.join(errors)}"

        if errors:
            result += f"\n⚠️ Partial results — {'; '.join(errors)}"

        await self._emit(__event_emitter__, "Done", done=True)
        return result
