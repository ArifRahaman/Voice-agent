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
import logging
import os
import re
import subprocess
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

from config import (
    AGENT_NAME,
    APP_COMMANDS,
    APP_COMMANDS_MAC,
    ASSISTANT_NAME,
    GREETING,
    HOSTED,
    INSTRUCTIONS,
    LLM_GATEWAY_URL,
    LLM_MODEL,
    MACOS,
    OPENROUTER_MODEL,
    OPENROUTER_URL,
    SITES,
    STT_KEYTERMS,
    STT_MODE,
    TTS_VOICE,
    VAD_THRESHOLD,
)
from helpers.email import (
    contact_email,
    delete_gmail_draft,
    save_gmail_draft,
    smtp_send,
)
from helpers.github import ago, github_get, parse_repo, say_count
from helpers.search import web_search as _web_search
from helpers.vision import ask_gemini_about_image, grab_screen_jpeg

logger = logging.getLogger("agent")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=INSTRUCTIONS.format(name=ASSISTANT_NAME),
            tools=[EndCallTool(ignore_on_enter=True)],
        )
        self._pw = None
        self._ctx = None
        self._page = None
        self._draft: dict[str, str] | None = None

    async def on_enter(self) -> None:
        self.session.say(GREETING)

    def _require_local(self, what: str) -> None:
        if HOSTED:
            raise ToolError(
                f"I can't {what} from here, since I'm running on a server. "
                "I can still answer questions or look things up for you."
            )

    # --- Time ---

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

    # --- Music / YouTube ---

    @function_tool
    async def play_song(self, song: str) -> str:
        """Open Spotify in the web browser to play a song.

        Args:
            song: The song to play, like "Numb by Linkin Park" or "Bohemian Rhapsody"
        """
        self._require_local("open Spotify")
        url = "https://open.spotify.com/search/" + urllib.parse.quote(song)
        webbrowser.open(url)
        return f"Opening Spotify for {song}. Press play on the top result."

    async def _browser_page(self):
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
        for label in ("Accept all", "Reject all", "I agree"):
            try:
                btn = page.get_by_role("button", name=label)
                if await btn.count():
                    await btn.first.click(timeout=2000)
                    break
            except Exception:
                pass
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
        await page.goto("https://www.youtube.com" + href.rstrip("/") + "/videos")
        newest = '#contents ytd-rich-item-renderer a[href*="/watch"]'
        await page.wait_for_selector(newest, timeout=20000)
        await page.locator(newest).first.click()
        await page.wait_for_selector("video", timeout=20000)

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
            await self._page.keyboard.press("Shift+KeyN")
        return "Skipping to the next one."

    # --- Apps / websites ---

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
            url = "https://www.google.com/search?q=" + urllib.parse.quote(site)
        webbrowser.open(url)
        logger.info("open_website: %s", url)
        return f"Opening {site}."

    # --- Web search ---

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

    # --- Email ---

    @function_tool
    async def draft_email(self, to: str, subject: str, body: str) -> str:
        """Write an email and hold it for approval. This does NOT send anything.

        Always call this first when someone wants to send an email. Then read the
        draft back to them and ask whether to send it.

        Args:
            to: Who it's for: "me", or an address like "sam@example.com".
            subject: A short subject line.
            body: What the email should say, in full sentences.
        """
        self._require_local("send email")
        address = contact_email(to)
        if not body.strip():
            raise ToolError("The email needs something in it. What should it say?")
        self._draft = {
            "to": address,
            "subject": subject.strip() or "(no subject)",
            "body": body.strip(),
        }
        in_gmail = ""
        try:
            uid = await asyncio.to_thread(
                save_gmail_draft, address, self._draft["subject"], self._draft["body"]
            )
            self._draft["uid"] = uid or ""
            in_gmail = " It's saved in their Gmail drafts, so they can check it there."
        except Exception as e:
            logger.warning("couldn't save the draft to Gmail: %s", e)
        logger.info("draft_email: to %s", address)
        return (
            f"Drafted, NOT yet sent. To: {address}. Subject: {self._draft['subject']}. "
            f"Body: {self._draft['body']}{in_gmail}\n"
            "Read this back to them and ask whether to send it. Only call send_email "
            "once they have clearly said yes."
        )

    @function_tool
    async def send_email(self) -> str:
        """Send the email that draft_email prepared.

        Only call this after reading the draft back to the user and hearing a clear
        yes. If they want anything changed, call draft_email again instead.
        """
        self._require_local("send email")
        if not self._draft:
            raise ToolError("There's no draft ready. What should the email say?")
        draft = self._draft
        await asyncio.to_thread(
            smtp_send, draft["to"], draft["subject"], draft["body"]
        )
        self._draft = None
        if draft.get("uid"):
            try:
                await asyncio.to_thread(delete_gmail_draft, draft["uid"])
            except Exception as e:
                logger.warning("couldn't remove the saved Gmail draft: %s", e)
        return f"Sent to {draft['to']}."

    # --- Vision ---

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
        if len(re.sub(r"[^a-z]", "", question.lower())) < 3:
            question = "What is on the screen?"
        jpeg = await asyncio.to_thread(grab_screen_jpeg)
        prompt = (
            "This is a screenshot of the user's computer screen. Answer their question "
            "in one or two short sentences, written to be read aloud, with no markdown "
            f"or lists. Their question: {question}"
        )
        answer = await asyncio.to_thread(ask_gemini_about_image, prompt, jpeg)
        logger.info("look_at_screen: %s (%d KB)", question, len(jpeg) // 1024)
        return answer

    # --- GitHub ---

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

    # --- Browser / read page ---

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
        await page.wait_for_timeout(2500)
        text = await page.evaluate("document.body ? document.body.innerText : ''")
        text = re.sub(r"\n{3,}", "\n\n", (text or "")).strip()
        if not text:
            raise ToolError(f"Couldn't read anything from {site}.")
        logger.info("read_page: %s (%d chars)", site, len(text))
        return f"Content from {site} (summarize the key points aloud):\n{text[:3000]}"

    async def aclose_browser(self) -> None:
        try:
            if self._ctx is not None:
                await self._ctx.close()
            if self._pw is not None:
                await self._pw.stop()
        except Exception:
            pass


# --- LLM provider ---


def llm_gateway(model: str = LLM_MODEL) -> openai.LLM:
    """The conversational LLM: OpenRouter when its key is set, else AssemblyAI's gateway.

    Both speak the OpenAI API, so switching is only a different base URL and key.
    """
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        logger.info("LLM: %s via OpenRouter", OPENROUTER_MODEL)
        return openai.LLM(
            model=OPENROUTER_MODEL, base_url=OPENROUTER_URL, api_key=openrouter_key
        )
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise ValueError("Set ASSEMBLYAI_API_KEY in .env.local or the environment")
    logger.info("LLM: %s via AssemblyAI", model)
    return openai.LLM(model=model, base_url=LLM_GATEWAY_URL, api_key=api_key)


# --- Server ---


server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load(activation_threshold=VAD_THRESHOLD)


server.setup_fnc = prewarm


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}

    tts = assemblyai.TTS(voice=TTS_VOICE)
    tts.prewarm()

    session = AgentSession(
        stt=assemblyai.STT(
            model="universal-3-6-pro",
            mode=STT_MODE,
            vad_threshold=VAD_THRESHOLD,
            keyterms_prompt=STT_KEYTERMS,
        ),
        llm=llm_gateway(),
        tts=tts,
        vad=ctx.proc.userdata["vad"],
        turn_handling=TurnHandlingOptions(
            turn_detection="stt",
            endpointing={"min_delay": 0},
            interruption={"resume_false_interruption": True},
        ),
        tts_text_transforms=["filter_emoji", "filter_markdown"],
        use_tts_aligned_transcript=True,
    )

    async def log_usage() -> None:
        logger.info("usage: %s", session.usage)

    ctx.add_shutdown_callback(log_usage)

    assistant = Assistant()
    ctx.add_shutdown_callback(assistant.aclose_browser)

    await session.start(agent=assistant, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
