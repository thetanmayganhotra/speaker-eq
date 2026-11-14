#!/usr/bin/env python3
"""Deconvolve sweeps -> frequency response + distortion, fit a parametric EQ, plot."""
import json, numpy as np, soundfile as sf
from scipy import signal, optimize
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

DIR = "/Users/tanmayganhotra/speaker"
F1, F2, T = 20.0, 20000.0, 8.0
REPEATS, GAP = 3, 2.0
MAX_BANDS, MAX_BOOST, MAX_CUT = 7, 6.0, -12.0

sweep, fs = sf.read(f"{DIR}/sweep.wav")
rec, _ = sf.read(f"{DIR}/recording.wav")
R = np.log(F2 / F1)
t = np.arange(len(sweep)) / fs

# Farina inverse filter: time-reversed sweep with +6 dB/oct compensation
inv = sweep[::-1] * np.exp(-t * R / T)
ir_all = signal.fftconvolve(rec, inv)
ir_all /= np.max(np.abs(ir_all))

# Find the three linear-IR peaks (≥ sweep+gap apart)
period = int((T + GAP) * fs)
peaks, _ = signal.find_peaks(np.abs(ir_all), distance=int(period * 0.8), height=0.3)
peaks = peaks[:REPEATS]
print("IR peaks at (s):", np.round(peaks / fs, 3))

NFFT = 1 << 16
freqs = np.fft.rfftfreq(NFFT, 1 / fs)
pre, post = int(0.002 * fs), int(0.060 * fs)  # 60 ms window -> mostly direct + desk
win = np.concatenate([np.ones(pre), signal.windows.hann(2 * post)[post:]])

def mag(seg):
    return 20 * np.log10(np.abs(np.fft.rfft(seg, NFFT)) + 1e-12)

def smooth(f, db, frac=6):
    out = np.empty_like(db); p = 10 ** (db / 10)
    for i, fc in enumerate(f):
        lo, hi = fc * 2 ** (-1 / (2 * frac)), fc * 2 ** (1 / (2 * frac))
        m = (f >= lo) & (f <= hi)
        out[i] = 10 * np.log10(p[m].mean()) if m.any() else db[i]
    return out

lin, h2, h3 = [], [], []
for p in peaks:
    lin.append(mag(ir_all[p - pre:p + post] * win))
    for k, store in ((2, h2), (3, h3)):     # harmonic IRs arrive earlier by T*ln(k)/R
        q = p - int(T * np.log(k) / R * fs)
        hw = int(0.02 * fs)
        seg = ir_all[q - pre:q + hw] * np.concatenate([np.ones(pre), signal.windows.hann(2 * hw)[hw:]])
        H = mag(seg)
        # harmonic response is indexed at k*f; remap to fundamental frequency
        store.append(np.interp(freqs * k, freqs, H))
pw = lambda L: 10 * np.log10(np.mean([10 ** (x / 10) for x in L], axis=0))
lin, h2, h3 = pw(lin), pw(h2), pw(h3)

# Log-spaced analysis grid
fg = np.geomspace(20, 20000, 400)
L = smooth(fg, np.interp(fg, freqs, lin), 6)
D2 = smooth(fg, np.interp(fg, freqs, h2), 3)
D3 = smooth(fg, np.interp(fg, freqs, h3), 3)
ref = np.mean(L[(fg > 300) & (fg < 3000)])
L -= ref; D2 -= ref; D3 -= ref
thd = 100 * np.sqrt(10 ** ((D2 - L) / 10) + 10 ** ((D3 - L) / 10))

# Low-frequency limit: lowest f where response is within -10 dB AND THD < 10%,
# scanning down from 300 Hz
ok = (L > -10) & (thd < 10)
i = np.searchsorted(fg, 300)
while i > 0 and ok[i - 1]: i -= 1
f_lo = float(fg[i])
hp = float(np.clip(round(f_lo * 0.9 / 5) * 5, 40, 200))
print(f"LF limit ≈ {f_lo:.0f} Hz → high-pass at {hp:.0f} Hz")

# ---- Biquad helpers (RBJ cookbook) ----
def peq(f0, g, q):
    A = 10 ** (g / 40); w = 2 * np.pi * f0 / fs; a = np.sin(w) / (2 * q)
    b = [1 + a * A, -2 * np.cos(w), 1 - a * A]; aa = [1 + a / A, -2 * np.cos(w), 1 - a / A]
    return np.array(b) / aa[0], np.array(aa) / aa[0]
def hpf(f0, q=0.707):
    w = 2 * np.pi * f0 / fs; a = np.sin(w) / (2 * q); c = np.cos(w)
    b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]; aa = [1 + a, -2 * c, 1 - a]
    return np.array(b) / aa[0], np.array(aa) / aa[0]
