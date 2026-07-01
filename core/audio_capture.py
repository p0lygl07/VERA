import os
import sys
import json
import socket
import pyaudio
import numpy as np
from faster_whisper import WhisperModel

# IPC Settings
IPC_HOST = "127.0.0.1"
IPC_PORT = 8765

# Audio Configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
SILENCE_THRESHOLD = 500  # Adjust based on mic sensitivity
SILENCE_CHUNKS = 30      # ~2 seconds of silence before processing

print("[*] Loading local Faster-Whisper Model ('base')...")
model = WhisperModel("base", device="cpu", compute_type="int8")
p = pyaudio.PyAudio()

stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, 
                input=True, frames_per_buffer=CHUNK)

print("\n============================================================")
print("[VERA AUDIO] Mic Engine ACTIVE. Listening asynchronously...")
print("============================================================\n")

def send_to_conductor(text):
    """Sends the transcribed text straight to the Conductor's socket."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((IPC_HOST, IPC_PORT))
        payload = {"origin": "mic_engine", "action": "user_speech", "text": text}
        s.sendall(json.dumps(payload).encode('utf-8'))
        s.close()
        print(f"[Sent to VERA]: {text}")
    except Exception as e:
        print(f"[-] Broadcast to Conductor failed: {e}")

frames = []
is_speaking = False
silent_chunks_count = 0

try:
    while True:
        data = stream.read(CHUNK)
        audio_data = np.frombuffer(data, dtype=np.int16)
        amplitude = np.abs(audio_data).mean()

        if amplitude > SILENCE_THRESHOLD:
            if not is_speaking:
                print("[*] Audio detected... recording.")
                is_speaking = True
            frames.append(data)
            silent_chunks_count = 0
        elif is_speaking:
            frames.append(data)
            silent_chunks_count += 1
            
            # User stopped talking
            if silent_chunks_count > SILENCE_CHUNKS:
                print("[*] Processing utterance...")
                raw_audio = b''.join(frames)
                
                # Convert buffer back to float32 array for whisper
                audio_np = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
                
                segments, _ = model.transcribe(audio_np, beam_size=5)
                text = " ".join([segment.text for segment in segments]).strip()
                
                if text:
                    print(f"[Transcribed]: {text}")
                    send_to_conductor(text)
                
                # Reset buffers
                frames = []
                is_speaking = False
                silent_chunks_count = 0
except KeyboardInterrupt:
    print("[*] Shutting down Mic Engine gracefully...")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()