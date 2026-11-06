"""Seeing the user's screen."""

from __future__ import annotations

import asyncio
import logging
import re

from livekit.agents import function_tool

from services.vision import ask_gemini_about_image, grab_screen_jpeg
from tools.base import ToolBase

logger = logging.getLogger("agent")


class VisionTools(ToolBase):
    @function_tool
    async def look_at_screen(self, question: str) -> str:
        """Look at what's on the user's screen right now and answer about it.

        Use this whenever they ask what's on their screen, what an error message says,
        what they're looking at, or to read something in front of them. Answer from what
        comes back, in one or two spoken sentences.

        Args:
            question: What to find out, like "what error is shown?", "what's on my
                screen?" or "what does this code do?"
        """
        self._require_local("see your screen")
        if len(re.sub(r"[^a-z]", "", question.lower())) < 3:
            question = "What is on the screen?"
        jpeg = await asyncio.to_thread(grab_screen_jpeg)
        prompt = (
            "This is a screenshot of the user's computer screen. Answer their question "
            "in one or two short sentences, written to be read aloud, with no markdown "
            f"or lists. Their question: {question}"
        )
        answer = await asyncio.to_thread(ask_gemini_about_image, prompt, jpeg)
        logger.info("look_at_screen: %s (%d KB)", question, len(jpeg) // 1024)
        return answer
