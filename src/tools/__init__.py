"""Tool groups the LLM can call, one file per topic."""

from tools.apps import AppTools
from tools.clock import ClockTools
from tools.github import GitHubTools
from tools.mail import MailTools
from tools.media import MediaTools
from tools.system import SystemTools
from tools.vision import VisionTools
from tools.web import WebTools

__all__ = [
    "AppTools",
    "ClockTools",
    "GitHubTools",
    "MailTools",
    "MediaTools",
    "SystemTools",
    "VisionTools",
    "WebTools",
]
