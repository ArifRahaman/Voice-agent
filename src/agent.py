"""A voice agent starter where every model is AssemblyAI's, on one API key.

- Text-to-speech: AssemblyAI streaming TTS, with word-level timings
- Speech-to-text: Universal-3.6 Pro streaming, which also decides when the user has finished
  their turn
- LLM: LLM Gateway, an OpenAI-compatible API for models from Google, OpenAI, Anthropic and more

Each setting below names the skill in skills/ that explains when and how to change it.

    uv run src/agent.py console   # talk to the agent in your terminal
    uv run src/agent.py dev       # connect it to LiveKit Cloud, for a web or phone frontend
"""

from __future__ import annotations

import asyncio
import base64
import html
import io
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    ToolError,
    TurnHandlingOptions,
    cli,
    function_tool,
)
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import assemblyai, openai, silero

try:
    # Only needed for the browser tools (YouTube, read_page), which run on your own
    # machine. A hosted server doesn't install Playwright, and those tools are off there.
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

load_dotenv(Path(__file__).parents[1] / ".env.local")

logger = logging.getLogger("agent")

# Frontends, phone numbers and the Agent Console ask LiveKit for the agent by this name
AGENT_NAME = "assistant"

# --- Hosting ---
# Set HOSTED=1 in the environment when running on a server (LiveKit Cloud, Docker, a VPS).
# It switches OFF the tools that control THIS computer (opening apps, Spotify, YouTube,
# reading pages) because there's no desktop on a server, and keeps the ones that work
# anywhere (web_search and get_current_time). On your laptop, leave it unset for everything.
HOSTED = os.getenv("HOSTED", "").strip().lower() in ("1", "true", "yes")

# --- Voice: skills/tts-voice ---

# A voice id from https://www.assemblyai.com/docs/tts/voices, or one of your cloned voices
TTS_VOICE = "37e65973-9d96-5aab-adcd-01bf56ab5af9"  # Kyla

# The agent introduces itself by the voice's name; if you change one, change the other
ASSISTANT_NAME = "Kyla"

# --- Speech-to-text ---

# How quickly a turn ends versus how accurate the transcript is: "min_latency", "balanced"
# or "max_accuracy". See skills/turn-detection.
STT_MODE = "balanced"

# How loud speech must be to count, for transcription and for interrupting the agent. The
# STT and Silero use the same value. See skills/interruptions-and-vad.
# On speakers rather than headphones, the mic picks up the agent's own voice; the echo
# arrives quieter than real speech, so a higher bar here stops it being heard as a reply.
# Lower it towards 0.2 if your own quiet speech gets missed.
VAD_THRESHOLD = 0.4

# Names and terms the STT should spell right. See skills/keyterms-and-prompt.
STT_KEYTERMS = [ASSISTANT_NAME]

# --- LLM: skills/llm-model ---

# Any model from https://llm-gateway.assemblyai.com/v1/models that supports tools
LLM_MODEL = "gemma-4-31b"
LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1"

# --- Web search: Firecrawl ---

# web_search uses Firecrawl when FIRECRAWL_API_KEY is set in .env.local (cleaner,
# more reliable results), and falls back to the DuckDuckGo scrape when it isn't.
# Get a key at https://www.firecrawl.dev/app/api-keys.
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"

# --- GitHub ---
# github_repo_summary needs no key for public repos (60 requests an hour per IP).
# Set GITHUB_TOKEN in .env.local to raise that to 5000 an hour and to read private repos.
GITHUB_API = "https://api.github.com"

# --- Seeing the screen ---
# look_at_screen sends a screenshot to Google's Gemini API, which needs its own free key:
# the models on the AssemblyAI gateway's free plan don't accept images at all.
# Get one at https://aistudio.google.com/apikey and set GEMINI_API_KEY in .env.local.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_API_REVISION = "2026-05-20"

# Any flash model is liable to answer 503 "high demand" for a minute at a time, so these
# are tried in turn, most consistently available first, and the whole list is retried once.
GEMINI_MODELS = (
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
)

# A working answer takes about 8 seconds, so 30 is generous; an overloaded model refuses
# in under a second, which is what keeps walking the whole list cheap.
GEMINI_TIMEOUT = 30

# Screenshots are shrunk to this width before upload: wide enough to read on-screen text,
# small enough that the round trip doesn't leave a silence in the conversation.
SCREENSHOT_WIDTH = 1600

GREETING = f"Hi, I'm {ASSISTANT_NAME}. How can I help?"

# How to talk is the same everywhere; what the agent can DO differs by where it runs.
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

