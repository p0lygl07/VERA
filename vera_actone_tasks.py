"""
vera_actone_tasks.py — named per-device task functions over ACTONE.

Each function is a thin, named wrapper around get_outbound_channel(...)
.send(...) for one specific device + command pair, so callers (VERA's
tool-calling, or you directly) can say `arm_grab()` instead of having
to remember `send_actone_command(target="ARM", command="GRAB")` every
time. Nothing new is added at the protocol level -- this is purely a
convenience layer over the same 21 fixed commands and the same
authenticated channels already built and tested.

Every function returns a plain string result in the same "OK: ..." /
"ERROR: ..." shape the rest of VERA's tools use, so these can be
registered directly as SYSTEM_TOOLS without a translation layer.
"""

from vera_actone_devices import get_outbound_channel


def _send(target: str, command: str) -> str:
    channel = get_outbound_channel(target)
    if channel is None:
        return f"ERROR: unknown ACTONE target '{target}'"
    try:
        channel.send(command)
        return f"OK: sent '{command}' to {target} [VERA VERIFIED]"
    except Exception as e:
        return f"ERROR: failed to send '{command}' to {target}: {e}"


# --- Kyger suit -------------------------------------------------------------

def kyger_start_scan() -> str:
    """Switch the Kyger suit into autonomous scanning/recon mode."""
    return _send("KYGER", "MODE_AUTO")


def kyger_manual_mode() -> str:
    """Switch the Kyger suit back to manual (non-autonomous) mode."""
    return _send("KYGER", "MODE_MANUAL")


def kyger_ping() -> str:
    """Send a PING to the Kyger suit to check it's listening."""
    return _send("KYGER", "PING")


# --- Robot arm ----------------------------------------------------------

def arm_grab() -> str:
    """Close the robot arm's gripper."""
    return _send("ARM", "GRAB")


def arm_release() -> str:
    """Open the robot arm's gripper."""
    return _send("ARM", "RELEASE")


def arm_raise() -> str:
    """Raise the robot arm."""
    return _send("ARM", "ARM_UP")


def arm_lower() -> str:
    """Lower the robot arm."""
    return _send("ARM", "ARM_DOWN")


def arm_move_forward() -> str:
    """Move the robot arm forward."""
    return _send("ARM", "MOVE_FWD")


def arm_move_backward() -> str:
    """Move the robot arm backward."""
    return _send("ARM", "MOVE_BACK")


def arm_stop() -> str:
    """Stop whatever the robot arm is currently doing."""
    return _send("ARM", "STOP")


# --- BB8 droid ------------------------------------------------------------

def bb8_turn_left() -> str:
    """Turn BB-8 left."""
    return _send("BB8", "TURN_LEFT")


def bb8_turn_right() -> str:
    """Turn BB-8 right."""
    return _send("BB8", "TURN_RIGHT")


def bb8_move_forward() -> str:
    """Move BB-8 forward."""
    return _send("BB8", "MOVE_FWD")


def bb8_move_backward() -> str:
    """Move BB-8 backward."""
    return _send("BB8", "MOVE_BACK")


def bb8_led_on() -> str:
    """Turn on BB-8's status LED."""
    return _send("BB8", "LED_ON")


def bb8_led_off() -> str:
    """Turn off BB-8's status LED."""
    return _send("BB8", "LED_OFF")


def bb8_home() -> str:
    """Send BB-8 back to its home/parked position."""
    return _send("BB8", "HOME")


def bb8_stop() -> str:
    """Stop BB-8 immediately."""
    return _send("BB8", "STOP")


# --- ESP32 Marauder ---------------------------------------------------------
# NOTE: MARAUDER's key in vera_actone_devices.py is still a PLACEHOLDER
# (all-0x33 bytes) as of this writing -- these calls will run, but the
# real device (once it exists and is provisioned with a real key the
# same way KYGER/BB8/ARM were) will not authenticate against a
# placeholder key. Generate and swap in a real key before relying on this.

def marauder_start_capture() -> str:
    """Start a wireless capture session on the Marauder."""
    return _send("MARAUDER", "RECORD_START")


def marauder_stop_capture() -> str:
    """Stop the current capture session on the Marauder."""
    return _send("MARAUDER", "RECORD_STOP")


TASK_FUNCTIONS = {
    "kyger_start_scan": kyger_start_scan,
    "kyger_manual_mode": kyger_manual_mode,
    "kyger_ping": kyger_ping,
    "arm_grab": arm_grab,
    "arm_release": arm_release,
    "arm_raise": arm_raise,
    "arm_lower": arm_lower,
    "arm_move_forward": arm_move_forward,
    "arm_move_backward": arm_move_backward,
    "arm_stop": arm_stop,
    "bb8_turn_left": bb8_turn_left,
    "bb8_turn_right": bb8_turn_right,
    "bb8_move_forward": bb8_move_forward,
    "bb8_move_backward": bb8_move_backward,
    "bb8_led_on": bb8_led_on,
    "bb8_led_off": bb8_led_off,
    "bb8_home": bb8_home,
    "bb8_stop": bb8_stop,
    "marauder_start_capture": marauder_start_capture,
    "marauder_stop_capture": marauder_stop_capture,
}
