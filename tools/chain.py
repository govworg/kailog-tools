#!/usr/bin/env python3
"""Kai Log record chain (R8 append only, R9 tamper-evident).

Each line of records/kailog.jsonl is one entry. Every entry carries the hash of
the entry before it, so changing or removing any past entry breaks every hash
after it.

  hash = sha256( canonical JSON of the entry without its "hash" field )
  canonical JSON = sorted keys, no spaces, UTF-8

Usage:
  chain.py verify [file]            check every link; exit 1 on any break
  chain.py head [file]              print the latest seq and hash
  chain.py add FILE.json [file]     append one entry (fields from FILE.json)
  chain.py extends OLD NEW          exit 0 only if NEW keeps OLD unchanged as its start
"""
import hashlib, json, sys, datetime

DEFAULT = "records/kailog.jsonl"
GENESIS = "0" * 64
REQUIRED = ("id", "type", "date", "period", "summary")
TYPES = ("task", "event", "rule", "correction")


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def entry_hash(e):
    return hashlib.sha256(canon({k: v for k, v in e.items() if k != "hash"})).hexdigest()


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []


def verify(entries):
    prev = GENESIS
    for i, e in enumerate(entries, 1):
        if e.get("seq") != i:
            return f"seq {e.get('seq')} at line {i}"
        if e.get("prev") != prev:
            return f"broken link at seq {i}"
        if entry_hash(e) != e.get("hash"):
            return f"hash mismatch at seq {i}"
        prev = e["hash"]
    return None


def add(path, fields):
    entries = load(path)
    err = verify(entries)
    if err:
        sys.exit(f"chain invalid, not adding: {err}")
    missing = [k for k in REQUIRED if k not in fields]
    if missing:
        sys.exit(f"missing fields: {', '.join(missing)}")
    if fields["type"] not in TYPES:
        sys.exit(f"type must be one of {TYPES}")
    if fields["type"] == "correction" and "corrects" not in fields:
        sys.exit("a correction must name the entry it corrects (corrects: KL-E....)")
    if any(e["id"] == fields["id"] for e in entries):
        sys.exit(f"id {fields['id']} already used")
    e = dict(fields)
    e["seq"] = len(entries) + 1
    e["logged_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    e["prev"] = entries[-1]["hash"] if entries else GENESIS
    e["hash"] = entry_hash(e)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
    return e


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd = argv[1]
    if cmd == "verify":
        entries = load(argv[2] if len(argv) > 2 else DEFAULT)
        err = verify(entries)
        print(f"FAIL: {err}" if err else f"OK: {len(entries)} entries")
        sys.exit(1 if err else 0)
    if cmd == "head":
        entries = load(argv[2] if len(argv) > 2 else DEFAULT)
        print(f"{len(entries)} {entries[-1]['hash'] if entries else GENESIS}")
        return
    if cmd == "add":
        with open(argv[2], encoding="utf-8") as f:
            e = add(argv[3] if len(argv) > 3 else DEFAULT, json.load(f))
        print(f"added seq {e['seq']} {e['id']} {e['hash'][:16]}")
        return
    if cmd == "extends":
        old, new = load(argv[2]), load(argv[3])
        for err, label in ((verify(old), "old"), (verify(new), "new")):
            if err:
                sys.exit(f"{label} chain invalid: {err}")
        if len(new) < len(old) or any(a["hash"] != b["hash"] for a, b in zip(old, new)):
            sys.exit("REFUSED: the new chain rewrites or drops published entries")
        print(f"OK: {len(new) - len(old)} new entries")
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
