#!/usr/bin/env python3
"""Sealed notes (R19): Kai's notes that the project lead cannot open.

How it works
  1. Each key holder makes an age key pair on their own computer (age-keygen)
     and shares only the PUBLIC key ("age1..."). Private keys never leave them.
  2. `seal` encrypts a batch of notes with a fresh random key (AES-256-GCM),
     splits that key into shares (Shamir, any THRESHOLD of the holders can
     rebuild it) and encrypts each share to one holder's public key.
     The random key is never stored or shown.
  3. To open a batch (only under R16, by board decision), THRESHOLD holders
     each decrypt their share with their own key, and `open` rebuilds the key.

Standards: age v1 (age-encryption.org), Shamir secret sharing, AES-256-GCM (NIST SP 800-38D).
Holders may keep their key on a YubiKey (age-plugin-yubikey, PIV): opening a share then needs the key, its PIN and a touch.

Usage
  sealed.py seal NOTES_FILE [sealed_dir]        -> sealed/<batch>.bin + <batch>.share-N.age
  sealed.py open BATCH.bin SHARE.txt SHARE.txt  -> plaintext to stdout
  (a holder runs:  age -d -i my-key.txt BATCH.share-N.age > share-N.txt)
"""
import base64, datetime, json, os, subprocess, sys
from Crypto.Cipher import AES
from Crypto.Protocol.SecretSharing import Shamir
import pyrage

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def holders(sealed_dir):
    cfg = json.load(open(os.path.join(sealed_dir, "holders.json")))
    hs = cfg["holders"]
    if any(not h["recipient"].startswith("age1") for h in hs):
        sys.exit("holders.json: every holder needs a public age key (age1... or age1yubikey1...)")
    if not 2 <= cfg["threshold"] <= len(hs):
        sys.exit("holders.json: threshold must be between 2 and the number of holders")
    return hs, cfg["threshold"]


def seal(notes_path, sealed_dir):
    hs, k = holders(sealed_dir)
    data = open(notes_path, "rb").read()
    key = os.urandom(32)
    nonce = os.urandom(12)
    ct, tag = AES.new(key, AES.MODE_GCM, nonce=nonce).encrypt_and_digest(data)
    batch = "sealed-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    open(os.path.join(sealed_dir, batch + ".bin"), "wb").write(b"KLS1" + nonce + tag + ct)
    # Shamir works on 16-byte blocks: split each half of the 32-byte key
    halves = [Shamir.split(k, len(hs), key[:16]), Shamir.split(k, len(hs), key[16:])]
    for i, h in enumerate(hs):
        idx = halves[0][i][0]
        share = json.dumps({"batch": batch, "index": idx, "threshold": k,
                            "a": base64.b64encode(halves[0][i][1]).decode(),
                            "b": base64.b64encode(halves[1][i][1]).decode()}).encode()
        out = os.path.join(sealed_dir, f"{batch}.share-{idx}.age")
        if h["recipient"].startswith("age1yubikey1"):
            # YubiKey holders: needs age-plugin-yubikey installed where sealing runs; opening needs the key, its PIN and a touch
            subprocess.run(["age", "-r", h["recipient"], "-o", out], input=share, check=True)
        else:
            rec = pyrage.x25519.Recipient.from_str(h["recipient"])
            open(out, "wb").write(pyrage.encrypt(share, [rec]))
    del key
    print(f"sealed {batch}: {len(data)} bytes, {len(hs)} shares, any {k} can open")


def open_batch(bin_path, share_paths):
    shares = [json.load(open(p)) for p in share_paths]
    k = shares[0]["threshold"]
    if len(shares) < k:
        sys.exit(f"need {k} shares")
    key = (Shamir.combine([(s["index"], base64.b64decode(s["a"])) for s in shares[:k]]) +
           Shamir.combine([(s["index"], base64.b64decode(s["b"])) for s in shares[:k]]))
    blob = open(bin_path, "rb").read()
    assert blob[:4] == b"KLS1", "not a sealed batch"
    nonce, tag, ct = blob[4:16], blob[16:32], blob[32:]
    sys.stdout.buffer.write(AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag))


if __name__ == "__main__":
    a = sys.argv
    if len(a) >= 3 and a[1] == "seal":
        seal(a[2], a[3] if len(a) > 3 else os.path.join(HERE, "sealed"))
    elif len(a) >= 5 and a[1] == "open":
        open_batch(a[2], a[3:])
    else:
        sys.exit(__doc__)
