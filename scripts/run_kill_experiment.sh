#!/bin/bash
# Runs one 0/N-kill experiment end-to-end: brings up self-healing
# port-forwards to each worker (so the host-side poller keeps reaching
# whichever pod currently holds a given worker slot, even across a
# kill-and-replace), runs dssd-experiment, then tears the forwards down.
set -eu

KILLS="$1"
DURATION="$2"
OUT="$3"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT

for i in 0 1 2 3 4; do
  port=$((18000 + i))
  (
    while true; do
      kubectl port-forward "svc/worker-${i}-svc" "${port}:8000" >/tmp/pf-${i}.log 2>&1
      sleep 1
    done
  ) &
  PIDS+=($!)
done

sleep 5

dssd-experiment \
  --peer=worker-0=127.0.0.1:18000 \
  --peer=worker-1=127.0.0.1:18001 \
  --peer=worker-2=127.0.0.1:18002 \
  --peer=worker-3=127.0.0.1:18003 \
  --peer=worker-4=127.0.0.1:18004 \
  --kills="$KILLS" \
  --duration="$DURATION" \
  --interval=3 \
  --out="$OUT"
