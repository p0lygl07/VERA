"""
vera_tool_tones.py — audible tone announcements for VERA's own tools.

IMPORTANT SCOPE NOTE: this is OUTPUT ONLY. Playing a tone announces
which of VERA's already-registered tools she is about to run -- it is
NOT an input channel, and nothing here creates a way to trigger a tool
via audio. In particular, run_shell_command's existing human
confirmation gate ("[VERA CONFIRM] Run: ... Allow? [y/N]") is
untouched by this file and must never be bypassed by any tone-based
mechanism, now or later.

Uses the SAME frequency law as ACTONE/RUNIC LUX (f = band_root *
2^(n/12)) but in its own band -- root 330 Hz -- chosen to sit well
below both ACTONE's command band (600Hz+) and the ~1500Hz rolloff
your laptop's built-in speaker/mic demonstrated in testing, so these
tones are the most likely to actually be audible/recordable on
consumer hardware if you ever want to log/verify them.

No auth, no decode, no C library dependency -- this only ever plays
a tone; nothing needs to authenticate an announcement.
"""

import time
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except (ImportError, OSError):
    sd = None

TOOL_TONE_BAND_ROOT_HZ = 330.0

# Order matters only in that it assigns each tool a stable n (and thus
# a stable frequency) -- add new tools to the END of this list so
# existing tools' tones never change out from under anyone who's
# learned to recognize them by ear.
TOOL_ORDER = [
    "read_file",
    "write_file",
    "run_shell_command",
    "list_directory",
    "web_search",
    "read_skill",
    "search_files",
    "get_status",
    "send_actone_command",
]

TOOL_TONE_HZ = {
    name: TOOL_TONE_BAND_ROOT_HZ * (2 ** (n / 12))
    for n, name in enumerate(TOOL_ORDER)
}


def _generate_tone(freq_hz: float, sample_rate: int, duration_ms: int) -> np.ndarray:
    num_samples = int(sample_rate * duration_ms / 1000)
    t = np.arange(num_samples) / sample_rate
    tone = 0.5 * np.sin(2 * np.pi * freq_hz * t)  # 0.5 amplitude: audible, not jarring

    # Short attack/decay envelope so it doesn't click.
    ramp = max(1, num_samples // 20)
    envelope = np.ones(num_samples)
    envelope[:ramp] = np.linspace(0, 1, ramp)
    envelope[-ramp:] = np.linspace(1, 0, ramp)
    return (tone * envelope).astype(np.float32)


def play_tool_tone(tool_name: str, sample_rate: int = 16000,
                    duration_ms: int = 150, device: Optional[int] = None) -> bool:
    """
    Play the announcement tone for a registered VERA tool. Returns True
    if a tone was actually played, False if the tool is unknown or
    audio isn't available -- callers should treat False as "silently
    skip," never as an error worth interrupting the tool call itself.
    """
    if tool_name not in TOOL_TONE_HZ:
        return False
    if sd is None:
        return False
    try:
        tone = _generate_tone(TOOL_TONE_HZ[tool_name], sample_rate, duration_ms)
        sd.play(tone, sample_rate, device=device)
        sd.wait()
        return True
    except Exception:
        return False  # never let a tone failure break the actual tool call


def print_tone_table():
    print(f"{'tool':<24}{'n':<4}{'freq (Hz)'}")
    print("-" * 44)
    for n, name in enumerate(TOOL_ORDER):
        print(f"{name:<24}{n:<4}{TOOL_TONE_HZ[name]:.1f}")


if __name__ == "__main__":
    print_tone_table()
