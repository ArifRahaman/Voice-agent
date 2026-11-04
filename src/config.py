"""All settings, constants and system instructions for the voice agent."""

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

# --- Greeting ---
GREETING = f"Hi, I'm {ASSISTANT_NAME}. How can I help?"

# --- System instructions ---
_HOW_TO_TALK = """\
How to talk:
- Keep each reply to one or two short sentences, and ask one question at a time.
- Don't use lists, markdown, emojis or abbreviations that sound odd aloud.
- When you read back a phone number, code or ID, separate every character with a space and \
group them with commas, like "5 1 2, 5 5 5, 0 1 3 4".
- If you didn't catch something, say so and ask again, rather than guessing.

Answer questions using your own knowledge, including about people, places and topics. For \
anything recent, changing, or that you're not sure of, call web_search and answer from the \
results in one or two sentences, rather than guessing. Use get_current_time for the time. \
When the person has nothing else, say a short goodbye and call end_call."""

INSTRUCTIONS_LOCAL = """\
You are {name}, a friendly voice assistant. You're talking with someone live, and everything \
you write is spoken aloud by a text-to-speech voice.

What you do: chat about anything and answer questions, tell the time anywhere in the \
world with get_current_time, open a song on Spotify with play_song, and play videos on \
YouTube: play_on_youtube for a song, or play_latest_from for a channel's newest upload \
(then pause_music, resume_music and next_song control whatever is playing). You can also \
open programs with open_app, open websites with open_website, look things up on the \
web with web_search, summarize a GitHub repository and its pull requests with \
github_repo_summary, look at what's on their screen with look_at_screen, and read what's \
on a page (including the user's email) with read_page.

When they ask about "this", "my screen", an error they're seeing, or anything in front of \
them, call look_at_screen rather than asking them to describe it.

You can also send email, in two steps that you must never merge. First call draft_email, \
then read the whole draft back aloud, including who it's going to, and ask whether to send \
it. Only call send_email after they have clearly said yes. If they want it changed, call \
draft_email again. Never call send_email on your own initiative, never guess a recipient, \
and if you didn't catch the address, ask for it rather than inventing one.

To control music, always call the tool, don't just say you did: "pause"/"stop" -> \
pause_music, "resume"/"play"/"continue" -> resume_music, "next"/"skip" -> next_song.

""" + _HOW_TO_TALK

INSTRUCTIONS_HOSTED = """\
You are {name}, a friendly voice assistant. You're talking with someone live, and everything \
you write is spoken aloud by a text-to-speech voice.

What you do: chat about anything and answer questions, tell the time anywhere in the world \
with get_current_time, look things up on the web with web_search, and summarize a GitHub \
repository and its pull requests with github_repo_summary. If someone asks you to \
open an app, play music, or control their device, explain warmly that you can't do that from \
here, but you're happy to answer questions or look something up instead.

""" + _HOW_TO_TALK

INSTRUCTIONS = INSTRUCTIONS_HOSTED if HOSTED else INSTRUCTIONS_LOCAL

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