def resp(bands, f=fg, with_hp=True):
    H = np.zeros_like(f)
    filt = [peq(*b) for b in bands] + ([hpf(hp), hpf(hp)] if with_hp else [])  # 4th-order HP
    for b, a in filt:
        _, h = signal.freqz(b, a, worN=f, fs=fs); H += 20 * np.log10(np.abs(h) + 1e-12)
    return H

# Target: flat, gentle -1 dB/oct tilt above 2 kHz (sounds natural, avoids harshness)
target = np.where(fg > 2000, -1.0 * np.log2(fg / 2000), 0.0)
band = (fg >= hp * 1.2) & (fg <= 12000)
L3 = smooth(fg, np.interp(fg, freqs, lin), 3) - ref
err0 = target - L3

# Greedy init then joint least-squares refine
bands = []
for _ in range(MAX_BANDS):
    e = (err0 - resp(bands, with_hp=False))[band]; fb = fg[band]
    j = np.argmax(np.abs(e))
    if abs(e[j]) < 1.5: break
    g = float(np.clip(e[j], MAX_CUT, MAX_BOOST))
    bands.append([fb[j], g, 1.0 if g > 0 else 2.0])

def unpack(x): return [x[i:i + 3] for i in range(0, len(x), 3)]
def cost(x):
    return (err0 - resp(unpack(x), with_hp=False))[band]
# each band may move ±1/2 octave; boosts broad (Q<=1.5), cuts Q<=4
lo = sum([[max(b[0] / 1.41, hp), MAX_CUT if b[1] < 0 else 0, 0.5] for b in bands], [])
hi = sum([[min(b[0] * 1.41, 12000), 0 if b[1] < 0 else MAX_BOOST, 4.0 if b[1] < 0 else 1.5] for b in bands], [])
x0 = np.clip(sum(bands, []), np.array(lo) + 1e-6, np.array(hi) - 1e-6)
sol = optimize.least_squares(cost, x0, bounds=(lo, hi))
bands = [[float(round(f, 0)), float(round(g, 1)), float(round(q, 2))] for f, g, q in unpack(sol.x)]
bands = [b for b in bands if abs(b[1]) >= 0.5]
bands.sort()
preamp = -max(0.0, float(np.max(resp(bands)[band])) + 0.5)

corrected = L + resp(bands)
print(f"Residual error (±dB, {hp*1.2:.0f}-16k): before {np.std(err0[band]):.2f}, "
      f"after {np.std((target - L3 - resp(bands))[band]):.2f}")
print(f"Preamp {preamp:.1f} dB")
for f, g, q in bands: print(f"  PK {f:7.0f} Hz  {g:+5.1f} dB  Q {q:.2f}")

json.dump({"samplerate": fs, "highpass_hz": hp, "highpass_order": 4, "preamp_db": round(preamp, 1),
           "bands": [{"type": "peaking", "freq": f, "gain": g, "q": q} for f, g, q in bands],
           "lf_limit_hz": round(f_lo)}, open(f"{DIR}/eq.json", "w"), indent=2)

# ---- Plot ----
fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1.3]})
a1.semilogx(fg, L, color="#888", lw=1.6, label="Measured (1/6 oct)")
a1.semilogx(fg, resp(bands) + preamp, color="#2b7bd6", lw=1.2, ls="--", label="EQ curve (incl. preamp)")
a1.semilogx(fg, corrected, color="#d6492b", lw=2, label="Predicted after EQ")
a1.semilogx(fg, target, color="#3a3", lw=1, ls=":", label="Target")
a1.axvline(hp, color="k", lw=0.8, ls=":"); a1.text(hp * 1.05, -22, f"HPF {hp:.0f} Hz", fontsize=9)
a1.set_ylim(-30, 15); a1.set_ylabel("dB (rel. 300 Hz–3 kHz)"); a1.grid(True, which="both", alpha=.3)
a1.axvspan(12000, 20000, color="#000", alpha=.05)
a1.legend(loc="lower center", ncol=2); a1.set_title("NuR_SONICPOP50 — in-room response @ 50 cm (MacBook Air mic)")
a2.semilogx(fg, np.clip(thd, 0.1, 100), color="#a3c")
a2.axhline(10, color="k", lw=0.6, ls=":"); a2.set_yscale("log"); a2.set_ylim(0.3, 100)
a2.set_ylabel("THD % (H2+H3)"); a2.set_xlabel("Hz"); a2.grid(True, which="both", alpha=.3)
a2.set_xlim(20, 20000)
plt.tight_layout(); plt.savefig(f"{DIR}/response.png", dpi=130)
print("Saved response.png, eq.json")
