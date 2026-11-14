# Speaker EQ

Measured and fixed the sound of a cheap Bluetooth speaker (NuR SONICPOP50) using only a MacBook mic — then made the fix run automatically whenever the speaker is connected.

## How it works

1. **Measure** — `measure.py` plays logarithmic sine sweeps (20 Hz – 20 kHz) through the speaker and records them with the MacBook mic.
2. **Analyse** — `analyze.py` deconvolves the sweeps (Farina method) to get the frequency response and distortion, then fits a parametric EQ (up to 7 bands, max +6 dB boost / −12 dB cut). Writes `eq.json` and `response.png`.
3. **Generate config** — `gen_config.py` turns `eq.json` into [CamillaDSP](https://github.com/HEnquist/camilladsp) configs: `eq.yml` (corrected) and `flat.yml` (bypass, loudness-matched for a fair A/B).
4. **Run** — `eq` routes audio through BlackHole → CamillaDSP → speaker, only when the speaker is the output you'd actually be listening to.
5. **Demo** — `demo.py` flips between flat and EQ live so you can hear the difference.

`recon.py` is a read-only Bluetooth LE scan of the speaker (it never writes anything).

## Use

```bash
./eq on        # EQ on
./eq off       # speaker plays direct
./eq status
./eq demo      # before/after
./eq watch     # keep reconciling every 3 s (what the LaunchAgent runs)
```

To run it at login: copy `com.tanmay.speaker-eq.plist` to `~/Library/LaunchAgents/` and `launchctl load` it.

## Needs

- `brew install blackhole-2ch switchaudio-osx`
- CamillaDSP binary in `bin/camilladsp` (not in the repo — download from its releases)
- Python: `numpy scipy soundfile sounddevice matplotlib websocket-client bleak`

Paths (`DIR`), device names and the speaker's MAC address are hard-coded at the top of each script — change them for your setup.
