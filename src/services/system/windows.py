"""System controls on Windows: PowerShell, WMI and media keys."""

from __future__ import annotations

import os
import subprocess
import time

from livekit.agents import ToolError

from config import APP_COMMANDS

# Media keys (via WScript SendKeys) move the volume in steps of 2 percent.
_VOL_MUTE, _VOL_DOWN, _VOL_UP = 173, 174, 175


def _powershell(script: str, env: dict[str, str] | None = None) -> str:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
            env={**os.environ, **env} if env else None,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise ToolError(f"That didn't work on this PC: {e}") from None
    return out.stdout.strip()


def _press(key: int, times: int = 1) -> None:
    if times <= 0:
        return
    _powershell(
        "$w = New-Object -ComObject WScript.Shell; "
        f"1..{times} | ForEach-Object {{ $w.SendKeys([char]{key}) }}"
    )


def set_volume(level: int) -> str:
    # No built-in way to set an exact level: drop to zero, then step up.
    _press(_VOL_DOWN, 50)
    _press(_VOL_UP, round(level / 2))
    return f"Volume set to about {level} percent."


def change_volume(delta: int) -> str:
    _press(_VOL_UP if delta > 0 else _VOL_DOWN, round(abs(delta) / 2))
    return f"Volume turned {'up' if delta > 0 else 'down'} by about {abs(delta)} percent."


def mute(on: bool) -> str:
    # Windows only exposes a mute toggle, so this flips the current state.
    _press(_VOL_MUTE)
    return "Toggled mute."


def set_brightness(level: int) -> str:
    try:
        _powershell(
            "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
            "Invoke-CimMethod -MethodName WmiSetBrightness "
            f"-Arguments @{{Timeout=1; Brightness={level}}}"
        )
    except ToolError:
        raise ToolError(
            "This screen doesn't support brightness control; that usually only works on laptops."
        ) from None
    return f"Brightness set to {level} percent."


def lock_screen() -> str:
    try:
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    except OSError as e:
        raise ToolError(f"Couldn't lock the screen: {e}") from None
    return "Locking the screen."


def battery_status() -> str:
    out = _powershell(
        "Get-CimInstance Win32_Battery | "
        'ForEach-Object { "$($_.EstimatedChargeRemaining) $($_.BatteryStatus)" }'
    )
    if not out:
        return "This PC doesn't have a battery; it's running on mains power."
    percent, status = out.splitlines()[0].split()
    # Win32_Battery.BatteryStatus: 2 means plugged in.
    state = "plugged in" if status == "2" else "on battery"
    return f"The battery is at {percent} percent and {state}."


def do_not_disturb(on: bool) -> str:
    # Focus Assist has no supported command-line switch, so open its settings page.
    os.startfile("ms-settings:quiethours")  # type: ignore[attr-defined]
    return "I've opened the Focus settings so you can switch Do Not Disturb there."


def _sendkeys_escape(text: str) -> str:
    # These characters are SendKeys commands unless wrapped in braces.
    out = "".join(f"{{{c}}}" if c in "+^%~(){}[]" else c for c in text)
    return out.replace("\r\n", "\n").replace("\n", "{ENTER}")


def type_text(text: str, app: str = "") -> str:
    if app:
        name = app.strip().lower()
        try:
            subprocess.Popen(APP_COMMANDS.get(name, name))
        except OSError:
            raise ToolError(f"Couldn't open {app}.") from None
        time.sleep(1.5)
    # Passed through an environment variable so the text is never run as PowerShell.
    _powershell(
        "$w = New-Object -ComObject WScript.Shell; $w.SendKeys($env:VOICE_AGENT_TEXT)",
        env={"VOICE_AGENT_TEXT": _sendkeys_escape(text)},
    )
    return "Typed it."
