# Sealed notes (R19)

Encrypted batches of Kai's notes. The project lead holds no key share, so he cannot open them.
Any 2 of the 3 holders can open a batch, and only when the board decides to release it (R16).

For each holder, once:
  1. Install age (https://age-encryption.org): `brew install age`, `winget install FiloSottile.age` or `apt install age`.
  2. `age-keygen -o kailog-key.txt` and keep that file private and backed up (a password manager works).
  3. Send only the line starting with `age1...` (the public key). It is safe to share.

To open a batch (board decision only): each of 2 holders runs
  `age -d -i kailog-key.txt <batch>.share-N.age > share-N.txt`
and the two share files go to `tools/sealed.py open <batch>.bin share-A.txt share-B.txt`.

## With a YubiKey (recommended)
Keep your key on a YubiKey instead of a file: install age-plugin-yubikey, run `age-plugin-yubikey` once to create a key
on the YubiKey, and send the `age1yubikey1...` line. Opening a share then needs the YubiKey itself, its PIN and a touch,
so a stolen laptop or a copied file is not enough.
