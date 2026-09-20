"""
actone_hardware_diagnostic.py

Runs entirely in ONE process: plays a real ACTONE frame through your
default speaker, then immediately records through your default mic,
and reports the RAW signal level -- separate from whether decode
succeeds -- so we can tell whether this is a hardware/routing problem
or a software one.

Run from C:\\Users\\P01yG107\\Desktop\\vera:
    python actone_hardware_diagnostic.py
"""

import time
import numpy as np
import sounddevice as sd

from vera_actone_devices import get_outbound_channel, scan_any_device
from vera_actone_secure import frame_samples

SAMPLE_RATE = 16000  # NOT 8000 -- auth tones climb to ~3950Hz, which sits
                      # right at 8kHz's Nyquist limit (4000Hz) and gets
                      # degraded there by real anti-aliasing/mic filtering.
                      # 16kHz gives real headroom.

print("=" * 60)
print("ACTONE hardware diagnostic")
print("=" * 60)

print("\nDefault devices sounddevice will use:")
print(sd.query_devices(kind="input"))
print()
print(sd.query_devices(kind="output"))
print()

fs = frame_samples(SAMPLE_RATE)
frame_ms = int(fs / SAMPLE_RATE * 1000)

channel = get_outbound_channel("BB8")
frame = channel.generate_frame("HOME")
tone_out = (frame.astype(np.float32) / 32768.0)

lead_silence = np.zeros(int(SAMPLE_RATE * 1.0), dtype=np.float32)   # 1000ms lead-in --
trail_silence = np.zeros(int(SAMPLE_RATE * 1.0), dtype=np.float32)  # wide margin so real
                                                                     # device latency (your
                                                                     # reported 180ms x2 for
                                                                     # in+out) can't push the
                                                                     # frame's tail past the
                                                                     # end of the recording
combined = np.concatenate([lead_silence, tone_out, trail_silence])
combined_2d = combined.reshape(-1, 1)  # sounddevice wants (samples, channels)

print(f"Simultaneously playing+recording a {len(combined)/SAMPLE_RATE*1000:.0f}ms "
      f"clip (1000ms silence, then {frame_ms}ms HOME tone, then 1000ms silence)...")

recording = sd.playrec(combined_2d, samplerate=SAMPLE_RATE, channels=1, dtype="float32")
sd.wait()

recorded = recording[:, 0].astype(np.float64)  # avoid overflow in the RMS step below
peak = float(np.max(np.abs(recorded)))
rms = float(np.sqrt(np.mean(recorded ** 2)))

print()
print(f"Captured audio stats: peak amplitude={peak:.5f}, RMS={rms:.5f}")
print("(For reference: true silence/only-noise-floor is typically peak < 0.01."
      " A real tone played into a working mic at normal volume should show"
      " peak well above 0.05-0.1.)")

if peak < 0.01:
    print("\n>>> DIAGNOSIS: the microphone captured essentially nothing.")
    print("    This points to a hardware/routing problem, not a decode bug:")
    print("    - Is your system volume / this app's volume actually up and unmuted?")
    print("    - Is the DEFAULT playback device your actual speakers (not")
    print("      headphones, HDMI, or a disconnected device)?")
    print("    - Is the DEFAULT recording device your actual working mic?")
    print("    - Can you literally hear a short warbling tone right now when")
    print("      this script plays it?")
else:
    print("\n>>> Real signal was captured. Checking decode against the full buffer...")
    buf_clipped = np.clip(recorded, -1.0, 1.0)
    buf16 = (buf_clipped * 32767.0).astype(np.int16)
    device, result, offset = scan_any_device(buf16, sample_rate=SAMPLE_RATE, now=time.time())
    if device:
        print(f"    DECODED: device={device} cmd={result.cmd} offset={offset}")
        print("    Hardware AND decode both work -- something about the")
        print("    two-separate-terminal-process test is the actual issue")
        print("    (e.g. one process using a different default device than")
        print("    the other), not the ACTONE code itself.")
    else:
        print("    Signal was captured but did NOT decode correctly.")
        print("    Comparing each segment of the frame (command tone + each")
        print("    of the 3 auth-symbol tones) as SENT vs as RECEIVED, to see")
        print("    exactly which part is getting corrupted.\n")

        # Exact segment boundaries within the frame, matching actone_auth.c's
        # FRAME_TONE_MS=100 / FRAME_GAP_MS=40 layout at this sample rate.
        tone_samples = int(SAMPLE_RATE * 100 / 1000)
        gap_samples = int(SAMPLE_RATE * 40 / 1000)
        segments = [("command tone", 0)]
        pos = tone_samples
        for i in range(3):
            pos += gap_samples
            segments.append((f"auth symbol {i+1}", pos))
            pos += tone_samples

        # Locate where the tone ACTUALLY starts by detecting the first
        # real jump in short-time energy above the background noise floor,
        # rather than assuming a fixed lead-in offset -- we just learned
        # that assumption can be wrong by hundreds of ms due to real
        # device latency.
        win = int(SAMPLE_RATE * 0.02)  # 20ms energy windows
        n_windows = len(buf_clipped) // win
        energies = np.array([
            np.sqrt(np.mean(buf_clipped[i*win:(i+1)*win] ** 2))
            for i in range(n_windows)
        ])
        baseline = np.median(energies[:10])  # first ~200ms, before playback starts
        threshold = max(baseline * 5, 0.01)
        onset_windows = np.where(energies > threshold)[0]
        naive_offset = int(SAMPLE_RATE * 1.0)  # what a fixed-lead-in assumption would guess
        detected_start = int(onset_windows[0] * win) if len(onset_windows) else naive_offset

        print(f"    Detected tone onset at ~{detected_start/SAMPLE_RATE*1000:.0f}ms "
              f"into the recording (vs a naive fixed-offset assumption of "
              f"{naive_offset/SAMPLE_RATE*1000:.0f}ms) -- using the detected "
              f"position for the comparison below.\n")

        received_frame = buf_clipped[detected_start:detected_start + len(tone_out)]
        sent_frame = frame.astype(np.float64) / 32768.0  # the original, pre-playback samples

        def top_peak(segment, sample_rate):
            spectrum = np.abs(np.fft.rfft(segment))
            freqs = np.fft.rfftfreq(len(segment), d=1.0 / sample_rate)
            idx = int(np.argmax(spectrum))
            return freqs[idx], spectrum[idx]

        print(f"    {'segment':<16}{'sent freq':<12}{'sent mag':<12}"
              f"{'recv freq':<12}{'recv mag':<12}")
        print("    " + "-" * 62)
        for name, start in segments:
            sent_seg = sent_frame[start:start + tone_samples]
            recv_seg = received_frame[start:start + tone_samples]
            sent_f, sent_m = top_peak(sent_seg, SAMPLE_RATE)
            recv_f, recv_m = top_peak(recv_seg, SAMPLE_RATE)
            print(f"    {name:<16}{sent_f:<12.1f}{sent_m:<12.1f}"
                  f"{recv_f:<12.1f}{recv_m:<12.1f}")

        print()
        print("    Read this as: does 'recv freq' match 'sent freq' for EVERY")
        print("    segment, or only for the command tone? If the auth symbols'")
        print("    received frequencies are off from what was sent (or their")
        print("    magnitude collapsed much lower relative to the command")
        print("    tone's), that confirms the higher auth-band frequencies")
        print("    are specifically what's being lost -- most likely your")
        print("    laptop's built-in speaker/mic simply rolling off hard")
        print("    above ~2-3kHz, a physical hardware limit separate from")
        print("    the sample-rate/Nyquist issue already fixed.")
