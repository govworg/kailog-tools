#!/usr/bin/env python3
"""Build kailog.org from src/page.html and records/kailog.jsonl.

Writes:
  site/index.html, site/site.css, site/app.js   the live site (no third-party requests)
  site/pulse/pulse.json                          the Pulse numbers, machine-readable
  site/pulse/head-YYYY-MM-DD.txt                 the chain head to timestamp (scripts/stamp.sh)
  --preview PATH                                 one-file preview for the draft artifact

The Pulse shows volume only, never outcomes (R3): no miss rates, oversight
shares or ratings until a period report is released.
"""
import datetime, html, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(__file__))
import chain

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REC = os.environ.get("KAILOG_RECORDS", os.path.join(ROOT, "records", "kailog.jsonl"))
SITE = os.path.join(ROOT, "site")
PROOFS = os.path.join(SITE, "pulse", "proofs")
START = datetime.date(2026, 10, 19)          # Monday of the week the log began
DIRECTORS = 3
CONTACT = "kai@govw.org"

FONTS = """@font-face{font-family:"Bricolage Grotesque";font-weight:600;font-display:swap;src:url(/fonts/bricolage-grotesque-latin-600-normal.woff2) format("woff2")}
@font-face{font-family:"Bricolage Grotesque";font-weight:800;font-display:swap;src:url(/fonts/bricolage-grotesque-latin-800-normal.woff2) format("woff2")}
@font-face{font-family:"Literata";font-weight:400;font-display:swap;src:url(/fonts/literata-latin-400-normal.woff2) format("woff2")}
@font-face{font-family:"Literata";font-weight:600;font-display:swap;src:url(/fonts/literata-latin-600-normal.woff2) format("woff2")}
@font-face{font-family:"Martian Mono";font-weight:400;font-display:swap;src:url(/fonts/martian-mono-latin-400-normal.woff2) format("woff2")}
@font-face{font-family:"Martian Mono";font-weight:600;font-display:swap;src:url(/fonts/martian-mono-latin-600-normal.woff2) format("woff2")}
"""


def words(obj):
    if isinstance(obj, str):
        return len(obj.split())
    if isinstance(obj, dict):
        return sum(words(v) for k, v in obj.items() if k not in ("hash", "prev"))
    if isinstance(obj, list):
        return sum(words(v) for v in obj)
    return 0


def pulse(today):
    entries = chain.load(REC)
    err = chain.verify(entries)
    if err:
        sys.exit(f"chain invalid, not building: {err}")
    monday = today - datetime.timedelta(days=today.weekday())
    weeks = []
    w = START
    while w <= monday:
        n = sum(1 for e in entries if w <= datetime.date.fromisoformat(e["date"]) < w + datetime.timedelta(days=7))
        weeks.append({"week": w.isoformat(), "entries": n})
        w += datetime.timedelta(days=7)
    last = max((e["logged_at"] for e in entries), default=None)
    days_since = (today - datetime.date.fromisoformat(last[:10])).days if last else None
    with_ev = sum(1 for e in entries if e.get("evidence") and not e.get("unverified"))
    return {
        "as_of": today.isoformat(),
        "measured_by": "tools/build.py, counted from the record chain (measured, not estimated)",
        "entries_total": len(entries),
        "entries_this_week": weeks[-1]["entries"] if weeks else 0,
        "by_type": {t: sum(1 for e in entries if e["type"] == t) for t in chain.TYPES},
        "reconstructed": sum(1 for e in entries if e.get("reconstructed")),
        "days_since_last_entry": days_since,
        "words": words(entries),
        "bytes": os.path.getsize(REC) if os.path.exists(REC) else 0,
        "evidence_linked_pct": round(100 * with_ev / len(entries)) if entries else 0,
        "rule_changes_logged": sum(1 for e in entries if e["type"] == "rule"),
        "participants_consented": sum(1 for e in entries if e.get("consent_recorded")),
        "participants_total": DIRECTORS,
        "report_requests": sum(1 for e in entries if e.get("report_request")),
        "sealed_notes": "not started",
        "weeks": weeks,
        "chain_head": {"seq": len(entries), "hash": entries[-1]["hash"] if entries else chain.GENESIS},
    }


