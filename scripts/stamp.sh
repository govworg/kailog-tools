#!/bin/bash
# Public timestamps for one chain-head file, from two independent services:
#   1. OpenTimestamps: anchors the file's hash in the Bitcoin blockchain (no cost).
#      The proof starts "pending" and is completed by `ots upgrade` a few hours later.
#   2. RFC 3161: a signed timestamp token from FreeTSA (no cost).
# Only the hash of the file leaves this machine. Run from CloudShell.
set -euo pipefail
F="$1"; [ -f "$F" ] || { echo "usage: stamp.sh site/pulse/proofs/head-YYYY-MM-DD.txt"; exit 1; }
command -v ots >/dev/null || pip3 install --quiet opentimestamps-client || pip3 install --user --quiet opentimestamps-client
export PATH="$HOME/.local/bin:$PATH"

if [ ! -f "$F.ots" ]; then ots stamp "$F" && echo "OpenTimestamps: submitted ($F.ots)"; else echo "OpenTimestamps: already stamped"; fi

TSR="${F%.txt}.tsr"
if [ ! -f "$TSR" ]; then
  openssl ts -query -data "$F" -no_nonce -sha256 -cert -out /tmp/kailog.tsq
  curl -sS --fail -H 'Content-Type: application/timestamp-query' --data-binary @/tmp/kailog.tsq https://freetsa.org/tsr -o "$TSR"
  openssl ts -reply -in "$TSR" -text | grep -E 'Status:|Time stamp:' || true
else echo "RFC 3161: already stamped"; fi

# Complete earlier OpenTimestamps proofs that have since reached a Bitcoin block
for p in "$(dirname "$F")"/*.ots; do ots upgrade "$p" >/dev/null 2>&1 && echo "upgraded $(basename "$p")" || true; done
