"""Telling the time anywhere in the world."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from livekit.agents import ToolError, function_tool

from tools.base import ToolBase


class ClockTools(ToolBase):
    @function_tool
    async def get_current_time(self, timezone: str) -> str:
        """Get the current date and time somewhere in the world.

        Args:
            timezone: The place's IANA time zone, such as "Europe/London" or "America/Chicago"
        """
        try:
            now = datetime.now(ZoneInfo(timezone))
        except (ZoneInfoNotFoundError, ValueError):
            raise ToolError(
                f"{timezone!r} isn't a time zone. Use an IANA name such as America/Chicago."
            ) from None
        hour = now.hour % 12 or 12
        meridiem = "AM" if now.hour < 12 else "PM"
        return f"It's {hour}:{now:%M} {meridiem} on {now:%A, %B} {now.day} in {timezone}."
