"""
title: Plexy Tautulli Tool
description: Viewing analytics and activity monitoring via Tautulli
author: Peter Marino
version: 1.2.0
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """Tautulli analytics tools for Plexy."""

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

    def _api_call(self, cmd: str, params: dict = None) -> dict:
        """Make Tautulli API call."""
        try:
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
        except Exception as e:
            return {}

    def get_activity(self) -> str:
        """
        Get current Plex activity - who's watching what right now.
        Use this when users ask who's watching, what's playing, or current streams.

        :return: Current streaming activity
        """
        data = self._api_call("get_activity")
        
        if not data:
            return "Error: Could not fetch activity from Tautulli."

        sessions = data.get("sessions", [])
        stream_count = data.get("stream_count", 0)

        if stream_count == 0:
            return "🔴 No one is currently watching anything on Plex."

        result = f"🟢 **{stream_count} active stream(s)**:\n\n"

        for session in sessions:
            user = session.get("friendly_name", "Unknown")
            title = session.get("title", "Unknown")
            media_type = session.get("media_type", "unknown")
            state = session.get("state", "unknown")
            player = session.get("player", "Unknown device")
            progress = session.get("progress_percent", 0)
            
            state_icon = "▶️" if state == "playing" else "⏸️"
            
            if media_type == "movie":
                year = session.get("year", "")
                result += f"{state_icon} **{user}** watching **{title}** ({year})\n"
            elif media_type == "episode":
                show = session.get("grandparent_title", "Unknown")
                season = session.get("parent_media_index", 0)
                episode = session.get("media_index", 0)
                result += f"{state_icon} **{user}** watching **{show}** S{season:02d}E{episode:02d}\n"
            else:
                result += f"{state_icon} **{user}** playing **{title}**\n"
                
            result += f"   📱 {player} | {progress}% complete\n"

        return result

    def get_watch_history(self, count: int = 15) -> str:
        """
        Get recent watch history from Plex.
        Use this when users ask what was watched recently or viewing history.

        :param count: Number of history items to show (default 15)
        :return: Recent watch history
        """
        data = self._api_call("get_history", {"length": count})
        
        if not data:
            return "Error: Could not fetch watch history."

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

    def get_most_watched(self, days: int = 30) -> str:
        """
        Get most watched content statistics.
        Use this when users ask about popular content, top watched, or stats.

        :param days: Time period in days (default 30)
        :return: Most watched movies and shows
        """
        result = f"Most watched content (last {days} days):\n\n"

        # Top movies
        data = self._api_call("get_home_stats", {
            "stat_id": "top_movies",
            "stats_count": 5,
            "time_range": days
        })
        
        if data and data.get("rows"):
            result += "**Top Movies:**\n"
            for i, item in enumerate(data.get("rows", [])[:5], 1):
                title = item.get("title", "Unknown")
                year = item.get("year", "")
                plays = item.get("total_plays", 0)
                year_str = f" ({year})" if year else ""
                result += f"  {i}. {title}{year_str} ({plays} plays)\n"

        # Top TV shows
        data = self._api_call("get_home_stats", {
            "stat_id": "top_tv",
            "stats_count": 5,
            "time_range": days
        })
        
        if data and data.get("rows"):
            result += "\n**Top TV Shows:**\n"
            for i, item in enumerate(data.get("rows", [])[:5], 1):
                title = item.get("title", "Unknown")
                plays = item.get("total_plays", 0)
                result += f"  {i}. {title} ({plays} plays)\n"

        # Top users
        data = self._api_call("get_home_stats", {
            "stat_id": "top_users",
            "stats_count": 5,
            "time_range": days
        })
        
        if data and data.get("rows"):
            result += "\n**Most Active Users:**\n"
            for i, item in enumerate(data.get("rows", [])[:5], 1):
                user = item.get("friendly_name", "Unknown")
                plays = item.get("total_plays", 0)
                result += f"  {i}. {user} ({plays} plays)\n"

        return result
