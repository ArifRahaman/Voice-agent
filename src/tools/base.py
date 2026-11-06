"""Shared by every tool group: the hosted check, site URLs and the browser."""

from __future__ import annotations

import urllib.parse
from pathlib import Path

from livekit.agents import ToolError

try:
    # Only needed for the browser tools, which run on your own machine.
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

from config import HOSTED, SITES


def site_url(site: str) -> str:
    """Turn "Gmail", "github.com" or any phrase into a URL (a Google search as a fallback)."""
    key = site.strip().lower()
    if key in SITES:
        return SITES[key]
    if "." in key and " " not in key:
        return key if key.startswith("http") else "https://" + key
    return "https://www.google.com/search?q=" + urllib.parse.quote(site)


class ToolBase:
    _pw = None
    _ctx = None
    _page = None

    def _require_local(self, what: str) -> None:
        if HOSTED:
            raise ToolError(
                f"I can't {what} from here, since I'm running on a server. "
                "I can still answer questions or look things up for you."
            )

    async def _browser_page(self):
        if self._page is not None:
            return self._page
        if async_playwright is None:
            raise ToolError("The browser isn't available here (Playwright isn't installed).")
        profile_dir = Path(__file__).parents[2] / ".browser-profile"
        self._pw = await async_playwright().start()
        self._ctx = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        return self._page

    async def aclose_browser(self) -> None:
        try:
            if self._ctx is not None:
                await self._ctx.close()
            if self._pw is not None:
                await self._pw.stop()
        except Exception:
            pass
