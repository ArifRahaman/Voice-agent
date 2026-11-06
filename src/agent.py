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

import logging
import os

from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    cli,
)
from livekit.plugins import assemblyai, openai, silero

from assistant import Assistant
from config import (
    AGENT_NAME,
    LLM_GATEWAY_URL,
    LLM_MODEL,
    OPENROUTER_MODEL,
    OPENROUTER_URL,
    STT_KEYTERMS,
    STT_MODE,
    TTS_VOICE,
    VAD_THRESHOLD,
)

logger = logging.getLogger("agent")


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
