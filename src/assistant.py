"""The assistant: its instructions, greeting, and every tool group."""

from __future__ import annotations

from livekit.agents import Agent
from livekit.agents.beta.tools import EndCallTool

from config import ASSISTANT_NAME
from prompts import GREETING, INSTRUCTIONS
from tools import (
    AppTools,
    ClockTools,
    GitHubTools,
    MailTools,
    MediaTools,
    SystemTools,
    VisionTools,
    WebTools,
)


# LiveKit finds every @function_tool on the class, including those from these groups.
class Assistant(
    ClockTools,
    MediaTools,
    AppTools,
    SystemTools,
    WebTools,
    MailTools,
    VisionTools,
    GitHubTools,
    Agent,
):
    def __init__(self) -> None:
        super().__init__(
            instructions=INSTRUCTIONS.format(name=ASSISTANT_NAME),
            tools=[EndCallTool(ignore_on_enter=True)],
        )

    async def on_enter(self) -> None:
        self.session.say(GREETING)
