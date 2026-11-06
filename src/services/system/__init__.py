"""System controls (volume, brightness, lock, battery, Do Not Disturb) for the current OS."""

import sys

if sys.platform == "darwin":
    from services.system import mac as platform
elif sys.platform == "win32":
    from services.system import windows as platform
else:
    from services.system import ubuntu as platform

set_volume = platform.set_volume
change_volume = platform.change_volume
mute = platform.mute
set_brightness = platform.set_brightness
lock_screen = platform.lock_screen
battery_status = platform.battery_status
do_not_disturb = platform.do_not_disturb
type_text = platform.type_text