def sparkline(weeks):
    w, h, gap = 560, 70, 4
    weeks = weeks[-26:]                      # half a year of weeks, filled left to right
    slot = w / 26
    bw = slot - gap
    top = max([x["entries"] for x in weeks] + [1])
    out = [f'<svg viewBox="0 -14 {w} {h + 30}" role="img" aria-label="Entries per week since the log began">']
    for i, x in enumerate(weeks):
        bh = h * x["entries"] / top
        X = i * slot
        out.append(f'<rect class="bar" x="{X:.1f}" y="{h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}"><title>Week of {x["week"]}: {x["entries"]}</title></rect>')
        if x["entries"]:
            out.append(f'<text x="{X + bw / 2:.1f}" y="{h - bh - 4:.1f}" text-anchor="middle">{x["entries"]}</text>')
    out.append(f'<line class="base" x1="0" y1="{h}" x2="{w}" y2="{h}"/>')
    out.append(f'<text x="0" y="{h + 14}">{weeks[0]["week"]}</text>' if weeks else "")
    if len(weeks) > 2:
        out.append(f'<text x="{(len(weeks) - 1) * slot + bw:.1f}" y="{h + 14}" text-anchor="end">this week</text>')
    out.append("</svg>")
    return "".join(out)


def proofs_list():
    if not os.path.isdir(PROOFS):
        return []
    days = sorted({f[5:15] for f in os.listdir(PROOFS) if f.startswith("head-") and f.endswith(".txt")}, reverse=True)
    rows = []
    for d in days[:6]:
        base = f"head-{d}"
        links = [f'<a href="/pulse/proofs/{base}.txt">head</a>']
        if os.path.exists(os.path.join(PROOFS, base + ".txt.ots")):
            links.append(f'<a href="/pulse/proofs/{base}.txt.ots">OpenTimestamps proof</a>')
        if os.path.exists(os.path.join(PROOFS, base + ".tsr")):
            links.append(f'<a href="/pulse/proofs/{base}.tsr">RFC 3161 token</a>')
        rows.append(f"<li>{d} · {' · '.join(links)}</li>")
    return rows


def render(p):
    s = lambda k, label: f'<div class="stat"><span class="v">{k}</span><span class="k">{label}</span></div>'
    kb = f'{p["bytes"] / 1024:.1f} KB'
    last = "today" if p["days_since_last_entry"] == 0 else f'{p["days_since_last_entry"]} days ago'
    prf = proofs_list()
    prf_html = (f'<ul class="proofs">{"".join(prf)}</ul>' if prf else
                '<p class="hint">Not anchored yet. The first public timestamp is added with the first weekly update.</p>')
    return f"""<section aria-labelledby="pulse-h">
    <h2 id="pulse-h">Pulse</h2>
    <p>Counted from the record every week, so anyone can see the record growing. These are volumes only: results wait for each period's report.</p>
    <div class="pulse-grid">
      {s(p["entries_total"], "entries in the record")}
      {s(p["entries_this_week"], "entries this week")}
      {s(f'{p["words"]:,}', "words of raw data")}
      {s(kb, "record size")}
      {s(last, "last entry")}
      {s(p["rule_changes_logged"], "rule changes logged")}
      {s(f'{p["evidence_linked_pct"]}%', "entries with linked evidence")}
      {s(f'{p["participants_consented"]} of {p["participants_total"]}', "participants consented")}
    </div>
    <div class="spark"><span class="label">Entries per week</span>{sparkline(p["weeks"])}</div>
    <div class="spark"><span class="label">Chain head · entry {p["chain_head"]["seq"]}</span>
      <div class="head"><b>sha256</b> {p["chain_head"]["hash"]}</div>
      <p class="hint">Each entry carries the hash of the one before it (R9). Publishing the latest hash commits us to every entry before it.</p></div>
    <div class="spark"><span class="label">Public timestamps</span>{prf_html}</div>
    <p class="hint">As of {p["as_of"]}. Includes {p["reconstructed"]} reconstructed Period 0 entr{"y" if p["reconstructed"] == 1 else "ies"}. Sealed notes: {p["sealed_notes"]}. Machine-readable: <a href="/pulse/pulse.json">pulse.json</a>.</p>
  </section>"""


