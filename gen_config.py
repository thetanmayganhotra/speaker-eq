#!/usr/bin/env python3
"""eq.json -> CamillaDSP configs: eq.yml (corrected) and flat.yml (bypass, loudness-matched for fair A/B)."""
import json, numpy as np
from scipy import signal

DIR = "/Users/tanmayganhotra/speaker"
eq = json.load(open(f"{DIR}/eq.json"))
FS = 44100  # the speaker's A2DP rate

def devices():
    return f"""devices:
  samplerate: {FS}
  chunksize: 1024
  enable_rate_adjust: true
  capture:
    type: CoreAudio
    channels: 2
    device: "BlackHole 2ch"
  playback:
    type: CoreAudio
    channels: 2
    device: "NuR_SONICPOP50"
"""

filters = {"preamp": {"type": "Gain", "parameters": {"gain": eq["preamp_db"]}},
           "highpass": {"type": "BiquadCombo", "parameters": {
               "type": "ButterworthHighpass", "freq": eq["highpass_hz"], "order": eq["highpass_order"]}}}
for i, b in enumerate(eq["bands"], 1):
    filters[f"peq{i}"] = {"type": "Biquad", "parameters": {
        "type": "Peaking", "freq": b["freq"], "gain": b["gain"], "q": b["q"]}}

def yml(filters):
    out = ["filters:"]
    for name, f in filters.items():
        out.append(f"  {name}:\n    type: {f['type']}\n    parameters:")
        out += [f"      {k}: {v}" for k, v in f["parameters"].items()]
    out.append("pipeline:\n  - type: Filter\n    channels: [0, 1]\n    names:")
    out += [f"      - {n}" for n in filters]
    return "\n".join(out) + "\n"

open(f"{DIR}/eq.yml", "w").write(devices() + yml(filters))

# Loudness-match the bypass: average EQ gain over 200 Hz–8 kHz (where speech/music lives)
f = np.geomspace(200, 8000, 200)
H = np.full_like(f, eq["preamp_db"])
for b in eq["bands"]:
    A = 10 ** (b["gain"] / 40); w = 2 * np.pi * b["freq"] / FS; a = np.sin(w) / (2 * b["q"])
    num = [1 + a * A, -2 * np.cos(w), 1 - a * A]; den = [1 + a / A, -2 * np.cos(w), 1 - a / A]
    H += 20 * np.log10(np.abs(signal.freqz(num, den, worN=f, fs=FS)[1]))
match = round(float(10 * np.log10(np.mean(10 ** (H / 10)))), 1)
open(f"{DIR}/flat.yml", "w").write(devices() + yml({"match": {"type": "Gain", "parameters": {"gain": match}}}))
print(f"wrote eq.yml, flat.yml (bypass gain {match} dB)")
