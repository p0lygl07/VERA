"""
vera_actone_secure.py — Python binding to the HMAC-authenticated
ACTONE layer (libactone_secure.so / libactone_secure.dll) for VERA's
SAY/perception agents.

This replaces raw vera_actone.send()/Listener with authenticated
equivalents: every command is followed by a rolling HMAC code bound
to (counter, command), so a spoofed tone, a replayed recording, or a
spliced command can't be accepted -- see actone_auth.c for the design
and test_actone_auth.c for the verification of each property.

The shared secret key must be provisioned to VERA and to each device
(Kyger suit, droid) OUT OF BAND -- flash it onto the device at build
time, don't ever transmit it over audio.

Requires: pip install sounddevice numpy
Requires: the shared library built alongside this file --
    Windows:      gcc -O2 -Wall -Wextra -shared -o libactone_secure.dll actone.c actone_auth.c sha256.c -lm
    Linux/WSL:    gcc -O2 -fPIC -shared -o libactone_secure.so actone.c actone_auth.c sha256.c -lm
"""

import ctypes
import os
import platform
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
except (ImportError, OSError):
    sd = None

_LIB_NAME = "libactone_secure.dll" if platform.system() == "Windows" else "libactone_secure.so"
_LIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), _LIB_NAME)
_lib = ctypes.CDLL(_LIB_PATH)

CMD_COUNT = 21
COMMANDS = [
    "PING", "ACK", "NACK", "STOP", "HOME",
    "MOVE_FWD", "MOVE_BACK", "TURN_LEFT", "TURN_RIGHT",
    "GRAB", "RELEASE", "LED_ON", "LED_OFF",
    "ARM_UP", "ARM_DOWN", "LAUNCH", "LAND",
    "RECORD_START", "RECORD_STOP", "MODE_MANUAL", "MODE_AUTO",
]
NAME_TO_CMD = {name: i for i, name in enumerate(COMMANDS)}

AUTH_RESULT_NAMES = ["OK", "BAD_MAC", "NO_COMMAND", "LOCKED_OUT"]


class _AuthCtx(ctypes.Structure):
    _fields_ = [
        ("key", ctypes.c_uint8 * 32),
        ("key_len", ctypes.c_size_t),
        ("counter", ctypes.c_uint64),
        ("consecutive_failures", ctypes.c_int),
        ("lockout_until", ctypes.c_double),
    ]


class _DecodedFrame(ctypes.Structure):
    _fields_ = [
        ("result", ctypes.c_int),
        ("cmd", ctypes.c_int),
        ("matched_counter", ctypes.c_uint64),
    ]


_lib.actone_auth_init.argtypes = [ctypes.POINTER(_AuthCtx), ctypes.c_char_p,
                                   ctypes.c_size_t, ctypes.c_uint64]
_lib.actone_auth_init.restype = None

_lib.actone_auth_generate_frame.argtypes = [
    ctypes.POINTER(_AuthCtx), ctypes.c_int, ctypes.c_int,
    ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t,
]
_lib.actone_auth_generate_frame.restype = ctypes.c_size_t

_lib.actone_auth_decode_frame.argtypes = [
    ctypes.POINTER(_AuthCtx), ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t,
    ctypes.c_int, ctypes.c_double,
]
_lib.actone_auth_decode_frame.restype = _DecodedFrame

_lib.actone_auth_peek_frame.argtypes = [
    ctypes.POINTER(_AuthCtx), ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t,
    ctypes.c_int,
]
_lib.actone_auth_peek_frame.restype = _DecodedFrame


def frame_samples(sample_rate: int) -> int:
    """Exact length of one secure frame (command tone + 3 auth-symbol
    tones + gaps) at the given sample rate. Callers doing a sliding-
    window scan need this to know how big a slice to test at each
    candidate offset."""
    tone_ms, gap_ms, code_symbols = 100, 40, 3
    return int(sample_rate * (tone_ms + code_symbols * (gap_ms + tone_ms)) / 1000)


@dataclass
class SecureDecodeResult:
    result: str            # "OK" / "BAD_MAC" / "NO_COMMAND" / "LOCKED_OUT"
    cmd: Optional[str]      # only set when result == "OK"
    matched_counter: Optional[int]