def split(src):
    css = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
    js = re.search(r"<script>(.*?)</script>", src, re.S).group(1)
    body = re.sub(r"<style>.*?</style>|<script>.*?</script>|<title>.*?</title>|<meta [^>]*>|<link [^>]*>", "", src, flags=re.S)
    return css, js, body.strip()


def updates_html():
    ups = json.load(open(os.path.join(ROOT, "content", "updates.json"), encoding="utf-8"))
    li = "".join(f'<li><time datetime="{u["date"]}"><span class="id">{u["id"]}</span>{u["date"]}</time>\n        <p>{html.escape(u["text"])}</p></li>\n      ' for u in ups)
    return f'<ol class="log" reversed>\n      {li}</ol>\n    <p class="hint">Follow along: <a href="/feed.xml">Atom feed</a>.</p>', ups


def feed(ups):
    ent = "".join(f"""<entry><id>https://kailog.org/#{u['id']}</id><title>{html.escape(u['id'])}</title><updated>{u['date'] if len(u['date']) == 10 else u['date'] + '-01'}T12:00:00Z</updated><link href="https://kailog.org/"/><content type="text">{html.escape(u['text'])}</content></entry>\n""" for u in ups)
    newest = max(u["date"] if len(u["date"]) == 10 else u["date"] + "-01" for u in ups)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><id>https://kailog.org/</id><title>Kai Log updates</title><updated>{newest}T12:00:00Z</updated><author><name>GOVW Foundation, Inc.</name></author><link href="https://kailog.org/"/><link rel="self" href="https://kailog.org/feed.xml"/>
{ent}</feed>
"""


def codebook_html():
    sch = json.load(open(os.path.join(ROOT, "schema", "entry.schema.json")))
    rows = []
    for k, v in sch["properties"].items():
        kind = " · ".join(v["enum"]) if "enum" in v else v.get("type", "") + (f' ({v["format"]})' if "format" in v else "")
        req = "required" if k in sch["required"] else ""
        rows.append(f'<tr><td><code>{k}</code></td><td>{html.escape(kind)}</td><td>{html.escape(v.get("description", ""))}</td><td>{req}</td></tr>')
    return f"""<section><h2>Codebook</h2>
  <p>Every entry in the private record follows this format. It describes the shape of the data, never the data itself. Machine-readable: <a href="/schema/entry.schema.json">entry.schema.json</a> (JSON Schema 2020-12).</p>
  <div class="tablewrap"><table><thead><tr><th>Field</th><th>Values</th><th>Meaning</th><th></th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
  <h3>Hash rule</h3><p><code>hash = sha256(canonical JSON of the entry without "hash")</code>. Canonical JSON uses sorted keys, no spaces and UTF-8. The first entry's <code>prev</code> is 64 zeros. The tool that checks this is open source.</p>
</section>"""


def protocol_html():
    vs = json.load(open(os.path.join(ROOT, "protocol", "versions.json")))
    import hashlib
    rows = []
    for v in vs:
        h = hashlib.sha256(open(os.path.join(ROOT, "protocol", v["file"]), "rb").read()).hexdigest()
        rows.append(f'<tr><td><a href="/protocol/{v["file"]}">{v["version"]}</a></td><td>{v["date"]}</td><td>{html.escape(v["status"])}</td><td>{html.escape(v["change"])}</td><td><code>{h[:16]}…</code></td></tr>')
    return f"""<section><h2>Protocol versions</h2>
  <p>Every version of the logging rules is kept, dated and hashed (R1, R2). A change applies only to entries made after it.</p>
  <div class="tablewrap"><table><thead><tr><th>Version</th><th>Date</th><th>Status</th><th>Change</th><th>sha256</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
</section>"""


def shell(title, body, desc):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/atom+xml" href="/feed.xml" title="Kai Log updates">
<link rel="stylesheet" href="/site.css">
</head>
<body>
{body}
<script src="/app.js" defer></script>
</body>
</html>
"""


