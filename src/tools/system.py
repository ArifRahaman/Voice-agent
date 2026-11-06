"""Controlling the computer: volume, brightness, lock, battery, Do Not Disturb, typing."""

from __future__ import annotations

import asyncio
import logging

from livekit.agents import ToolError, function_tool

from services import system
from tools.base import ToolBase

logger = logging.getLogger("agent")


class SystemTools(ToolBase):
    @function_tool
    async def set_volume(self, level: int) -> str:
        """Set the speaker volume to an exact level. Only use this when the user names a
        number or says "max", "half" and so on; for "louder" or "quieter" use change_volume.

        Args:
            level: The volume from 0 to 100.
        """
        self._require_local("change the volume")
        return await asyncio.to_thread(system.set_volume, max(0, min(100, level)))

    @function_tool
    async def change_volume(self, change: int) -> str:
        """Turn the volume up or down from where it is now. Use this for "louder",
        "quieter", "a bit up" and similar; don't ask the user for a number first.

        Args:
            change: How much to change it, -100 to 100. Use 10 or -10 for "a bit" or
                "slightly", and 25 or -25 for "a lot".
        """
        self._require_local("change the volume")
        if change == 0:
            raise ToolError("Should it go up or down?")
        return await asyncio.to_thread(system.change_volume, max(-100, min(100, change)))

    @function_tool
    async def mute_sound(self, on: bool) -> str:
        """Mute or unmute the computer's sound.

        Args:
            on: True to mute, False to unmute.
        """
        self._require_local("mute the sound")
        return await asyncio.to_thread(system.mute, on)

    @function_tool
    async def set_brightness(self, level: int) -> str:
        """Set the screen brightness.

        Args:
            level: The brightness from 0 to 100.
        """
        self._require_local("change the brightness")
        return await asyncio.to_thread(system.set_brightness, max(0, min(100, level)))

    @function_tool
    async def lock_screen(self) -> str:
        """Lock the computer's screen."""
        self._require_local("lock your screen")
        return await asyncio.to_thread(system.lock_screen)

    @function_tool
    async def battery_status(self) -> str:
        """Check the battery level and whether it's charging."""
        self._require_local("check your battery")
        return await asyncio.to_thread(system.battery_status)

    @function_tool
    async def do_not_disturb(self, on: bool) -> str:
        """Turn Do Not Disturb (Focus) on or off.

        Args:
            on: True to turn it on, False to turn it off.
        """
        self._require_local("change Do Not Disturb")
        return await asyncio.to_thread(system.do_not_disturb, on)

    @function_tool
    async def type_text(self, text: str, app: str = "") -> str:
        """Type text on the keyboard for the user, into an app.

        Use for "type ...", "write ... in Notepad" and "open Notepad and type ...". For
        that last one, call this once with app set; don't call open_app first. Type
        exactly what they dictated, with normal punctuation, and add nothing of your own.

        Args:
            text: The exact text to type. Use a new line for each new line or paragraph.
            app: An app to open first, like "Notepad". Leave empty to type into
                whatever app is already in front.
        """
        self._require_local("type on your computer")
        if not text.strip():
            raise ToolError("What should I type?")
        logger.info("type_text: %d chars into %s", len(text), app or "the front app")
        return await asyncio.to_thread(system.type_text, text, app)
