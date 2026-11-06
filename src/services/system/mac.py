"""System controls on macOS: AppleScript, pmset and Shortcuts."""

from __future__ import annotations

import re
import shutil
import subprocess
import time

from livekit.agents import ToolError

from config import APP_COMMANDS_MAC

# macOS has no command for Focus; make these two in the Shortcuts app ("Set Focus" action).
DND_ON_SHORTCUT = "Focus On"
DND_OFF_SHORTCUT = "Focus Off"


def _run(*cmd: str) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError) as e:
        raise ToolError(f"That didn't work on this Mac: {e}") from None
    return out.stdout.strip()


def _osascript(script: str) -> str:
    return _run("osascript", "-e", script)


def set_volume(level: int) -> str:
    _osascript(f"set volume output volume {level}")
    return f"Volume set to {level} percent."


def change_volume(delta: int) -> str:
    current = int(_osascript("output volume of (get volume settings)") or 0)
    return set_volume(max(0, min(100, current + delta)))


def mute(on: bool) -> str:
    _osascript(f"set volume output muted {'true' if on else 'false'}")
    return "Muted." if on else "Unmuted."


def set_brightness(level: int) -> str:
    # Needs `brew install brightness`; macOS ships no brightness command.
    if not shutil.which("brightness"):
        raise ToolError("Brightness control needs the brightness tool: brew install brightness.")
    _run("brightness", f"{level / 100:.2f}")
    return f"Brightness set to {level} percent."


def lock_screen() -> str:
    # Locks only if "Require password after screen saver" is on in Lock Screen settings.
    _run("pmset", "displaysleepnow")
    return "Locking the screen."


def battery_status() -> str:
    out = _run("pmset", "-g", "batt")
    match = re.search(r"(\d+)%;\s*([\w ]+?);", out)
    if not match:
        return "This Mac doesn't have a battery; it's running on mains power."
    percent, state = match.groups()
    return f"The battery is at {percent} percent and {state.strip()}."


def do_not_disturb(on: bool) -> str:
    name = DND_ON_SHORTCUT if on else DND_OFF_SHORTCUT
    try:
        _run("shortcuts", "run", name)
    except ToolError:
        raise ToolError(
            f'Make a shortcut called "{name}" in the Shortcuts app that sets Focus, then try again.'
        ) from None
    return "Do Not Disturb is on." if on else "Do Not Disturb is off."


# Types each argv line, pressing Return between them; argv item 1 is a placeholder so a
# line starting with "-" isn't read as an osascript option.
_TYPE_SCRIPT = (
    "on run argv",
    'tell application "System Events"',
    "repeat with i from 2 to count of argv",
    "if i > 2 then key code 36",
    "keystroke (item i of argv)",
    "end repeat",
    "end tell",
    "end run",
)


def type_text(text: str, app: str = "") -> str:
    if app:
        name = APP_COMMANDS_MAC.get(app.strip().lower(), app.strip())
        if name == "TextEdit":
            # `open -a TextEdit` shows a file picker instead of a blank page.
            _osascript('tell application "TextEdit" to activate\n'
                       'tell application "TextEdit" to make new document')
        else:
            _run("open", "-a", name)
        time.sleep(1.5)
    cmd = ["osascript"]
    for line in _TYPE_SCRIPT:
        cmd += ["-e", line]
    cmd += ["_", *text.split("\n")]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        if "not allowed" in result.stderr or "1002" in result.stderr:
            raise ToolError(
                "I'm not allowed to type yet. Open System Settings, Privacy and Security, "
                "Accessibility, and turn on the app I'm running in, like Terminal or VS Code."
            )
        raise ToolError(f"Typing didn't work: {result.stderr.strip()}")
    return "Typed it."
