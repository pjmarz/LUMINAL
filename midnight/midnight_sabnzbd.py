"""
title: Midnight SABnzbd Tool
description: Download queue and history via SABnzbd for Midnight
author: Peter Marino
version: 1.2.0
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """SABnzbd download management tools for Midnight."""

    class Valves(BaseModel):
        """Configuration for SABnzbd API connection."""
        SABNZBD_URL: str = Field(
            default="http://192.168.4.46:8080",
            description="SABnzbd server URL"
        )
        SABNZBD_API_KEY: str = Field(
            default="",
            description="SABnzbd API key"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _api_call(self, mode: str, params: dict = None) -> dict:
        """Make SABnzbd API call."""
        try:
            all_params = {
                "apikey": self.valves.SABNZBD_API_KEY,
                "mode": mode,
                "output": "json"
            }
            if params:
                all_params.update(params)
                
            response = requests.get(
                f"{self.valves.SABNZBD_URL}/api",
                params=all_params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {}

    def get_download_queue(self) -> str:
        """
        Get current download queue from SABnzbd.
        Use this when users ask about pending downloads, what's downloading, or queue status.

        :return: Current download queue with progress
        """
        data = self._api_call("queue")
        
        if not data:
            return "Error: Could not fetch download queue from SABnzbd."

        queue = data.get("queue", {})
        slots = queue.get("slots", [])
        speed = queue.get("speed", "0")
        timeleft = queue.get("timeleft", "0:00:00")
        paused = queue.get("paused", False)

        if not slots:
            status = "⏸️ Paused" if paused else "💤 Idle"
            return f"Download queue is empty. Status: {status}"

        status_icon = "⏸️" if paused else "⬇️"
        result = f"{status_icon} **{len(slots)} item(s) in queue** | Speed: {speed}/s | ETA: {timeleft}\n\n"

        for slot in slots[:10]:
            filename = slot.get("filename", "Unknown")
            percentage = slot.get("percentage", "0")
            size = slot.get("size", "0 MB")
            timeleft = slot.get("timeleft", "Unknown")
            status = slot.get("status", "Unknown")
            
            # Make filename readable
            display_name = filename[:50] + "..." if len(filename) > 50 else filename
            
            if status == "Downloading":
                result += f"⬇️ **{display_name}**\n"
                result += f"   {percentage}% of {size} | ETA: {timeleft}\n"
            else:
                result += f"⏳ **{display_name}** - {status}\n"
                result += f"   {size}\n"

        if len(slots) > 10:
            result += f"\n... and {len(slots) - 10} more items in queue."

        return result

    def get_download_history(self, count: int = 15) -> str:
        """
        Get recent download history from SABnzbd.
        Use this when users ask about completed downloads or what was downloaded.

        :param count: Number of history items to show (default 15)
        :return: Recent download history
        """
        data = self._api_call("history", {"limit": count})
        
        if not data:
            return "Error: Could not fetch download history."

        history = data.get("history", {})
        slots = history.get("slots", [])

        if not slots:
            return "No download history available."

        result = "Recent downloads:\n\n"

        for slot in slots:
            name = slot.get("name", "Unknown")
            status = slot.get("status", "Unknown")
            size = slot.get("size", "0 MB")
            completed = slot.get("completed", 0)
            
            # Parse completion time
            from datetime import datetime
            try:
                completed_date = datetime.fromtimestamp(completed).strftime("%Y-%m-%d %H:%M")
            except:
                completed_date = "Unknown"
            
            # Truncate long names
            display_name = name[:45] + "..." if len(name) > 45 else name
            
            if status == "Completed":
                result += f"✓ **{display_name}**\n"
                result += f"   {size} | Completed: {completed_date}\n"
            elif status == "Failed":
                result += f"✗ **{display_name}** - Failed\n"
            else:
                result += f"? **{display_name}** - {status}\n"

        return result
