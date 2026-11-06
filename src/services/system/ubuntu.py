"""System controls on Ubuntu (GNOME): pactl, brightnessctl, loginctl and gsettings."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from livekit.agents import ToolError

_SINK = "@DEFAULT_SINK@"

# Friendly names -> the GNOME apps that ship with Ubuntu.
_APPS = {
    "notepad": "gnome-text-editor",
    "text editor": "gnome-text-editor",
    "textedit": "gnome-text-editor",
    "calculator": "gnome-calculator",
    "terminal": "gnome-terminal",
    "files": "nautilus",
    "file explorer": "nautilus",
}


def _run(*cmd: str) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError) as e:
        raise ToolError(f"That didn't work on this computer: {e}") from None
    return out.stdout.strip()


def set_volume(level: int) -> str:
    _run("pactl", "set-sink-volume", _SINK, f"{level}%")
    return f"Volume set to {level} percent."


def change_volume(delta: int) -> str:
    match = re.search(r"(\d+)%", _run("pactl", "get-sink-volume", _SINK))
    current = int(match.group(1)) if match else 0
    return set_volume(max(0, min(100, current + delta)))


def mute(on: bool) -> str:
    _run("pactl", "set-sink-mute", _SINK, "1" if on else "0")
    return "Muted." if on else "Unmuted."


def set_brightness(level: int) -> str:
    if shutil.which("brightnessctl"):
        _run("brightnessctl", "set", f"{level}%")
    else:
        # GNOME's own brightness setting, for laptops without brightnessctl installed.
        _run(
            "gdbus", "call", "--session",
            "--dest", "org.gnome.SettingsDaemon.Power",
            "--object-path", "/org/gnome/SettingsDaemon/Power",
            "--method", "org.freedesktop.DBus.Properties.Set",
            "org.gnome.SettingsDaemon.Power.Screen", "Brightness", f"<int32 {level}>",
        )
    return f"Brightness set to {level} percent."


def lock_screen() -> str:
    _run("loginctl", "lock-session")
    return "Locking the screen."


def battery_status() -> str:
    batteries = sorted(Path("/sys/class/power_supply").glob("BAT*"))
    if not batteries:
        return "This computer doesn't have a battery; it's running on mains power."
    bat = batteries[0]
    percent = (bat / "capacity").read_text().strip()
    state = (bat / "status").read_text().strip().lower()
    return f"The battery is at {percent} percent and {state}."


def do_not_disturb(on: bool) -> str:
    # GNOME's Do Not Disturb is simply "don't show notification banners".
    _run(
        "gsettings", "set", "org.gnome.desktop.notifications",
        "show-banners", "false" if on else "true",
    )
    return "Do Not Disturb is on." if on else "Do Not Disturb is off."


def type_text(text: str, app: str = "") -> str:
    if app:
        name = app.strip().lower()
        try:
            subprocess.Popen([_APPS.get(name, name)])
        except OSError:
            raise ToolError(f"Couldn't open {app}.") from None
        time.sleep(1.5)
    if os.getenv("XDG_SESSION_TYPE") == "x11" and shutil.which("xdotool"):
        _run("xdotool", "type", "--delay", "15", "--", text)
    elif shutil.which("ydotool"):
        # Wayland (Ubuntu's default) blocks xdotool; ydotool needs its ydotoold service running.
        _run("ydotool", "type", "--", text)
    else:
        raise ToolError(
            "Typing needs xdotool on an X11 session, or ydotool on Wayland. "
            "Install one with apt and try again."
        )
    return "Typed it."