class SecureChannel:
    """
    One shared-key authenticated channel. VERA holds one instance per
    device it talks to (a droid, the Kyger suit) -- each with its own
    key and its own counter, since counters are per-pair, not global.
    """

    def __init__(self, key: bytes, starting_counter: int = 0,
                 sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.ctx = _AuthCtx()
        _lib.actone_auth_init(ctypes.byref(self.ctx), key, len(key), starting_counter)

    def generate_frame(self, cmd_name: str) -> np.ndarray:
        """Sender side: build the PCM buffer for an authenticated command."""
        if cmd_name not in NAME_TO_CMD:
            raise ValueError(f"Unknown command: {cmd_name!r}")
        cap = self.sample_rate * 2  # generous upper bound for one frame
        buf = (ctypes.c_int16 * cap)()
        n = _lib.actone_auth_generate_frame(
            ctypes.byref(self.ctx), NAME_TO_CMD[cmd_name],
            self.sample_rate, buf, cap,
        )
        return np.frombuffer(buf, dtype=np.int16)[:n].copy()

    def decode_frame(self, buf: np.ndarray, now: Optional[float] = None) -> SecureDecodeResult:
        """Receiver side: verify and decode a captured audio buffer.
        Mutates state (advances counter on success, tracks failures
        toward lockout). Use this only on a slice you already believe
        contains a real frame -- for scanning many candidate offsets,
        use peek_frame() first (see SecureChannel.peek_frame)."""
        if now is None:
            now = time.time()
        buf16 = np.ascontiguousarray(buf, dtype=np.int16)
        c_buf = buf16.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        decoded = _lib.actone_auth_decode_frame(
            ctypes.byref(self.ctx), c_buf, len(buf16), self.sample_rate, now,
        )
        result_name = AUTH_RESULT_NAMES[decoded.result]
        return SecureDecodeResult(
            result=result_name,
            cmd=COMMANDS[decoded.cmd] if result_name == "OK" else None,
            matched_counter=decoded.matched_counter if result_name == "OK" else None,
        )

    def peek_frame(self, buf: np.ndarray) -> SecureDecodeResult:
        """Stateless check: does this slice authenticate, without
        touching the counter or failure-tracking state? Use this to
        scan many candidate offsets in a rolling capture buffer --
        most won't even look like a command tone (NO_COMMAND) and cost
        nothing toward lockout. Once you find an OK offset, call
        decode_frame() on that exact slice to actually consume it."""
        buf16 = np.ascontiguousarray(buf, dtype=np.int16)
        c_buf = buf16.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        decoded = _lib.actone_auth_peek_frame(
            ctypes.byref(self.ctx), c_buf, len(buf16), self.sample_rate,
        )
        result_name = AUTH_RESULT_NAMES[decoded.result]
        return SecureDecodeResult(
            result=result_name,
            cmd=COMMANDS[decoded.cmd] if result_name == "OK" else None,
            matched_counter=decoded.matched_counter if result_name == "OK" else None,
        )

    def send(self, cmd_name: str, device: Optional[int] = None) -> None:
        """Broadcast an authenticated command over speaker."""
        if sd is None:
            raise RuntimeError("sounddevice not installed -- pip install sounddevice")
        frame = self.generate_frame(cmd_name)
        audio_float = frame.astype(np.float32) / 32768.0
        sd.play(audio_float, self.sample_rate, device=device)
        sd.wait()


class SecureListener:
    """
    Continuous mic listener that only reports commands that pass
    authentication. Callback receives a SecureDecodeResult; VERA's
    orchestrator decides what to log/do with each result (including
    BAD_MAC / LOCKED_OUT events, which are worth logging too -- a
    burst of BAD_MAC hits is itself a signal something's probing the
    channel).
    """

    def __init__(self, channel: SecureChannel,
                 on_result: Callable[[SecureDecodeResult], None],
                 window_ms: int = 620,  # ~ full frame length at 100ms tone/40ms gap x4
                 device: Optional[int] = None):
        if sd is None:
            raise RuntimeError("sounddevice not installed -- pip install sounddevice")
        self.channel = channel
        self.on_result = on_result
        self.window_samples = int(channel.sample_rate * window_ms / 1000)
        self.device = device
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        buf = (indata[:, 0] * 32767.0).astype(np.int16)
        result = self.channel.decode_frame(buf)
        if result.result != "NO_COMMAND":  # don't spam on plain silence/noise
            self.on_result(result)

    def start(self):
        self._stream = sd.InputStream(
            samplerate=self.channel.sample_rate, channels=1,
            blocksize=self.window_samples, device=self.device,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
