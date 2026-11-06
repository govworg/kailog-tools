#!/bin/bash
# Encrypt one day's state folder to the owner's public key. Plaintext never leaves this machine.
# Usage: tools/backup_state.sh FOLDER   -> state/kai-state-YYYY-MM-DD.tar.age
set -euo pipefail
cd "$(dirname "$0")/.."
R=$(grep -o 'age1[a-z0-9]*' state/recipient.txt | head -1) || { echo "add the owner's public key to state/recipient.txt"; exit 1; }
OUT="state/kai-state-$(date -u +%F).tar.age"
tar -C "$1" -cf - . | age -r "$R" -o "$OUT"
echo "encrypted $(du -h "$OUT" | cut -f1) -> $OUT"
