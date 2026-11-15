"""Source health: every series, every run, so a source that keeps failing cannot hide.

Each run's ``fetch`` stage notes which series downloaded, which failed but had a cached copy
(stale) and which failed with nothing to fall back on (skipped). One run's notes live in
``results/run_status.json`` and are replaced by the next run, so a series that fails every
single run looks, run by run, like bad luck. ``results/source_health.json`` keeps the running
record instead: per series, the last good download, how many runs in a row it has failed and why.

The first version of this file was rebuilt from the ``run_status.json`` of every run on main
since 18 October 2026 (``seed``), which is how ``news_war`` was found never to have downloaded once.
"""

from __future__ import annotations

import json
from pathlib import Path

HEALTH = Path("results/source_health.json")
BROKEN = 3  # runs in a row without a fresh download before a series counts as broken


def _blank() -> dict:
    return {"runs": [], "series": {}}


def read(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return _blank()


def record(health: dict, at: str, ok: list[str], skipped: dict[str, str], stale: dict[str, str] | None = None) -> dict:
    """Add one fetch run (``at``: its UTC time) to the record. A run already recorded is ignored,
    so replaying the same run_status twice changes nothing."""
    stale = stale or {}
    if at in health["runs"]:
        return health
    health["runs"] = sorted([*health["runs"], at])[-200:]
    day = at[:10]
    fresh = set(ok) - set(stale)
    for sid in sorted(set(ok) | set(skipped) | set(stale)):
        s = health["series"].setdefault(sid, {"ok": 0, "failed": 0, "streak": 0, "last_ok": None, "since": None, "error": None})
        if sid in fresh:
            s.update(ok=s["ok"] + 1, streak=0, last_ok=day, since=None, error=None)
        else:
            s["failed"] += 1
            s["streak"] += 1
            s["since"] = s["since"] or day
            s["error"] = (skipped.get(sid) or stale.get(sid) or "")[:300]
            s["cached"] = sid in stale
    return health


def update(path: Path, at: str, ok: list[str], skipped: dict[str, str], stale: dict[str, str] | None = None) -> dict:
    health = record(read(path), at, ok, skipped, stale)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(health, indent=1, sort_keys=True) + "\n")
    return health


def seed(statuses: list[dict]) -> dict:
    """The record rebuilt from saved run_status.json files, oldest first (fetch stages only)."""
    health = _blank()
    for st in statuses:
        f = (st or {}).get("stages", {}).get("fetch")
        if f and f.get("at"):
            record(health, f["at"], f.get("ok", []), f.get("skipped", {}), f.get("stale", {}))
    return health


def state(s: dict) -> str:
    if s["streak"] == 0:
        return "ok"
    if not s["ok"]:
        return "never"
    return "broken" if s["streak"] >= BROKEN else "flaky"


def reason(error: str | None) -> str:
    """GDELT's and the HTTP library's words, in plain English."""
    e = error or ""
    if "429" in e or "Busy" in e or "rate" in e.lower():
        return "the source was rate-limiting requests"
    if "JSONDecodeError" in e or "Expecting value" in e:
        return "the source answered with a plain-text notice instead of data"
    if "GDELT says" in e:
        return e.split("GDELT says", 1)[1].strip(" :")[:160]
    if "Timeout" in e or "timed out" in e:
        return "the source timed out"
    return e[:160] or "unknown"


def short(description: str) -> str:
    """"Share of world news coverage mentioning tariffs" -> "Tariffs"."""
    import re
    s = re.sub(r"^Share of (world news )?coverage (mentioning|about) ", "", description or "").split(":")[0].strip()
    return s[:1].upper() + s[1:]


def payload(health: dict, titles: dict[str, str] | None = None) -> dict | None:
    """The app's view: counts per state and every series that is not healthy, worst first."""
    if not health or not health.get("series"):
        return None
    titles = titles or {}
    items = []
    for sid, s in health["series"].items():
        st = state(s)
        items.append({"id": sid, "title": short(titles.get(sid, sid)), "state": st, "ok": s["ok"], "failed": s["failed"],
                      "streak": s["streak"], "last_ok": s["last_ok"], "since": s["since"], "cached": bool(s.get("cached")),
                      "why": reason(s["error"]) if s["streak"] else None})
    rank = {"never": 0, "broken": 1, "flaky": 2, "ok": 3}
    items.sort(key=lambda i: (rank[i["state"]], -i["streak"], i["id"]))
    counts = {k: sum(i["state"] == k for i in items) for k in rank}
    runs = health["runs"]
    return {"runs": len(runs), "first": runs[0][:10] if runs else None, "last": runs[-1][:10] if runs else None,
            "counts": counts, "series": len(items), "items": [i for i in items if i["state"] != "ok"], "broken_after": BROKEN}


def describe(p: dict | None) -> str:
    if not p:
        return "No source record yet; `psychohistory fetch` starts it in results/source_health.json."
    c = p["counts"]
    lines = [f"Source health over {p['runs']} runs ({p['first']} to {p['last']}), {p['series']} series: "
             f"{c['ok']} fresh this run, {c['flaky']} failing lately, {c['broken']} broken ({p['broken_after']}+ runs in a row), "
             f"{c['never']} never downloaded."]
    for i in p["items"]:
        when = f"since {i['since']}" if i["since"] else ""
        last = f"last good {i['last_ok']}" if i["last_ok"] else "never downloaded"
        lines.append(f"  {i['state']:7} {i['id']:22} {i['streak']:>3} runs {when:17} {last:24} {'(cached copy used) ' if i['cached'] else ''}{i['why']}")
    return "\n".join(lines)
