#!/usr/bin/env python3
"""Play log sweeps through the speaker, record with the MacBook mic. Saves sweep + recording."""
import numpy as np, sounddevice as sd, soundfile as sf, time, sys

FS = 48000
F1, F2, T = 20.0, 20000.0, 8.0
REPEATS = 3
OUT_DEV, IN_DEV = "NuR_SONICPOP50", "MacBook Air Microphone"
DIR = "/Users/tanmayganhotra/speaker"

t = np.arange(int(T * FS)) / FS
R = np.log(F2 / F1)
sweep = np.sin(2 * np.pi * F1 * T / R * (np.exp(t * R / T) - 1))
fade = int(0.05 * FS)
sweep[:fade] *= np.linspace(0, 1, fade)
sweep[-fade:] *= np.linspace(1, 0, fade)
sweep *= 10 ** (-6 / 20)  # -6 dBFS

gap = np.zeros(int(2.0 * FS))
play = np.concatenate([gap] + [np.concatenate([sweep, gap]) for _ in range(REPEATS)])
play_st = np.column_stack([play, play]).astype(np.float32)

rec = []
def cb(indata, frames, ti, status):
    rec.append(indata[:, 0].copy())

print(f"Playing {REPEATS} sweeps ({len(play)/FS:.0f}s). Keep the room quiet…")
with sd.InputStream(device=IN_DEV, samplerate=FS, channels=1, callback=cb):
    time.sleep(0.5)
    sd.play(play_st, FS, device=OUT_DEV, blocking=True)
    time.sleep(1.5)

r = np.concatenate(rec)
peak = np.max(np.abs(r))
sf.write(f"{DIR}/sweep.wav", sweep, FS)
sf.write(f"{DIR}/recording.wav", r, FS)
print(f"Recorded {len(r)/FS:.1f}s, mic peak = {20*np.log10(peak+1e-12):.1f} dBFS")
if peak > 0.98: print("WARNING: clipped — turn the speaker down and rerun.")
elif peak < 0.01: print("WARNING: almost silent — mic permission denied, or speaker too quiet.")
print("Done. Tell Claude 'recorded'.")
