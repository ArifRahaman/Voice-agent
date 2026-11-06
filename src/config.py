"""All settings and constants for the voice agent (instructions live in prompts.py)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / ".env.local")

# Frontends, phone numbers and the Agent Console ask LiveKit for the agent by this name
AGENT_NAME = "assistant"

# --- Hosting ---
HOSTED = os.getenv("HOSTED", "").strip().lower() in ("1", "true", "yes")

# --- Voice ---
TTS_VOICE = "37e65973-9d96-5aab-adcd-01bf56ab5af9"  # Kyla
ASSISTANT_NAME = "Kyla"

# --- Speech-to-text ---
STT_MODE = "balanced"
VAD_THRESHOLD = 0.4
STT_KEYTERMS = [ASSISTANT_NAME]

# --- LLM ---
LLM_MODEL = "gemma-4-31b"
LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1"

OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")

# --- Web search ---
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"

# --- GitHub ---
GITHUB_API = "https://api.github.com"

# --- Gemini vision ---
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_API_REVISION = "2026-05-20"
GEMINI_MODELS = (
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
)
GEMINI_TIMEOUT = 30

# --- Email ---
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
IMAP_HOST = "imap.gmail.com"

# --- Screen ---
SCREENSHOT_WIDTH = 1600

# --- App name maps ---
MACOS = sys.platform == "darwin"

APP_COMMANDS = {
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "file explorer": "explorer",
    "explorer": "explorer",
    "files": "explorer",
    "command prompt": "cmd",
    "cmd": "cmd",
    "task manager": "taskmgr",
    "wordpad": "write",
}

APP_COMMANDS_MAC = {
    "notepad": "TextEdit",
    "textedit": "TextEdit",
    "wordpad": "TextEdit",
    "notes": "Notes",
    "calculator": "Calculator",
    "calc": "Calculator",
    "paint": "Preview",
    "preview": "Preview",
    "file explorer": "Finder",
    "explorer": "Finder",
    "files": "Finder",
    "finder": "Finder",
    "command prompt": "Terminal",
    "cmd": "Terminal",
    "terminal": "Terminal",
    "task manager": "Activity Monitor",
    "activity monitor": "Activity Monitor",
    "music": "Music",
    "safari": "Safari",
}

SITES = {
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "whatsapp": "https://web.whatsapp.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "spotify": "https://open.spotify.com",
    "amazon": "https://www.amazon.com",
    "wikipedia": "https://www.wikipedia.org",
    "netflix": "https://www.netflix.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
}