NAV = '<nav class="foot-nav" aria-label="More"><a href="/">Project</a> · <a href="/protocol.html">Protocol</a> · <a href="/codebook.html">Codebook</a> · <a href="/cite.html">How to cite</a> · <a href="/privacy.html">Privacy</a> · <a href="/feed.xml">Feed</a></nav>'


def main():
    today = datetime.date.fromisoformat(os.environ["KAILOG_TODAY"]) if os.environ.get("KAILOG_TODAY") else datetime.datetime.now(datetime.timezone.utc).date()
    p = pulse(today)
    src = open(os.path.join(ROOT, "src", "page.html"), encoding="utf-8").read()
    block = render(p)
    ups_html, ups = updates_html()
    src = src.replace("<!--UPDATES-->", ups_html).replace("<!--NAV-->", NAV)

    # Preview for the draft artifact (keeps the draft badge and Google Fonts)
    if "--preview" in sys.argv:
        out = sys.argv[sys.argv.index("--preview") + 1]
        open(out, "w", encoding="utf-8").write(src.replace("<!--PULSE-->", block))

    css, js, body = split(src)
    body = re.sub(r'\s*<span class="draft">.*?</span>', "", body)
    body = body.replace("<!--PULSE-->", block)
    footer = re.search(r"<footer>.*?</footer>", body, re.S).group(0)
    os.makedirs(os.path.join(SITE, "pulse", "proofs"), exist_ok=True)
    open(os.path.join(SITE, "site.css"), "w", encoding="utf-8").write(FONTS + css.strip() + "\n")
    open(os.path.join(SITE, "app.js"), "w", encoding="utf-8").write(js.strip() + "\n")
    desc = "An open research record of a small nonprofit working with an AI assistant under human oversight. A research project of GOVW Foundation, Inc."
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(shell("Kai Log", body, desc))

    head_mark = '<header class="sub"><a class="mark" href="/"><span class="h1s">Kai Log</span><span class="morse" aria-hidden="true">−·−</span></a></header>'
    for slug, title, frag in (("codebook", "Codebook", codebook_html()), ("protocol", "Protocol", protocol_html()),
                              ("cite", "How to cite", open(os.path.join(ROOT, "content", "cite.html")).read()),
                              ("privacy", "Privacy", open(os.path.join(ROOT, "content", "privacy.html")).read())):
        open(os.path.join(SITE, slug + ".html"), "w", encoding="utf-8").write(
            shell(f"{title} · Kai Log", f'<div class="wrap">{head_mark}{frag}{footer}</div>', desc))
    os.makedirs(os.path.join(SITE, "schema"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "schema", "entry.schema.json"), os.path.join(SITE, "schema", "entry.schema.json"))
    os.makedirs(os.path.join(SITE, "protocol"), exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, "protocol")):
        if f.startswith("v") and f.endswith(".md"):
            shutil.copy(os.path.join(ROOT, "protocol", f), os.path.join(SITE, "protocol", f))
    shutil.copy(os.path.join(ROOT, "CITATION.cff"), os.path.join(SITE, "CITATION.cff"))
    open(os.path.join(SITE, "feed.xml"), "w", encoding="utf-8").write(feed(ups))
    os.makedirs(os.path.join(SITE, ".well-known"), exist_ok=True)
    exp = (today + datetime.timedelta(days=365)).isoformat()
    open(os.path.join(SITE, ".well-known", "security.txt"), "w").write(
        f"Contact: mailto:security@govw.org\nExpires: {exp}T00:00:00Z\nPreferred-Languages: en, es\nCanonical: https://kailog.org/.well-known/security.txt\n")

    json.dump(p, open(os.path.join(SITE, "pulse", "pulse.json"), "w"), indent=1)
    head = os.path.join(PROOFS, f"head-{today.isoformat()}.txt")
    stamped = os.path.exists(head + ".ots") or os.path.exists(head[:-4] + ".tsr")
    if not stamped:
        open(head, "w").write(f"Kai Log record chain head\ndate {today.isoformat()}\nentries {p['chain_head']['seq']}\nsha256 {p['chain_head']['hash']}\n")
    print(f"built: {p['entries_total']} entries, {p['words']} words, head {p['chain_head']['hash'][:16]}")


if __name__ == "__main__":
    main()
