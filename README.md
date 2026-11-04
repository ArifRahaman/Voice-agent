# Voice Agent (AssemblyAI + LiveKit)

A live voice assistant. One AssemblyAI key powers all three models:
speech-to-text (Universal-3.6 Pro), the LLM (via AssemblyAI's gateway), and
text-to-speech. You talk to it in your terminal.

```
voice-agent/
├── src/agent.py        The agent
├── .env.local          Your key (git-ignored)
├── .env.local.example  Template
├── requirements.txt    Dependencies (pip)
└── pyproject.toml      Dependencies (uv)
```

## 1. Get an AssemblyAI key

Sign up at https://www.assemblyai.com/app and copy an API key. Then open
`.env.local` and replace the placeholder:

```
ASSEMBLYAI_API_KEY=your-real-key
```

## 2. Install

### With plain Python (you have this)

From the `voice-agent/` folder:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux, activate it with `source .venv/bin/activate` instead.

(On the next sessions you only need the activate line again.)

### Or with uv (if you install it later)

```bash
uv sync
```

## 3. First run: download the local models

The agent uses a small on-device model for voice activity. Download it once:

```bash
python -m livekit.agents download-files
```

## 4. Talk to it

```bash
python src/agent.py console
```

Speak into your mic; it replies out loud. Say goodbye and it hangs up.
Press Ctrl+C to quit.

(With uv, prefix the commands with `uv run`, e.g. `uv run src/agent.py console`.)

## Optional keys, and what each one unlocks

Only `ASSEMBLYAI_API_KEY` is required. The rest are free and add a tool each;
see `.env.local.example` for where to get them.

| Key | Unlocks | Without it |
|---|---|---|
| `FIRECRAWL_API_KEY` | Cleaner `web_search` results | Falls back to a DuckDuckGo scrape |
| `GEMINI_API_KEY` | `look_at_screen` — answers questions about what's on screen | The tool says it can't see |
| `GITHUB_TOKEN` | Private repos in `github_repo_summary`, 5000 calls/hour | Public repos only, 60/hour |

`look_at_screen` needs its own key because the models on AssemblyAI's free
gateway plan don't accept images at all.

## Running on a Mac

Everything works, with two differences:

- **Screen recording permission.** The first time `look_at_screen` runs, macOS
  asks to allow screen recording for your terminal. Grant it in System Settings
  → Privacy & Security → Screen Recording, then restart the terminal, or the
  screenshot comes back blank.
- **App names map automatically.** `open_app` translates the friendly names to
  Mac apps, so "Notepad" opens TextEdit and "Task Manager" opens Activity
  Monitor. Anything not in the list is passed to `open -a` as spoken.

## Use headphones

On speakers, the mic hears the agent's own voice, the transcriber files it as
your turn, and the agent answers itself — you get doubled replies. Headphones
remove this entirely. `VAD_THRESHOLD` raises the bar that echo has to clear,
but it's a mitigation, not a cure.

## What you can change

Each setting at the top of `src/agent.py` has a short comment:

- `TTS_VOICE` / `ASSISTANT_NAME` — the voice and the name it introduces itself with.
- `STT_MODE` — `"min_latency"`, `"balanced"`, or `"max_accuracy"`.
- `VAD_THRESHOLD` — how loud speech must be to register.
- `LLM_MODEL` — any tool-capable model from the AssemblyAI LLM gateway.

## Modes

- `console` — runs fully on your machine; needs only `ASSEMBLYAI_API_KEY`.
- `dev` — connects to LiveKit Cloud for a web or phone frontend; also needs the
  `LIVEKIT_*` values in `.env.local`.

## Notes

- This project is separate from `turbo-app`; nothing here touches that.
- Package versions are unpinned. If an import fails after install, the LiveKit
  API may have shifted — pin the versions from AssemblyAI's starter, or tell me
  the error and I'll align them.
