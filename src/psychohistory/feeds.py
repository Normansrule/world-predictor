"""Follow the forecasts from anywhere: a news feed and a small public JSON API, written next to the app.

After every forecast run GitHub Pages serves, beside the app:

* ``feed.xml``, an Atom feed (RFC 4287). Any feed reader can subscribe to it. One entry for each
  newly sealed batch (its boldest calls), one for each week of forecasts that came due (how they did,
  the closest calls and the biggest surprises) and one when the lead model changed its mind.
  Entry ids are stable, so a reader shows each one once and keeps the old ones after they leave the file.
* ``api/index.json``: every series' newest sealed forecast in one file (the chance it ends higher,
  the middle forecast, the 80% range, the dates), plus the record so far.
* ``api/series/<id>.json``: one series in full, with its recent history and the forecast fan.

They are plain files, built from the same ``data.js`` the app reads, so they say exactly what the app
says. Nothing runs on a server and nothing is tracked.

This module uses only the standard library, so the Pages workflow can run it as a plain script:
``python3 src/psychohistory/feeds.py <site folder>``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

PAGES_URL = "https://normansrule.github.io/world-predictor/"
TAG = "tag:normansrule.github.io,2026:world-predictor"
API_VERSION = 1
BOLDEST = 8  # calls listed in a "sealed" entry


def read_data(site: Path) -> dict:
    """The payload inside ``app/data/data.js`` (``window.WP_DATA={...};``)."""
    text = (Path(site) / "app" / "data" / "data.js").read_text(encoding="utf-8")
    start, end = text.index("{"), text.rindex("}")
    return json.loads(text[start:end + 1])


def _model_name(m: str | None) -> str:
    m = m or ""
    if m.startswith("timesfm"):
        return "TimesFM"
    return {"radiant": "Radiant", "chronos-bolt": "Chronos-Bolt", "seldon": "Seldon", "seldon-laws": "Seldon laws"}.get(m, m)


def _pct(v, signed: bool = False) -> str:
    if v is None:
        return "–"
    if signed:
        return f"{v * 100:+.1f}%"
    return "<1%" if v < 0.01 else ">99%" if v > 0.99 else f"{round(v * 100)}%"


def _safe_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(s))


def _day(s) -> str:
    """An RFC 3339 timestamp for a date (forecasts are sealed and judged by the day, at noon UTC)."""
    return f"{str(s)[:10]}T12:00:00Z"


# ---------- the JSON API ----------

def _summary(o: dict, base: str) -> dict:
    return {"id": o["id"], "title": o.get("title"), "area": o.get("domain"), "sealed_on": o.get("made_on"),
            "judged_on": o.get("target_date"), "chance_higher": o.get("p_up"), "middle_change": o.get("change"),
            "range80": [o.get("low"), o.get("high")], "page": f"{base}app/#series/{o['id']}",
            "detail": f"{base}api/series/{_safe_id(o['id'])}.json"}


def api(D: dict, base: str = PAGES_URL) -> tuple[dict, dict[str, dict]]:
    """The index and one document per series."""
    meta = D.get("meta") or {}
    record = (D.get("vault") or [None])[-1]
    index = {
        "api_version": API_VERSION, "generated": meta.get("generated"), "model": _model_name(meta.get("model")),
        "demo": bool(meta.get("demo")), "source": meta.get("repo"), "feed": f"{base}feed.xml",
        "notes": ("Changes are fractions (0.012 = +1.2%) from the last value before the forecast was sealed. "
                  "chance_higher is the forecast chance the series ends above that value on judged_on. "
                  "range80 is where the forecast put 80% of its weight."),
        "record": record and {"forecasts_judged": record.get("opened"), "inside80": record.get("inside80"),
                              "brier": record.get("brier"), "skill_vs_no_change": record.get("skill"), "as_of": record.get("date")},
        "series": [_summary(o, base) for o in D.get("outlook") or []],
    }
    docs = {}
    for o in D.get("outlook") or []:
        doc = _summary(o, base)
        doc.update({"api_version": API_VERSION, "generated": meta.get("generated"), "model": index["model"],
                    "description": o.get("description"),
                    "history": [{"date": d, "value": v} for d, v in o.get("history") or []],
                    "fan": [{"date": d, "q10": a, "q50": m, "q90": b} for d, a, m, b in o.get("fan") or []],
                    "radiant": [{"date": d, "q10": a, "q50": m, "q90": b} for d, a, m, b in o.get("radiant") or []] or None})
        docs[_safe_id(o["id"])] = doc
    return index, docs


# ---------- the Atom feed ----------

def entries(D: dict, base: str = PAGES_URL) -> list[dict]:
    """Feed entries, newest first: id, title, updated, link and an HTML summary."""
    model = _model_name((D.get("meta") or {}).get("model"))
    out = []
    batches: dict[str, list] = {}
    for o in D.get("outlook") or []:
        batches.setdefault(str(o.get("made_on")), []).append(o)
    for made_on, items in batches.items():
        bold = sorted(items, key=lambda o: -abs((0.5 if o.get("p_up") is None else o["p_up"]) - 0.5))[:BOLDEST]
        rows = "".join(
            f"<li><a href=\"{escape(base)}app/#series/{escape(o['id'])}\">{escape(o.get('title') or o['id'])}</a>: "
            f"{_pct(o.get('p_up'))} chance it ends higher by {escape(str(o.get('target_date')))} "
            f"(middle {_pct(o.get('change'), True)}, 80% range {_pct(o.get('low'), True)} to {_pct(o.get('high'), True)})</li>"
            for o in bold)
        out.append({"id": f"{TAG}:sealed:{made_on}", "updated": _day(made_on), "link": f"{base}app/#today",
                    "title": f"Sealed {made_on}: {len(items)} new forecasts by {model}",
                    "html": f"<p>{model} sealed {len(items)} forecasts on {escape(made_on)}. The boldest calls:</p><ul>{rows}</ul>"
                            "<p>Each one is fingerprinted when it is made and scored against what really happens.</p>"})
    brief = D.get("brief") or {}
    due = brief.get("due")
    if due:
        lead = _model_name(due.get("lead"))
        table = "".join(f"<li>{escape(_model_name(m))}: {n} forecasts on {k} series, {_pct(i)} inside the 80% range, "
                        f"{_pct(d)} right direction, skill {_pct(s, True) if s is not None else '–'} vs no change</li>"
                        for m, n, k, i, d, s in due.get("models") or [])
        near = "; ".join(f"{escape(c['title'])} (said {_pct(c.get('mid'), True)}, was {_pct(c.get('actual'), True)})" for c in due.get("nailed") or [])
        miss = "; ".join(f"{escape(c['title'])} (range {_pct(c.get('low'), True)} to {_pct(c.get('high'), True)}, was {_pct(c.get('actual'), True)})"
                         for c in due.get("surprises") or [])
        out.append({"id": f"{TAG}:due:{due['until']}", "updated": _day(due["until"]), "link": f"{base}app/#today",
                    "title": f"Came due {due['since']} to {due['until']}: how the forecasts did",
                    "html": f"<ul>{table}</ul><p><b>{escape(lead)}'s closest calls:</b> {near or 'none this week'}.</p>"
                            f"<p><b>Biggest surprises:</b> {miss or 'none: every outcome landed inside its range'}.</p>"})
    rev = brief.get("revisions")
    if rev and rev.get("items"):
        rows = "".join(f"<li>{escape(x['title'])}{' (flipped)' if x.get('flip') else ''}: {_pct(x.get('p_old'))} → {_pct(x.get('p_new'))} "
                       f"for {escape(str(x.get('target')))}</li>" for x in rev["items"])
        out.append({"id": f"{TAG}:revised:{rev['new']}", "updated": _day(rev["new"]), "link": f"{base}app/#today",
                    "title": f"{_model_name(rev.get('model'))} changed its mind on {rev.get('flips', 0)} of {rev.get('series', 0)} series",
                    "html": f"<p>Chance of ending above today's level, {escape(str(rev['old']))} batch against {escape(str(rev['new']))}:</p><ul>{rows}</ul>"})
    out.sort(key=lambda e: e["updated"], reverse=True)
    return out


def atom(D: dict, base: str = PAGES_URL) -> str:
    meta = D.get("meta") or {}
    items = entries(D, base)
    updated = max([e["updated"] for e in items] + [_day(meta.get("generated") or "1970-01-01")])
    demo = " (demo data)" if meta.get("demo") else ""
    parts = ['<?xml version="1.0" encoding="utf-8"?>',
             '<feed xmlns="http://www.w3.org/2005/Atom">',
             f"  <title>World Predictor{demo}</title>",
             "  <subtitle>Sealed forecasts for markets, world events, technology and weather, scored against what really happened.</subtitle>",
             f"  <id>{TAG}:feed</id>",
             f'  <link rel="self" type="application/atom+xml" href="{escape(base)}feed.xml"/>',
             f'  <link rel="alternate" type="text/html" href="{escape(base)}app/"/>',
             f"  <updated>{updated}</updated>",
             f"  <author><name>World Predictor</name><uri>{escape(meta.get('repo') or base)}</uri></author>",
             f'  <generator version="{escape(str(meta.get("version") or ""))}">psychohistory</generator>']
    for e in items:
        parts += ["  <entry>", f"    <id>{escape(e['id'])}</id>", f"    <title>{escape(e['title'])}</title>",
                  f"    <updated>{e['updated']}</updated>", f'    <link rel="alternate" type="text/html" href="{escape(e["link"])}"/>',
                  f'    <content type="html">{escape(e["html"])}</content>', "  </entry>"]
    parts.append("</feed>")
    return "\n".join(parts) + "\n"


def publish(site: Path, base: str = PAGES_URL) -> list[Path]:
    """Write feed.xml and api/ into ``site`` from its data.js. Returns the files written."""
    site = Path(site)
    D = read_data(site)
    written = [site / "feed.xml"]
    written[0].write_text(atom(D, base), encoding="utf-8")
    index, docs = api(D, base)
    folder = site / "api" / "series"
    folder.mkdir(parents=True, exist_ok=True)
    (site / "api" / "index.json").write_text(json.dumps(index, indent=1, allow_nan=False), encoding="utf-8")
    written.append(site / "api" / "index.json")
    for key, doc in docs.items():
        path = folder / f"{key}.json"
        path.write_text(json.dumps(doc, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":  # used by the Pages workflow, which does not install the package
    if len(sys.argv) != 2:
        sys.exit("usage: feeds.py <site folder>")
    files = publish(Path(sys.argv[1]))
    print(f"Feed and API written: {files[0]} and {len(files) - 1} JSON files")
