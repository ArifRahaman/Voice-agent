"""Opening programs and websites."""

from __future__ import annotations

import logging
import subprocess
import webbrowser

from livekit.agents import ToolError, function_tool

from config import APP_COMMANDS, APP_COMMANDS_MAC, MACOS
from tools.base import ToolBase, site_url

logger = logging.getLogger("agent")


class AppTools(ToolBase):
    @function_tool
    async def open_app(self, app: str) -> str:
        """Open a program on this computer, like Notepad or Calculator.

        Args:
            app: The program name, like "Notepad", "Calculator" or "Paint".
        """
        self._require_local("open programs")
        name = app.strip().lower()
        if MACOS:
            command = ["open", "-a", APP_COMMANDS_MAC.get(name, app.strip())]
        else:
            command = APP_COMMANDS.get(name, name)
        try:
            subprocess.Popen(command)
        except Exception:
            raise ToolError(f"Couldn't open {app}.") from None
        logger.info("open_app: %s", command)
        return f"Opening {app}."

    @function_tool
    async def open_website(self, site: str) -> str:
        """Open a website in the browser, like Gmail or YouTube, or any URL.

        Args:
            site: A site name like "Gmail", or an address like "github.com".
        """
        self._require_local("open websites")
        url = site_url(site)
        webbrowser.open(url)
        logger.info("open_website: %s", url)
        return f"Opening {site}."
