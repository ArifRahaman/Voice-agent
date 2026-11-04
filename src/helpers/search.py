"""Web search: Firecrawl (when a key is set) with DuckDuckGo fallback."""

from __future__ import annotations

import html
import json
import logging
import os
import re
import urllib.parse
import urllib.request

from config import FIRECRAWL_SEARCH_URL

logger = logging.getLogger("agent")


def _firecrawl_search(query: str) -> list[str]:
    api_key = os.getenv("FIRECRAWL_API_KEY")
    body = json.dumps({"query": query, "limit": 5}).encode("utf-8")
    req = urllib.request.Request(
        FIRECRAWL_SEARCH_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    data = json.loads(raw)
    results = []
    for item in (data.get("data") or {}).get("web", []):
        title = (item.get("title") or "").strip()
        desc = (item.get("description") or "").strip()
        line = f"{title}: {desc}" if title and desc else title or desc
        if line:
            results.append(line)
    return results[:5]


def _ddg_search(query: str) -> list[str]:
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    snippets = re.findall(r"class=['\"]result-snippet['\"][^>]*>(.*?)</td>", raw, re.S)
    cleaned = [html.unescape(re.sub("<[^>]+>", "", s)).strip() for s in snippets]
    return [s for s in cleaned if s][:5]


def web_search(query: str) -> list[str]:
    """Search with Firecrawl when a key is configured, else fall back to DuckDuckGo."""
    if os.getenv("FIRECRAWL_API_KEY"):
        try:
            results = _firecrawl_search(query)
            if results:
                return results
            logger.warning("Firecrawl returned no results; falling back to DuckDuckGo")
        except Exception as e:
            logger.warning("Firecrawl search failed (%s); falling back to DuckDuckGo", e)
    return _ddg_search(query)
