"""
vera_actone_devices.py — single shared registry of ACTONE device keys.

Both vera_system_tools.py (VERA sending commands) and vera_perception.py
(VERA listening for commands/status coming back) import from HERE, so
there is exactly one place the keys are defined -- never duplicate them
in two files, or a key mismatch will silently break auth in one
direction only, which is a nasty thing to debug.

Outbound and inbound channels are kept as SEPARATE SecureChannel
instances per device, each with their own counter, because
"VERA -> device" and "device -> VERA" are two independent conversations
that happen to share a key -- they are not the same rolling counter.

Real per-device keys were generated with:
    python -c "import secrets; print(secrets.token_hex(32))"
and are provisioned below. Keep a copy of these exact values somewhere
outside this codebase (a password manager) as well -- this file is
what eventually needs to match what gets flashed onto each device's
firmware, and it lives in a folder structure that maps onto a public
GitHub repo. Never commit real keys to that repo.
"""

from vera_actone_secure import SecureChannel, frame_samples

# name -> 32-byte shared secret, generated per device with `secrets.token_hex(32)`.
try:
    from vera_actone_keys_local import ACTONE_DEVICE_KEYS
except ImportError:
    raise RuntimeError(
        "vera_actone_keys_local.py not found. Copy vera_actone_keys_local.py.example, "
        "fill in real per-device keys, and never commit that file."
    )

_outbound_channels = {}
_inbound_channels = {}


def known_devices():
    return list(ACTONE_DEVICE_KEYS.keys())


def get_outbound_channel(target: str):
    """VERA -> device. Used when VERA is the one sending a command."""
    target = target.upper()
    if target not in ACTONE_DEVICE_KEYS:
        return None
    if target not in _outbound_channels:
        _outbound_channels[target] = SecureChannel(
            ACTONE_DEVICE_KEYS[target], starting_counter=0
        )
    return _outbound_channels[target]


def get_inbound_channel(target: str):
    """device -> VERA. Used when VERA is listening for that device's
    replies (ACK, status, telemetry). Independent counter from outbound."""
    target = target.upper()
    if target not in ACTONE_DEVICE_KEYS:
        return None
    if target not in _inbound_channels:
        _inbound_channels[target] = SecureChannel(
            ACTONE_DEVICE_KEYS[target], starting_counter=0
        )
    return _inbound_channels[target]


def decode_any_device(buf, now=None):
    """
    Try decoding a captured audio buffer against every registered
    device's inbound channel, since the listener doesn't know in
    advance which device transmitted. Returns (device_name, result)
    for the first channel that authenticates successfully, or
    (None, None) if nothing matched any device.

    NOTE: this assumes `buf` is EXACTLY one frame's worth of samples,
    starting right at the command tone. In real continuous capture you
    almost never get that alignment for free -- use scan_any_device()
    against a rolling buffer instead; this function is kept for the
    case where you already know a frame starts at buf[0] (e.g. tests).
    """
    for name in known_devices():
        channel = get_inbound_channel(name)
        result = channel.decode_frame(buf, now=now)
        if result.result == "OK":
            return name, result
    return None, None


def scan_any_device(buf, sample_rate=16000, step=200, now=None):
    """
    Slide across a (typically much longer than one frame) rolling
    capture buffer, testing many candidate offsets against every
    registered device, without needing the burst to start at buf[0].

    IMPORTANT: the search itself uses ONLY the stateless peek_frame()
    -- scanning ~20-60 candidate offsets per receive cycle must never
    by itself count toward a device's lockout, or noise that randomly
    looks command-shaped at a handful of offsets (which happens more
    than you'd expect over many offsets) would lock the receiver out
    before it ever reaches the real signal. That's a real failure mode
    this function used to have, caught by testing against a noisy
    stream rather than a single isolated slice.

    Per device, per call: if any offset authenticates, consume it for
    real (exactly once) via decode_frame and return success. If none
    authenticate but at least one offset looked command-shaped and
    failed its MAC (a genuine "something tried to authenticate and
    failed" event, not scanning noise), register exactly ONE failure
    for that device this cycle -- so lockout tracks real repeated
    attempts, not scanning granularity.

    Returns (device_name, result, offset) on success, or
    (None, None, None) if nothing in the buffer matched any device.
    """
    fs = frame_samples(sample_rate)
    if len(buf) < fs:
        return None, None, None

    for name in known_devices():
        channel = get_inbound_channel(name)
        best_bad_mac_offset = None
        offset = 0
        while offset + fs <= len(buf):
            slice_ = buf[offset:offset + fs]
            peek = channel.peek_frame(slice_)
            if peek.result == "OK":
                result = channel.decode_frame(slice_, now=now)  # consume for real, once
                if result.result == "OK":
                    return name, result, offset
            elif peek.result == "BAD_MAC" and best_bad_mac_offset is None:
                best_bad_mac_offset = offset  # remember the first, don't act yet
            offset += step

        if best_bad_mac_offset is not None:
            # Exactly one real authentication attempt charged against
            # this device for this whole scan cycle.
            channel.decode_frame(buf[best_bad_mac_offset:best_bad_mac_offset + fs], now=now)

    return None, None, None
