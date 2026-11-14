#!/bin/bash
# Speaker EQ control.  eq on | off | status | demo | watch
SPK="NuR_SONICPOP50"; BH="BlackHole 2ch"; FALLBACK="MacBook Air Speakers"
DIR="$HOME/speaker"; STATE="$DIR/eq_state"; SAS=/opt/homebrew/bin/SwitchAudioSource
CDSP="$DIR/bin/camilladsp"; PORT=1234

current()   { $SAS -c -t output; }
connected() { $SAS -a -t output | grep -qx "$SPK"; }
running()   { pgrep -f "$CDSP" >/dev/null; }
enabled()   { [ "$(cat "$STATE" 2>/dev/null || echo on)" = on ]; }
start()     { running || nohup "$CDSP" -p $PORT -a 127.0.0.1 -o "$DIR/camilladsp.log" "$DIR/eq.yml" >/dev/null 2>&1 & }
stop()      { pkill -f "$CDSP" 2>/dev/null; }
route()     { [ "$(current)" = "$1" ] || $SAS -t output -s "$1" >/dev/null; }

# One reconcile pass. Rule: EQ only kicks in when the speaker is what you'd be listening to.
tick() {
  local cur; cur=$(current)
  if connected && enabled; then
    if [ "$cur" = "$SPK" ] || [ "$cur" = "$BH" ]; then start; sleep 0.3; route "$BH"; else stop; fi
  else
    stop
    if [ "$cur" = "$BH" ]; then connected && route "$SPK" || route "$FALLBACK"; fi
  fi
}

case "$1" in
  on)     echo on > "$STATE"; connected && [ "$(current)" != "$BH" ] && route "$SPK"; tick; echo "EQ on";;
  off)    echo off > "$STATE"; tick; echo "EQ off (speaker plays direct)";;
  status) echo "EQ: $(enabled && echo on || echo off) | speaker: $(connected && echo connected || echo not connected) | output: $(current) | dsp: $(running && echo running || echo stopped)";;
  demo)   exec "$DIR/.venv/bin/python" "$DIR/demo.py";;
  watch)  while true; do tick; sleep 3; done;;
  *)      echo "usage: eq on|off|status|demo";;
esac
