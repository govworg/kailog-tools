# Kai Log tools

The open-source half of Kai Log: tools, page source, protocol and codebook. The record itself lives in a private repository.

Public site, weekly Pulse and tools for Kai Log, a research project of GOVW Foundation, Inc. (https://kailog.org).

| Path | What it is | Public? |
|---|---|---|
| `src/page.html`, `content/` | Page source, updates, cite and privacy text | yes (CC BY 4.0) |
| `protocol/` | Protocol versions (v0.1 draft), OSF preregistration draft | yes |
| `schema/entry.schema.json` | Codebook: the entry format (JSON Schema 2020-12) | yes |
| `tools/chain.py` | Append, verify and compare the hash chain (R8, R9) | yes (MIT) |
| `tools/build.py` | Builds `site/` and the Pulse (volumes only, R3) | yes (MIT) |
| `tools/sealed.py` | Sealed notes: AES-256-GCM, key split 2-of-3, shares encrypted with age (R19) | yes (MIT) |
| `tools/snapshot.py` | Setup snapshot hashes (R21) | yes (MIT) |
| `scripts/` | One-time AWS setup, GitHub role, publish, timestamps | yes (MIT) |
| `.github/workflows/pulse.yml` | Weekly build, timestamp, publish, second witness | yes |
| `records/kailog.jsonl` | The record chain | **private** |
| `sealed/` | Sealed note batches and holders' public keys | **private** |

Verify a published head yourself: `ots verify head-YYYY-MM-DD.txt.ots` and `openssl ts -reply -in head-YYYY-MM-DD.tsr -text`.
Fonts: Bricolage Grotesque, Literata and Martian Mono under the SIL Open Font License (site/fonts).
