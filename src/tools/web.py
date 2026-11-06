"""The web: searching it, and reading a page in the browser."""

from __future__ import annotations

import asyncio
import logging
import re

from livekit.agents import ToolError, function_tool

from services.search import web_search as _web_search
from tools.base import ToolBase, site_url

logger = logging.getLogger("agent")


class WebTools(ToolBase):
    @function_tool
    async def web_search(self, query: str) -> str:
        """Search the web for current information to answer from.

        Use this for anything recent or that you're unsure of: news, prices, scores,
        dates, "who is the current ...". Summarize the results in your spoken reply;
        don't read the list aloud.

        Args:
            query: What to look up on the web.
        """
        results = await asyncio.to_thread(_web_search, query)
        if not results:
            raise ToolError("The web search came back empty.")
        logger.info("web_search: %s (%d results)", query, len(results))
        return "Top web results:\n- " + "\n- ".join(results)

    @function_tool
    async def read_page(self, site: str) -> str:
        """Open a website and read what's on it, so you can tell the user.

        Use for "open my email and tell me what's there", "what's on the BBC front
        page", and similar. Summarize the key points in your spoken reply. If the text
        looks like a sign-in page, tell the user to sign in once in the browser window.

        Args:
            site: A site name like "Gmail" or "BBC", or a URL.
        """
        self._require_local("read a page in the browser")
        page = await self._browser_page()
        await page.goto(site_url(site))
        await page.wait_for_timeout(2500)
        text = await page.evaluate("document.body ? document.body.innerText : ''")
        text = re.sub(r"\n{3,}", "\n\n", (text or "")).strip()
        if not text:
            raise ToolError(f"Couldn't read anything from {site}.")
        logger.info("read_page: %s (%d chars)", site, len(text))
        return f"Content from {site} (summarize the key points aloud):\n{text[:3000]}"
