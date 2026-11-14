#!/usr/bin/env python3
"""Before/after demo. Flips CamillaDSP between flat.yml and eq.yml live.
   eq demo          -> spoken sentence, alternating off/on
   eq demo music    -> play your own music; flips every 8 s, Ctrl+C to stop (leaves EQ on)"""
import json, subprocess, sys, time
from websocket import create_connection

DIR = "/Users/tanmayganhotra/speaker"
ws = create_connection("ws://127.0.0.1:1234", timeout=5)

def use(name):
    for msg in ({"SetConfigFilePath": f"{DIR}/{name}.yml"}, "Reload"):
        ws.send(json.dumps(msg)); ws.recv()
    print(f"  ▶ {'EQ ON ' if name == 'eq' else 'EQ OFF'}", flush=True)

try:
    if sys.argv[1:] == ["music"]:
        print("Start some music. Flipping every 8 s — Ctrl+C to stop.")
        while True:
            for name in ("flat", "eq"):
                use(name); time.sleep(8)
    else:
        line = ("Testing, one two three. She sells sea shells by the sea shore, "
                "and the shells she sells are surely seashells.")
        for _ in range(2):
            for name in ("flat", "eq"):
                use(name); time.sleep(0.3)
                subprocess.run(["say", "-v", sys.argv[1] if len(sys.argv) > 1 else "Samantha", line])
                time.sleep(0.6)
except KeyboardInterrupt:
    pass
finally:
    use("eq"); ws.close()
