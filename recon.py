#!/usr/bin/env python3
"""Read-only Bluetooth recon for NuR_SONICPOP50. Never writes to any characteristic."""
import asyncio, subprocess, json, sys
from bleak import BleakScanner, BleakClient

MAC = "97:43:BD:1D:3F:85"
OUT = "/Users/tanmayganhotra/speaker/recon.txt"
lines = []
def log(s=""):
    print(s); lines.append(str(s))

def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()

async def main():
    log("=== blueutil ===")
    log(sh(f"/opt/homebrew/bin/blueutil --info {MAC} --format json-pretty"))
    log(sh("/opt/homebrew/bin/blueutil --connected"))

    log("\n=== BLE scan (20s) ===")
    found = await BleakScanner.discover(timeout=20.0, return_adv=True)
    target = None
    for addr, (dev, adv) in sorted(found.items(), key=lambda kv: -kv[1][1].rssi):
        name = dev.name or adv.local_name or ""
        log(f"{addr}  rssi={adv.rssi:4}  name={name!r}  uuids={adv.service_uuids}  "
            f"mfr={ {hex(k): v.hex() for k, v in adv.manufacturer_data.items()} }")
        if any(t in name.lower() for t in ("sonicpop", "nur", "nu republic")):
            target = target or dev
    if not target:
        log("\nSpeaker NOT advertising over BLE -> classic-only (no GATT control service).")
        return
    log(f"\n=== GATT of {target.name} ({target.address}) — read-only ===")
    async with BleakClient(target, timeout=20) as c:
        for svc in c.services:
            log(f"[service] {svc.uuid}  {svc.description}")
            for ch in svc.characteristics:
                val = ""
                if "read" in ch.properties:
                    try:
                        b = await c.read_gatt_char(ch)
                        val = f"  = {b.hex()}  {b.decode('utf-8', 'replace')!r}"
                    except Exception as e:
                        val = f"  (read failed: {e})"
                log(f"   [char] {ch.uuid}  {ch.properties}{val}")
                for d in ch.descriptors:
                    log(f"      [desc] {d.uuid}  {d.description}")

try:
    asyncio.run(main())
finally:
    open(OUT, "w").write("\n".join(lines) + "\n")
    print(f"\nSaved to {OUT}")
