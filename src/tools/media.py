"""Music and video: Spotify, YouTube, and pause / resume / next."""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser

from livekit.agents import ToolError, function_tool

from tools.base import ToolBase

logger = logging.getLogger("agent")


class MediaTools(ToolBase):
    @function_tool
    async def play_song(self, song: str) -> str:
        """Open Spotify in the web browser to play a song.

        Args:
            song: The song to play, like "Numb by Linkin Park" or "Bohemian Rhapsody"
        """
        self._require_local("open Spotify")
        url = "https://open.spotify.com/search/" + urllib.parse.quote(song)
        webbrowser.open(url)
        return f"Opening Spotify for {song}. Press play on the top result."

    @function_tool
    async def play_on_youtube(self, song: str) -> str:
        """Play a song on YouTube. Afterwards pause_music, resume_music and next_song control it.

        Args:
            song: The song to play, like "Numb by Linkin Park" or "Bohemian Rhapsody"
        """
        self._require_local("play YouTube")
        page = await self._browser_page()
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(song)
        await page.goto(url)
        for label in ("Accept all", "Reject all", "I agree"):
            try:
                btn = page.get_by_role("button", name=label)
                if await btn.count():
                    await btn.first.click(timeout=2000)
                    break
            except Exception:
                pass
        await page.wait_for_selector("ytd-video-renderer a#video-title", timeout=20000)
        await page.locator("ytd-video-renderer a#video-title").first.click()
        return f"Playing {song} on YouTube."

    @function_tool
    async def play_latest_from(self, channel: str) -> str:
        """Open a YouTube channel's page and play its latest (newest) video.

        Args:
            channel: The channel or creator name, like "MrBeast" or "Veritasium"
        """
        self._require_local("play YouTube")
        page = await self._browser_page()
        await page.goto(
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(channel) + "&sp=EgIQAg%3D%3D"
        )
        for label in ("Accept all", "Reject all", "I agree"):
            try:
                btn = page.get_by_role("button", name=label)
                if await btn.count():
                    await btn.first.click(timeout=2000)
                    break
            except Exception:
                pass
        await page.wait_for_selector("ytd-channel-renderer a#main-link", timeout=20000)
        href = await page.locator("ytd-channel-renderer a#main-link").first.get_attribute("href")
        if not href:
            raise ToolError(f"Couldn't find a channel called {channel}.")
        await page.goto("https://www.youtube.com" + href.rstrip("/") + "/videos")
        newest = '#contents ytd-rich-item-renderer a[href*="/watch"]'
        await page.wait_for_selector(newest, timeout=20000)
        await page.locator(newest).first.click()
        await page.wait_for_selector("video", timeout=20000)

        title = ""
        try:
            await page.wait_for_function(
                "document.title && document.title !== 'YouTube'", timeout=5000
            )
            t = await page.title()
            title = t[:-10] if t.endswith(" - YouTube") else t
        except Exception:
            pass
        logger.info("play_latest_from: %s -> %s", channel, title or "(unknown)")
        return f"Playing the latest from {channel}" + (f": {title}." if title else ".")

    @function_tool
    async def pause_music(self) -> str:
        """Pause the playing YouTube video. Call this whenever the user says pause or stop."""
        if self._page is None:
            raise ToolError("Nothing is playing yet.")
        await self._page.evaluate(
            "const p = document.getElementById('movie_player');"
            "if (p && p.pauseVideo) { p.pauseVideo(); }"
            "else { const v = document.querySelector('video'); if (v) v.pause(); }"
        )
        logger.info("pause_music: paused")
        return "Paused."

    @function_tool
    async def resume_music(self) -> str:
        """Resume the paused YouTube video. Call this when the user says resume, play or continue."""
        if self._page is None:
            raise ToolError("Nothing is playing yet.")
        await self._page.evaluate(
            "const p = document.getElementById('movie_player');"
            "if (p && p.playVideo) { p.playVideo(); }"
            "else { const v = document.querySelector('video'); if (v) v.play(); }"
        )
        logger.info("resume_music: resumed")
        return "Resumed."

    @function_tool
    async def next_song(self) -> str:
        """Skip to the next video on YouTube."""
        if self._page is None:
            raise ToolError("Nothing is playing yet.")
        try:
            await self._page.locator("a.ytp-next-button").first.click(timeout=3000)
        except Exception:
            await self._page.keyboard.press("Shift+KeyN")
        return "Skipping to the next one."
