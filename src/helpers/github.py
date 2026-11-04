"""GitHub API helpers: fetch repos, parse spoken repo names, format numbers."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime

from livekit.agents import ToolError

from config import AGENT_NAME, GITHUB_API


def github_get(path: str):
    """GET a GitHub API path and return the parsed JSON."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": AGENT_NAME}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{GITHUB_API}{path}", headers=headers)
    try:
        raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ToolError("I couldn't find that repository on GitHub.")
        if e.code in (401, 403):
            raise ToolError(
                "GitHub turned that request down, which usually means too many requests "
                "in one hour. It should work again shortly."
            )
        raise ToolError(f"GitHub returned an error, code {e.code}.")
    return json.loads(raw)


def parse_repo(text: str) -> str:
    """Turn what someone said or pasted into an "owner/name" repository slug."""
    t = text.strip()
    t = re.sub(r"^https?://", "", t, flags=re.I)
    t = re.sub(r"^(www\.)?github\.com/", "", t, flags=re.I)
    t = re.sub(r"\s*\bslash\b\s*", "/", t, flags=re.I)
    t = t.strip("/ ").removesuffix(".git")
    if "/" not in t:
        t = re.sub(r"\s+", "/", t, count=1)
    parts = [p.strip() for p in t.split("/") if p.strip()][:2]
    if len(parts) != 2:
        raise ToolError(
            "I need both the owner and the repository name, like facebook slash react."
        )
    return "/".join(parts)


def say_count(n: int) -> str:
    """Round a big number to something that sounds natural spoken aloud."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".removesuffix(".0") + " million"
    if n >= 1000:
        return f"{n / 1000:.1f}".removesuffix(".0") + " thousand"
    return str(n)


def ago(iso: str) -> str:
    """Describe a GitHub timestamp in words, like "today" or "3 days ago"."""
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "recently"
    days = (datetime.now(tz=when.tzinfo) - when).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    if days < 365:
        months = days // 30
        return "last month" if months == 1 else f"{months} months ago"
    years = days // 365
    return "about a year ago" if years == 1 else f"about {years} years ago"