# On a laptop: the full assistant, including tools that drive this computer.
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

To control music, always call the tool, don't just say you did: "pause"/"stop" -> \
pause_music, "resume"/"play"/"continue" -> resume_music, "next"/"skip" -> next_song.

""" + _HOW_TO_TALK

# When hosted on a server: only the tools that work anywhere. No computer to drive.
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


# Friendly app names -> the command that launches them on Windows.
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

MACOS = sys.platform == "darwin"

# The same friendly names on a Mac, where apps are launched by name with `open -a`.
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

# Friendly site names -> their URLs.
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


def _firecrawl_search(query: str) -> list[str]:
    """Search the web through Firecrawl, returning the top results as text lines."""
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


def _grab_screen_jpeg() -> bytes:
    """Capture every monitor as one JPEG, shrunk for a fast upload."""
    # Imported here, not at the top: a hosted server has no screen and no Pillow.
    from PIL import Image, ImageGrab

    img = ImageGrab.grab(all_screens=True).convert("RGB")
    if img.width > SCREENSHOT_WIDTH:
        height = round(img.height * SCREENSHOT_WIDTH / img.width)
        img = img.resize((SCREENSHOT_WIDTH, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _ask_gemini_about_image(prompt: str, jpeg: bytes) -> str:
    """Send an image and a question to Gemini, returning the answer as text."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ToolError(
            "I can't see the screen, because no vision key is set up yet."
        )
    image = {
        "type": "image",
        "data": base64.b64encode(jpeg).decode(),
        "mime_type": "image/jpeg",
    }
    why = "busy"
    for attempt in range(2):
        if attempt:
            time.sleep(1.5)  # a spike in demand is usually over in a moment
        for model in GEMINI_MODELS:
            req = urllib.request.Request(
                GEMINI_URL,
                data=json.dumps(
                    {"model": model, "input": [{"type": "text", "text": prompt}, image]}
                ).encode("utf-8"),
                method="POST",
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                    "Api-Revision": GEMINI_API_REVISION,
                },
            )
            try:
                raw = urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT).read()
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "ignore")[:200]
                logger.warning("Gemini %s failed: %s %s", model, e.code, detail)
                if e.code in (401, 403):
                    raise ToolError(
                        "The vision key was rejected, so I can't see the screen."
                    )
                # 503 and 429 mean this model is overloaded; another usually isn't
                why = f"error {e.code}"
                continue
            except OSError as e:  # timeout, DNS, connection reset
                logger.warning("Gemini %s unreachable: %s", model, e)
                why = "no answer"
                continue
            # The answer is the text blocks of the model's output step
            blocks = [
                block.get("text", "")
                for step in json.loads(raw).get("steps", [])
                for block in (step.get("content") or [])
                if block.get("type") == "text"
            ]
            answer = " ".join(b.strip() for b in blocks if b.strip())
            if answer:
                logger.info("look_at_screen answered by %s", model)
                return answer
            why = "an empty answer"
    raise ToolError(f"I couldn't get a look at the screen just now ({why}).")


def _github_get(path: str):
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


def _parse_repo(text: str) -> str:
    """Turn what someone said or pasted into an "owner/name" repository slug."""
    t = text.strip()
    t = re.sub(r"^https?://", "", t, flags=re.I)
    t = re.sub(r"^(www\.)?github\.com/", "", t, flags=re.I)
    # Spoken aloud, "owner/repo" arrives as "owner slash repo" or just "owner repo"
    t = re.sub(r"\s*\bslash\b\s*", "/", t, flags=re.I)
    t = t.strip("/ ").removesuffix(".git")
    if "/" not in t:
        t = re.sub(r"\s+", "/", t, count=1)
    # Anything after owner/name (like a /pulls path) is dropped
    parts = [p.strip() for p in t.split("/") if p.strip()][:2]
    if len(parts) != 2:
        raise ToolError(
            "I need both the owner and the repository name, like facebook slash react."
        )
    return "/".join(parts)


def _say_count(n: int) -> str:
    """Round a big number to something that sounds natural spoken aloud."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".removesuffix(".0") + " million"
    if n >= 1000:
        return f"{n / 1000:.1f}".removesuffix(".0") + " thousand"
    return str(n)


def _ago(iso: str) -> str:
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


def _ddg_search(query: str) -> list[str]:
    """Fetch the top result snippets from DuckDuckGo's lightweight endpoint."""
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    snippets = re.findall(r"class=['\"]result-snippet['\"][^>]*>(.*?)</td>", raw, re.S)
    cleaned = [html.unescape(re.sub("<[^>]+>", "", s)).strip() for s in snippets]
    return [s for s in cleaned if s][:5]


