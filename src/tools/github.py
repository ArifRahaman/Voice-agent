"""GitHub: summarizing a repository, its open pull requests and contributors."""

from __future__ import annotations

import asyncio
import logging

from livekit.agents import function_tool

from services.github import ago, github_get, parse_repo, say_count
from tools.base import ToolBase

logger = logging.getLogger("agent")


class GitHubTools(ToolBase):
    @function_tool
    async def github_repo_summary(self, repo: str) -> str:
        """Look up a GitHub repository: what it is, how popular it is, its open pull
        requests and who opened them, and its top contributors.

        Use this whenever someone asks about a repository or project on GitHub, who is
        working on it, or what pull requests are open. Summarize it in a sentence or two
        unless they ask for the whole list.

        Args:
            repo: The repository as "owner/name", like "facebook/react". A full GitHub
                URL works too.
        """
        slug = parse_repo(repo)
        info, pulls, contributors = await asyncio.gather(
            asyncio.to_thread(github_get, f"/repos/{slug}"),
            asyncio.to_thread(
                github_get,
                f"/repos/{slug}/pulls?state=open&sort=updated&direction=desc&per_page=5",
            ),
            asyncio.to_thread(github_get, f"/repos/{slug}/contributors?per_page=5"),
            return_exceptions=True,
        )
        if isinstance(info, BaseException):
            raise info
        if isinstance(pulls, BaseException):
            pulls = []
        if isinstance(contributors, BaseException):
            contributors = []

        about = (info.get("description") or "no description given").rstrip(" .")
        lines = [
            f"{info.get('full_name', slug)}: {about}.",
            f"Mainly {info.get('language') or 'several languages'}, with "
            f"{say_count(info.get('stargazers_count', 0))} stars, "
            f"{say_count(info.get('forks_count', 0))} forks and "
            f"{say_count(info.get('open_issues_count', 0))} open issues and pull "
            f"requests. Last pushed {ago(info.get('pushed_at') or '')}.",
        ]
        if pulls:
            lines.append("Open pull requests, most recently updated first:")
            for pr in pulls:
                author = (pr.get("user") or {}).get("login") or "someone"
                draft = ", still a draft" if pr.get("draft") else ""
                lines.append(
                    f"- number {pr.get('number')}, \"{pr.get('title')}\", opened by "
                    f"{author} {ago(pr.get('created_at') or '')}{draft}"
                )
        else:
            lines.append("It has no open pull requests right now.")
        if contributors:
            lines.append(
                "Top contributors: "
                + ", ".join(
                    f"{c.get('login')} with "
                    f"{say_count(c.get('contributions', 0))} commits"
                    for c in contributors
                )
                + "."
            )
        logger.info("github_repo_summary: %s (%d open PRs)", slug, len(pulls))
        return "\n".join(lines)
