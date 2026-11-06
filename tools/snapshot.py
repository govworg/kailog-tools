#!/usr/bin/env python3
"""Setup snapshot (R21): hash the AI's setup so reports can show what changed between periods.

Records hashes only, never the content (the content may hold private details).
Usage: snapshot.py MODEL_ID LABEL=FILE [LABEL=FILE ...]  -> JSON for a chain entry's "setup_snapshot" field
"""
import hashlib, json, sys
if len(sys.argv) < 3:
    sys.exit(__doc__)
out = {"model": sys.argv[1], "files": {}}
for a in sys.argv[2:]:
    label, path = a.split("=", 1)
    data = open(path, "rb").read()
    out["files"][label] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
print(json.dumps(out, sort_keys=True))