def _web_search(query: str) -> list[str]:
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


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=INSTRUCTIONS.format(name=ASSISTANT_NAME),
            # Lets the agent hang up after saying goodbye, but not during the greeting
            tools=[EndCallTool(ignore_on_enter=True)],
        )
        # A Playwright browser we drive: plays/pauses YouTube and reads pages.
        # A persistent profile keeps logins (like Gmail) between runs.
        self._pw = None
        self._ctx = None
        self._page = None

    async def on_enter(self) -> None:
        # A fixed greeting is spoken right away, without waiting on the LLM
        self.session.say(GREETING)

    def _require_local(self, what: str) -> None:
        # Tools that drive this computer only make sense when the agent runs on the
        # user's own machine. When HOSTED, refuse politely instead of acting on the server.
        if HOSTED:
            raise ToolError(
                f"I can't {what} from here, since I'm running on a server. "
                "I can still answer questions or look things up for you."
            )

    @function_tool
    async def get_current_time(self, timezone: str) -> str:
        """Get the current date and time somewhere in the world.

        Args:
            timezone: The place's IANA time zone, such as "Europe/London" or "America/Chicago"
        """
        try:
            now = datetime.now(ZoneInfo(timezone))
        except (ZoneInfoNotFoundError, ValueError):
            raise ToolError(
                f"{timezone!r} isn't a time zone. Use an IANA name such as America/Chicago."
            ) from None
        hour = now.hour % 12 or 12
        meridiem = "AM" if now.hour < 12 else "PM"
        return f"It's {hour}:{now:%M} {meridiem} on {now:%A, %B} {now.day} in {timezone}."

    @function_tool
    async def play_song(self, song: str) -> str:
        """Open Spotify in the web browser to play a song.

        Args:
            song: The song to play, like "Numb by Linkin Park" or "Bohemian Rhapsody"
        """
        self._require_local("open Spotify")
        # Opens the Spotify web player at a search for this song, in the user's
        # default browser (where they are signed in). They press play on the result.
        url = "https://open.spotify.com/search/" + urllib.parse.quote(song)
        webbrowser.open(url)
        return f"Opening Spotify for {song}. Press play on the top result."

    async def _browser_page(self):
        # Start a Playwright browser the first time it's needed, and reuse it.
        # launch_persistent_context stores cookies in a profile folder, so a site
        # you sign into (like Gmail) stays signed in the next time.
        if self._page is not None:
            return self._page
        if async_playwright is None:
            raise ToolError("The browser isn't available here (Playwright isn't installed).")
        profile_dir = Path(__file__).parents[1] / ".browser-profile"
        self._pw = await async_playwright().start()
        self._ctx = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        return self._page

    @function_tool
    async def play_on_youtube(self, song: str) -> str:
        """Play a song on YouTube. Afterwards pause_music, resume_music and next_song control it.

        Args:
            song: The song to play, like "Numb by Linkin Park" or "Bohemian Rhapsody"
        """
        self._require_local("play YouTube")
        page = await self._browser_page()
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(song)
        await page.goto(url)
        # Dismiss the cookie/consent dialog if YouTube shows one.
        for label in ("Accept all", "Reject all", "I agree"):
            try:
                btn = page.get_by_role("button", name=label)
                if await btn.count():
                    await btn.first.click(timeout=2000)
                    break
            except Exception:
                pass
        # Clicking the first result is also the gesture that lets it play with sound.
        await page.wait_for_selector("ytd-video-renderer a#video-title", timeout=20000)
        await page.locator("ytd-video-renderer a#video-title").first.click()
        return f"Playing {song} on YouTube."

    @function_tool
    async def play_latest_from(self, channel: str) -> str:
        """Open a YouTube channel's page and play its latest (newest) video.

        Args:
            channel: The channel or creator name, like "MrBeast" or "Veritasium"
        """
        self._require_local("play YouTube")
        page = await self._browser_page()
        # Search filtered to channels (sp=EgIQAg%3D%3D), then open that channel.
        await page.goto(
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(channel) + "&sp=EgIQAg%3D%3D"
        )
        for label in ("Accept all", "Reject all", "I agree"):
            try:
                btn = page.get_by_role("button", name=label)
                if await btn.count():
                    await btn.first.click(timeout=2000)
                    break
            except Exception:
                pass
        await page.wait_for_selector("ytd-channel-renderer a#main-link", timeout=20000)
        href = await page.locator("ytd-channel-renderer a#main-link").first.get_attribute("href")
        if not href:
            raise ToolError(f"Couldn't find a channel called {channel}.")
        # The Videos tab lists newest first, so the first item is the latest upload.
        await page.goto("https://www.youtube.com" + href.rstrip("/") + "/videos")
        newest = '#contents ytd-rich-item-renderer a[href*="/watch"]'
        await page.wait_for_selector(newest, timeout=20000)
        await page.locator(newest).first.click()
        await page.wait_for_selector("video", timeout=20000)

        # YouTube is a single-page app: wait for the tab title to become the video's.
        title = ""
        try:
            await page.wait_for_function(
                "document.title && document.title !== 'YouTube'", timeout=5000
            )
            t = await page.title()
            title = t[:-10] if t.endswith(" - YouTube") else t
        except Exception:
            pass
        logger.info("play_latest_from: %s -> %s", channel, title or "(unknown)")
        return f"Playing the latest from {channel}" + (f": {title}." if title else ".")

    @function_tool
    async def pause_music(self) -> str:
        """Pause the playing YouTube video. Call this whenever the user says pause or stop."""
        if self._page is None:
            raise ToolError("Nothing is playing yet.")
        # Prefer YouTube's own player API; fall back to the raw video element.
        await self._page.evaluate(
            "const p = document.getElementById('movie_player');"
            "if (p && p.pauseVideo) { p.pauseVideo(); }"
            "else { const v = document.querySelector('video'); if (v) v.pause(); }"
        )
        logger.info("pause_music: paused")
        return "Paused."

    @function_tool
    async def resume_music(self) -> str:
        """Resume the paused YouTube video. Call this when the user says resume, play or continue."""
        if self._page is None:
            raise ToolError("Nothing is playing yet.")
        await self._page.evaluate(
            "const p = document.getElementById('movie_player');"
            "if (p && p.playVideo) { p.playVideo(); }"
            "else { const v = document.querySelector('video'); if (v) v.play(); }"
        )
        logger.info("resume_music: resumed")
        return "Resumed."

    @function_tool
    async def next_song(self) -> str:
        """Skip to the next video on YouTube."""
        if self._page is None:
            raise ToolError("Nothing is playing yet.")
        try:
            await self._page.locator("a.ytp-next-button").first.click(timeout=3000)
        except Exception:
            # Fall back to YouTube's keyboard shortcut for "next".
            await self._page.keyboard.press("Shift+KeyN")
        return "Skipping to the next one."

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
        key = site.strip().lower()
        if key in SITES:
            url = SITES[key]
        elif "." in key and " " not in key:
            url = key if key.startswith("http") else "https://" + key
        else:
            # Unknown name: fall back to a Google search for it.
            url = "https://www.google.com/search?q=" + urllib.parse.quote(site)
        webbrowser.open(url)
        logger.info("open_website: %s", url)
        return f"Opening {site}."

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
    async def look_at_screen(self, question: str) -> str:
        """Look at what's on the user's screen right now and answer about it.

        Use this whenever they ask what's on their screen, what an error message says,
        what they're looking at, or to read something in front of them. Answer from what
        comes back, in one or two spoken sentences.

        Args:
            question: What to find out, like "what error is shown?", "what's on my
                screen?" or "what does this code do?"
        """
        self._require_local("see your screen")
        # The LLM sometimes passes junk like ":" instead of the real question
        if len(re.sub(r"[^a-z]", "", question.lower())) < 3:
            question = "What is on the screen?"
        # Don't speak a filler line here: on speakers the mic hears it, the STT
        # transcribes it as the user, and that phantom turn interrupts the real answer.
        jpeg = await asyncio.to_thread(_grab_screen_jpeg)
        prompt = (
            "This is a screenshot of the user's computer screen. Answer their question "
            "in one or two short sentences, written to be read aloud, with no markdown "
            f"or lists. Their question: {question}"
        )
        answer = await asyncio.to_thread(_ask_gemini_about_image, prompt, jpeg)
        logger.info("look_at_screen: %s (%d KB)", question, len(jpeg) // 1024)
        return answer

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
        slug = _parse_repo(repo)
        info, pulls, contributors = await asyncio.gather(
            asyncio.to_thread(_github_get, f"/repos/{slug}"),
            asyncio.to_thread(
                _github_get,
                f"/repos/{slug}/pulls?state=open&sort=updated&direction=desc&per_page=5",
            ),
            asyncio.to_thread(_github_get, f"/repos/{slug}/contributors?per_page=5"),
            # A repo with no commits has no contributors, and pulls can be restricted;
            # neither should sink the whole summary.
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
            f"{_say_count(info.get('stargazers_count', 0))} stars, "
            f"{_say_count(info.get('forks_count', 0))} forks and "
            f"{_say_count(info.get('open_issues_count', 0))} open issues and pull "
            f"requests. Last pushed {_ago(info.get('pushed_at') or '')}.",
        ]
        if pulls:
            lines.append("Open pull requests, most recently updated first:")
            for pr in pulls:
                author = (pr.get("user") or {}).get("login") or "someone"
                draft = ", still a draft" if pr.get("draft") else ""
                lines.append(
                    f"- number {pr.get('number')}, \"{pr.get('title')}\", opened by "
                    f"{author} {_ago(pr.get('created_at') or '')}{draft}"
                )
        else:
            lines.append("It has no open pull requests right now.")
        if contributors:
            lines.append(
                "Top contributors: "
                + ", ".join(
                    f"{c.get('login')} with "
                    f"{_say_count(c.get('contributions', 0))} commits"
                    for c in contributors
                )
                + "."
            )
        logger.info("github_repo_summary: %s (%d open PRs)", slug, len(pulls))
        return "\n".join(lines)

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
        key = site.strip().lower()
        if key in SITES:
            url = SITES[key]
        elif "." in key and " " not in key:
            url = key if key.startswith("http") else "https://" + key
        else:
            url = "https://www.google.com/search?q=" + urllib.parse.quote(site)
        await page.goto(url)
        await page.wait_for_timeout(2500)  # let dynamic pages finish loading
        text = await page.evaluate("document.body ? document.body.innerText : ''")
        text = re.sub(r"\n{3,}", "\n\n", (text or "")).strip()
        if not text:
            raise ToolError(f"Couldn't read anything from {site}.")
        logger.info("read_page: %s (%d chars)", site, len(text))
        return f"Content from {site} (summarize the key points aloud):\n{text[:3000]}"

    async def aclose_browser(self) -> None:
        # Close the Playwright browser when the agent shuts down.
        try:
            if self._ctx is not None:
                await self._ctx.close()
            if self._pw is not None:
                await self._pw.stop()
        except Exception:
            pass


def llm_gateway(model: str = LLM_MODEL) -> openai.LLM:
    """An LLM served by AssemblyAI's LLM Gateway, through its OpenAI-compatible API."""
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise ValueError("Set ASSEMBLYAI_API_KEY in .env.local or the environment")
    return openai.LLM(model=model, base_url=LLM_GATEWAY_URL, api_key=api_key)


server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load(activation_threshold=VAD_THRESHOLD)


server.setup_fnc = prewarm


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}

    tts = assemblyai.TTS(voice=TTS_VOICE)
    # Open the TTS connection now, so the greeting doesn't wait on the handshake
    tts.prewarm()

    session = AgentSession(
        stt=assemblyai.STT(
            model="universal-3-6-pro",
            mode=STT_MODE,
            vad_threshold=VAD_THRESHOLD,
            keyterms_prompt=STT_KEYTERMS,
            # More building blocks, off by default. Each skill says when to use it.
            # voice_focus="near-field",     # background noise: skills/voice-focus
            # prompt="...",                 # what calls are about: skills/keyterms-and-prompt
            # language_codes=["en", "es"],  # expected languages: skills/languages
            # domain="medical-v1",          # medical vocabulary: skills/medical-mode
        ),
        llm=llm_gateway(),
        tts=tts,
        vad=ctx.proc.userdata["vad"],
        turn_handling=TurnHandlingOptions(
            # Universal-3.6 Pro decides when the user has finished speaking...
            turn_detection="stt",
            # ...so LiveKit shouldn't add its own delay on top
            endpointing={"min_delay": 0},
            # A cough or an "uh-huh" pauses the reply instead of cutting it off
            interruption={"resume_false_interruption": True},
        ),
        tts_text_transforms=["filter_emoji", "filter_markdown"],
        # When the user interrupts, keep only the words they heard in the chat history,
        # using the TTS's word timings
        use_tts_aligned_transcript=True,
    )

    async def log_usage() -> None:
        logger.info("usage: %s", session.usage)

    ctx.add_shutdown_callback(log_usage)

    assistant = Assistant()
    # Make sure the YouTube browser is closed when the agent stops.
    ctx.add_shutdown_callback(assistant.aclose_browser)

    await session.start(agent=assistant, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
