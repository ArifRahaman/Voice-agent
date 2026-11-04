"""Screen capture and Gemini vision API."""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
import urllib.error
import urllib.request

from livekit.agents import ToolError

from config import (
    GEMINI_API_REVISION,
    GEMINI_MODELS,
    GEMINI_TIMEOUT,
    GEMINI_URL,
    SCREENSHOT_WIDTH,
)

logger = logging.getLogger("agent")


def grab_screen_jpeg() -> bytes:
    """Capture every monitor as one JPEG, shrunk for a fast upload."""
    from PIL import Image, ImageGrab

    img = ImageGrab.grab(all_screens=True).convert("RGB")
    if img.width > SCREENSHOT_WIDTH:
        height = round(img.height * SCREENSHOT_WIDTH / img.width)
        img = img.resize((SCREENSHOT_WIDTH, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def ask_gemini_about_image(prompt: str, jpeg: bytes) -> str:
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
            time.sleep(1.5)
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
                why = f"error {e.code}"
                continue
            except OSError as e:
                logger.warning("Gemini %s unreachable: %s", model, e)
                why = "no answer"
                continue
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
