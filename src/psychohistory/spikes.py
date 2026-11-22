"""Spike watch: when attention jumps, where is it four weeks later?

The hype record (round 17) found that big 90-day moves in attention fade. This module looks at the
fast version: single days when a news topic or a technology's Wikipedia page gets at least twice its
usual attention (a launch, a coup, a vote). A spike's peak is easy to see after the fact; the useful
question is the one a forecast has to answer, a few days after the peak: **four weeks from now, how
far above its old level will attention be?**

Three plain rules answer it, and TimesFM answers it too:

* ``old level``: it will be back to the median of the 28 days before the spike;
* ``past spikes``: it will be where earlier spikes were at the same distance from their peak (the
  median ratio to the old level, pooled over every series' earlier spikes, known by then);
* ``no change``: it stays where it is on the day of the forecast;
* ``timesfm``: TimesFM's median for that day, sealed in the weekly ledger (and, in the backtest,
  from the saved backtest paths whose origin fell within a week after a peak).

Each is scored by how far it missed, as the absolute log ratio of forecast to outcome (0.22 is
about 25% off either way), and by how often it was within 25%. ``backtest`` replays every spike in
the history; ``seal`` writes the live calls to ``predictions/spike_ledger.csv`` on the run of the
first weekly forecast after a peak, and ``score`` checks them once their day has passed.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

SPIKE = 2.0          # a day at least this many times the usual level is a spike
BASE_DAYS = 28       # the usual level: the median of the 28 days before
GAP = 30             # days between two spikes in one series
PEAK_WINDOW = 7      # the peak is the highest day within a week of the first spike day
HORIZON = 28         # the forecast looks four weeks ahead, like the weekly ledger
LAG = 1              # in the backtest, the forecast is made the day after the peak
SEAL_WITHIN = 7      # a live spike is sealed by the first weekly forecast up to a week after its peak
RECENT = 21          # spikes this recent are shown as live
MIN_PAST = 5         # earlier spikes needed before the past-spikes rule speaks
CLOSE = math.log(1.25)  # within 25% either way
DOMAINS = ("news", "politics", "tech")
RULES = ("old level", "past spikes", "no change", "timesfm")
TIMESFM = "timesfm-2.5"

SPIKE_LEDGER = Path("predictions/spike_ledger.csv")
COLUMNS = ["made_on", "series_id", "peak_date", "peak", "base", "last_date", "last_value", "target_date",
           "old level", "past spikes", "no change", "timesfm"]


def eligible(spec) -> bool:
    return spec.domain in DOMAINS and spec.freq == "D" and not spec.id.endswith("_composite")


def daily(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").dropna()
    s.index = pd.to_datetime(s.index)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.asfreq("D").interpolate(limit=3).dropna() if len(s) else s


def find(sid: str, s: pd.Series) -> list[dict]:
    """Every spike in one series: its peak, the usual level before it, and attention against that
    level on each of the next 60 days (``after[d - 1]`` is day ``d``; NaN where not seen yet)."""
    x = daily(s)
    if len(x) < BASE_DAYS + 2:
        return []
    v = x.to_numpy(float)
    base = x.shift(1).rolling(BASE_DAYS, min_periods=BASE_DAYS * 3 // 4).median().to_numpy(float)
    out, last = [], -10 ** 9
    i = BASE_DAYS
    while i < len(v):
        b = base[i]
        if b > 0 and np.isfinite(b) and v[i] >= SPIKE * b and i - last > GAP:
            j = i + int(np.argmax(v[i:i + PEAK_WINDOW + 1]))
            while j + 1 < len(v) and v[j + 1] > v[j]:  # still climbing at the window's edge
                j += 1
            after = np.full(60, np.nan)
            seen = v[j + 1:j + 61] / b
            after[:len(seen)] = seen
            excess = v[j] - b
            half = next((d + 1 for d, r in enumerate(seen) if r * b - b <= 0.5 * excess), None)
            out.append({"series_id": sid, "start": x.index[i], "peak_date": x.index[j], "peak": float(v[j]), "base": float(b),
                        "ratio": float(v[j] / b), "half": half, "after": after})
            last = j
            i = j + GAP
        else:
            i += 1
    return out


def curve(spikes: list[dict], before: pd.Timestamp | None = None) -> np.ndarray:
    """The median ratio to the old level on each of days 1..60 after a peak, over the spikes whose
    day was already seen by ``before`` (NaN where fewer than ``MIN_PAST`` spikes count). Done as one
    array operation, as the full history has well over a thousand spikes."""
    if not spikes:
        return np.full(60, np.nan)
    a = np.vstack([s["after"] for s in spikes])
    if before is not None:
        peaks = np.array([s["peak_date"].value for s in spikes], dtype=np.int64)[:, None]
        seen = peaks + (np.arange(1, 61, dtype=np.int64) * 86_400_000_000_000)[None, :] <= pd.Timestamp(before).value
        a = np.where(seen, a, np.nan)
    count = np.isfinite(a).sum(axis=0)
    out = np.full(60, np.nan)
    ok = count >= MIN_PAST
    if ok.any():
        out[ok] = np.nanmedian(a[:, ok], axis=0)
    return out


def _err(pred, actual) -> float | None:
    if pred is None or actual is None or not (pred > 0 and actual > 0) or not np.isfinite(pred) or not np.isfinite(actual):
        return None
    return abs(math.log(pred / actual))


def backtest(data: dict[str, pd.Series], paths: pd.DataFrame | None = None, specs=None) -> pd.DataFrame:
    """Every spike in the history, forecast ``LAG`` day(s) after its peak for ``HORIZON`` days on,
    by each rule, with the past-spikes rule using only spikes seen by then. TimesFM's rows come
    from saved backtest paths whose origin fell within ``SEAL_WITHIN`` days after a peak."""
    ids = [s.id for s in specs if eligible(s)] if specs is not None else list(data)
    every = [sp for sid in ids if sid in data for sp in find(sid, data[sid])]
    tfm = {}
    if paths is not None and not paths.empty:
        tp = paths[paths["model"] == TIMESFM].assign(origin=lambda f: pd.to_datetime(f["origin"]), date=lambda f: pd.to_datetime(f["date"]))
        tfm = {sid: g for sid, g in tp.groupby("series_id")}
    rows = []
    for sp in every:
        lag = LAG + HORIZON
        actual = sp["after"][lag - 1]
        if not np.isfinite(actual):
            continue
        origin = sp["peak_date"] + pd.Timedelta(days=LAG)
        past = curve(every, before=origin)[lag - 1]  # a spike's own day 29 comes after its origin, so it never counts
        rows.append({"series_id": sp["series_id"], "peak_date": sp["peak_date"].date().isoformat(), "ratio": round(sp["ratio"], 3),
                     "half": sp["half"], "origin": origin.date().isoformat(), "days_after": lag, "actual": round(float(actual), 4),
                     "old level": 1.0, "past spikes": None if not np.isfinite(past) else round(float(past), 4),
                     "no change": round(float(sp["after"][LAG - 1]), 4), "timesfm": _tfm_backtest(tfm.get(sp["series_id"]), sp)})
    return pd.DataFrame(rows)


def _tfm_backtest(g: pd.DataFrame | None, sp: dict) -> float | None:
    """TimesFM's ratio for the backtest's target day, from a saved path (``g``: this series'
    TimesFM paths, dates parsed) whose origin fell up to a week after the peak."""
    if g is None or g.empty:
        return None
    lo, hi = sp["peak_date"], sp["peak_date"] + pd.Timedelta(days=SEAL_WITHIN)
    g = g[(g["origin"] >= lo) & (g["origin"] <= hi)]
    if g.empty:
        return None
    target = sp["peak_date"] + pd.Timedelta(days=LAG + HORIZON)
    hit = g[g["date"] == target]
    return round(float(hit["q50"].iloc[0]) / sp["base"], 4) if len(hit) else None


def score_rows(rows: pd.DataFrame) -> dict | None:
    """Per rule: how many spikes it called, its median miss and how often it was within 25%."""
    if rows is None or rows.empty:
        return None
    out = {}
    for r in RULES:
        if r not in rows:
            continue
        e = [x for x in (_err(p, a) for p, a in zip(rows[r], rows["actual"])) if x is not None]
        if e:
            out[r] = {"n": len(e), "median_miss": round(float(np.median(e)), 4), "close": int(sum(x <= CLOSE for x in e))}
    return out


def record(rows: pd.DataFrame | None, spikes: list[dict] | None = None) -> dict | None:
    """The backtest's summary: how many spikes, how fast they halve, where they are four weeks
    on, and each rule's score (TimesFM's on the spikes it has a forecast for, beside the rules on
    the same spikes, so the comparison is fair)."""
    if rows is None or rows.empty:
        return None
    rows = rows.copy()
    rows["domain"] = rows["series_id"].map(_domain)
    half = pd.to_numeric(rows["half"], errors="coerce")
    by = {}
    for d, g in rows.groupby("domain"):
        h = pd.to_numeric(g["half"], errors="coerce").dropna()
        by[d] = {"n": int(len(g)), "half": None if h.empty else float(h.median()),
                 "after": round(float(g["actual"].median()), 3), "back": _back(g["actual"])}
    tf = rows[pd.to_numeric(rows["timesfm"], errors="coerce").notna()] if "timesfm" in rows else rows.iloc[:0]
    return {"n": int(len(rows)), "series": int(rows["series_id"].nunique()),
            "first": str(rows["peak_date"].min()), "last": str(rows["peak_date"].max()),
            "half": None if half.dropna().empty else float(half.median()),
            "half_1": int((half == 1).sum()), "after": round(float(rows["actual"].median()), 3),
            "back": _back(rows["actual"]), "above": int((rows["actual"] > 1.25).sum()),
            "days_after": LAG + HORIZON, "by_domain": by, "rules": score_rows(rows),
            "timesfm_fair": score_rows(tf) if len(tf) else None, "timesfm_n": int(len(tf))}


def _back(actual: pd.Series) -> int:
    """How many were back within 25% of the old level, either way."""
    a = pd.to_numeric(actual, errors="coerce")
    return int(((a > 0) & (np.log(a.where(a > 0)).abs() <= CLOSE)).sum())


def short(description: str) -> str:
    """"Wikipedia views: SpaceX Starship" -> "SpaceX Starship"; "Share of coverage about coups" -> "Coups"."""
    import re
    s = re.sub(r"^Wikipedia views: ", "", description or "")
    s = re.sub(r"^Share of (world news )?coverage (mentioning|about) ", "", s).split(":")[0].strip()
    return s[:1].upper() + s[1:]


def _domain(sid: str) -> str:
    return "tech" if sid.startswith("wiki_") else sid.split("_", 1)[0]


def _ledger_q50(ledger: pd.DataFrame | None, sid: str, made_on: str, target: str) -> float | None:
    if ledger is None or ledger.empty:
        return None
    g = ledger[(ledger["series_id"] == sid) & (ledger["model"] == TIMESFM) & (ledger["made_on"].astype(str) == made_on)
               & (ledger["target_date"].astype(str) == target)]
    return float(g["q50"].iloc[0]) if len(g) else None


def now(data: dict[str, pd.Series], specs=None, ledger: pd.DataFrame | None = None) -> list[dict]:
    """Spikes in the last ``RECENT`` days, with each rule's call for four weeks after the newest
    day and TimesFM's, from the newest weekly forecast in the ledger when it covers that day."""
    ids = [s.id for s in specs if eligible(s)] if specs is not None else [k for k in data if _domain(k) in DOMAINS and not k.endswith("_composite")]
    every = {sid: find(sid, data[sid]) for sid in ids if sid in data}
    pooled = curve([sp for v in every.values() for sp in v])
    newest = None
    if ledger is not None and not ledger.empty:
        tl = ledger[ledger["model"] == TIMESFM]
        newest = str(tl["made_on"].max()) if len(tl) else None
    out = []
    for sid, spikes in every.items():
        if not spikes:
            continue
        sp = spikes[-1]
        x = daily(data[sid])
        last = x.index[-1]
        if (last - sp["peak_date"]).days > RECENT:
            continue
        days = (last - sp["peak_date"]).days
        target = last + pd.Timedelta(days=HORIZON)
        lag = days + HORIZON
        past = pooled[lag - 1] if lag <= 60 else np.nan
        tfm, tfm_made = None, None
        if newest:
            g = ledger[(ledger["series_id"] == sid) & (ledger["model"] == TIMESFM) & (ledger["made_on"].astype(str) == newest)]
            if len(g):
                end = g.sort_values("step").iloc[-1]
                tfm, tfm_made = float(end["q50"]) / sp["base"], {"made_on": newest, "target_date": str(end["target_date"])}
        halved = None if sp["half"] is None else (sp["peak_date"] + pd.Timedelta(days=sp["half"])).date().isoformat()
        out.append({"id": sid, "domain": _domain(sid), "peak_date": sp["peak_date"].date().isoformat(), "peak": round(sp["peak"], 4),
                    "base": round(sp["base"], 4), "ratio": round(sp["ratio"], 2), "days": days, "halved": halved,
                    "now": round(float(x.iloc[-1] / sp["base"]), 3), "last": last.date().isoformat(), "target": target.date().isoformat(),
                    "calls": {"old level": 1.0, "past spikes": None if not np.isfinite(past) else round(float(past), 3),
                              "no change": round(float(x.iloc[-1] / sp["base"]), 3), "timesfm": None if tfm is None else round(tfm, 3)},
                    "timesfm_from": tfm_made,
                    "recent": [[t.date().isoformat(), round(float(v), 4)] for t, v in x.loc[sp["peak_date"] - pd.Timedelta(days=BASE_DAYS):].items()]})
    out.sort(key=lambda it: -it["ratio"])
    return out


def seal_rows(data: dict[str, pd.Series], ledger: pd.DataFrame | None, specs=None, sealed: pd.DataFrame | None = None) -> pd.DataFrame:
    """The live calls to seal now: one row per spike, made from the newest weekly TimesFM forecast
    when that forecast's last observed day is within ``SEAL_WITHIN`` days after the peak, using
    only what was known on that day. A spike already sealed is never sealed again."""
    if ledger is None or ledger.empty:
        return pd.DataFrame(columns=COLUMNS)
    tl = ledger[ledger["model"] == TIMESFM]
    if tl.empty:
        return pd.DataFrame(columns=COLUMNS)
    made_on = str(tl["made_on"].max())
    done = set() if sealed is None or sealed.empty else set(zip(sealed["series_id"], sealed["peak_date"].astype(str)))
    ids = [s.id for s in specs if eligible(s)] if specs is not None else [k for k in data if _domain(k) in DOMAINS and not k.endswith("_composite")]
    batch = tl[tl["made_on"].astype(str) == made_on]
    every = [o for k in ids if k in data for o in find(k, data[k])]
    rows = []
    for sid in ids:
        g = batch[batch["series_id"] == sid]
        if sid not in data or g.empty:
            continue
        last_date = pd.Timestamp(str(g["last_date"].iloc[0]))
        raw = data[sid]
        known = daily(raw[pd.to_datetime(raw.index) <= last_date])
        found = find(sid, raw[pd.to_datetime(raw.index) <= last_date])
        if not found:
            continue
        sp = found[-1]
        days = (last_date - sp["peak_date"]).days
        if not 0 <= days <= SEAL_WITHIN or (sid, sp["peak_date"].date().isoformat()) in done:
            continue
        end = g.sort_values("step").iloc[-1]
        lag = (pd.Timestamp(str(end["target_date"])) - sp["peak_date"]).days
        past = curve(every, before=last_date)[lag - 1] if 1 <= lag <= 60 else np.nan  # its own later days are not seen by then
        b = sp["base"]
        rows.append({"made_on": made_on, "series_id": sid, "peak_date": sp["peak_date"].date().isoformat(), "peak": round(sp["peak"], 6),
                     "base": round(b, 6), "last_date": last_date.date().isoformat(), "last_value": round(float(known.iloc[-1]), 6),
                     "target_date": str(end["target_date"]), "old level": 1.0,
                     "past spikes": None if not np.isfinite(past) else round(float(past), 4),
                     "no change": round(float(known.iloc[-1]) / b, 4), "timesfm": round(float(end["q50"]) / b, 4)})
    return pd.DataFrame(rows, columns=COLUMNS)


def read(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path) if Path(path).exists() and Path(path).stat().st_size > 1 else None
    except (OSError, ValueError, pd.errors.EmptyDataError):
        return None


def append(rows: pd.DataFrame, path: Path = SPIKE_LEDGER) -> pd.DataFrame:
    """Add sealed calls; a spike is sealed once, so an earlier row for it always wins."""
    old = read(path)
    allrows = rows if old is None else pd.concat([old, rows], ignore_index=True)
    allrows = allrows.drop_duplicates(["series_id", "peak_date"], keep="first")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    allrows.to_csv(path, index=False)
    return allrows


def score(sealed: pd.DataFrame | None, data: dict[str, pd.Series]) -> pd.DataFrame:
    """The sealed calls whose day has come, with what happened (as a ratio to the old level)."""
    if sealed is None or sealed.empty:
        return pd.DataFrame()
    out = []
    for _, r in sealed.iterrows():
        if r["series_id"] not in data:
            continue
        x = daily(data[r["series_id"]])
        t = pd.Timestamp(str(r["target_date"]))
        if t not in x.index:
            continue
        out.append({**r.to_dict(), "actual": round(float(x.loc[t]) / float(r["base"]), 4)})
    return pd.DataFrame(out)


def verdict(rec: dict | None, live: dict | None = None) -> str:
    if not rec or rec["n"] < 10:
        return "Not enough spikes in the history for a verdict yet."
    n, rules = rec["n"], rec["rules"] or {}
    pct = lambda m: f"{math.expm1(m):.0%}"  # noqa: E731
    best = min(((k, v) for k, v in rules.items() if k != "timesfm" and v["n"] >= 10), key=lambda kv: kv[1]["median_miss"], default=None)
    text = (f"{n} spikes in {rec['series']} series since {rec['first'][:7]}: attention halved back towards its old level in a median of "
            f"{rec['half']:.0f} day{'s' if rec['half'] != 1 else ''}, and {rec['days_after']} days after the peak it sat at a median "
            f"{rec['after']:.2f} times the old level, back within 25% for {rec['back']} of {n} ({rec['back'] / n:.0%}).")
    if best:
        text += (" Four weeks on, " + ", ".join(f"\"{k}\" missed by a median {pct(v['median_miss'])} ({v['close']} of {v['n']} within 25%)"
                                                for k, v in rules.items() if k != "timesfm")
                 + f"; {best[0]} did best.")
    tf = rec.get("timesfm_fair")
    if tf and "timesfm" in tf and tf["timesfm"]["n"] >= 3:
        t, o = tf["timesfm"], tf.get("old level")
        text += (f" On the {t['n']} spikes TimesFM forecast within a week of the peak, it missed by a median {pct(t['median_miss'])}"
                 + (f", against {pct(o['median_miss'])} for \"old level\"" if o else "") + ".")
    else:
        text += " TimesFM's backtest has too few forecasts made right after a peak to judge it; the sealed ledger fills that in."
    if live and live.get("n"):
        text += f" Sealed live calls settled so far: {live['n']}."
    return text


def payload(data: dict[str, pd.Series], specs=None, paths: pd.DataFrame | None = None, ledger: pd.DataFrame | None = None,
            sealed: pd.DataFrame | None = None, titles: dict[str, str] | None = None) -> dict | None:
    """The app's Spike watch: the live spikes, the backtest record and the sealed calls so far."""
    rows = backtest(data, paths, specs)
    rec = record(rows)
    items = now(data, specs, ledger)
    if not items and not rec:
        return None
    titles = titles or {}
    for it in items:
        it["title"] = short(titles.get(it["id"], it["id"]))
    every = [sp for sid in data if _domain(sid) in DOMAINS and not sid.endswith("_composite") for sp in find(sid, data[sid])]
    cv = curve(every)
    scored = score(sealed, data)
    live = {"n": int(len(scored)), "rules": score_rows(scored) if len(scored) else None,
            "open": 0 if sealed is None else int(len(sealed) - len(scored)),
            "calls": [] if scored.empty else scored.tail(12).to_dict("records")}
    study = market_study(data, every)
    return {"made_on": max((it["last"] for it in items), default=None), "items": items, "record": rec, "live": live,
            "markets": study, "markets_verdict": market_verdict(study),
            "verdict": verdict(rec, live), "curve": [None if not np.isfinite(v) else round(float(v), 3) for v in cv],
            "rules": {"spike": SPIKE, "base_days": BASE_DAYS, "horizon": HORIZON, "lag": LAG, "gap": GAP, "min_past": MIN_PAST, "seal_within": SEAL_WITHIN}}


def describe(p: dict | None) -> str:
    if not p:
        return "No spikes found; run `psychohistory fetch` for news, politics and tech first."
    lines = [f"Spike watch: days with at least {p['rules']['spike']:g} times the median of the {p['rules']['base_days']} days before.", ""]
    if p["items"]:
        lines.append(f"{'series':26} {'peak':>10} {'x usual':>8} {'now':>6}  {'halved':>10}  in 4 weeks: old level / past spikes / no change / TimesFM")
        for it in p["items"]:
            c = it["calls"]
            f = lambda v: "–" if v is None else f"{v:.2f}x"  # noqa: E731
            lines.append(f"{it.get('title', it['id'])[:26]:26} {it['peak_date']:>10} {it['ratio']:>7.1f}x {it['now']:>5.2f}x  {it['halved'] or 'not yet':>10}  "
                         f"{f(c['old level'])} / {f(c['past spikes'])} / {f(c['no change'])} / {f(c['timesfm'])}")
    else:
        lines.append(f"No spike in the last {RECENT} days.")
    lines += ["", p["verdict"]]
    st = p.get("markets")
    if st:
        lines += ["", f"Do spikes move markets? Median move over the next {st['after']} trading days after a spike, against usual:"]
        for r in st["rows"]:
            lines.append(f"  {r['group_label']:24} {r['name']:14} {r['n']:>3} spikes  {r['size']:>6.1%} vs {r['usual']:>5.1%}  "
                         f"{r['ratio']:>5.2f}x  p {r['p']:.3f}"
                         + (f"  same quarters {r['ratio_era']:>4.2f}x p {r['p_era']:.3f}" if "p_era" in r else "")
                         + ("  passes" if r["passes"] else ""))
        lines.append(p.get("markets_verdict", ""))
    return "\n".join(lines)


# ---------- do spikes move markets? ----------

MARKETS = (("sp500", "S&P 500"), ("vix", "VIX"), ("gold", "Gold"), ("oil_wti", "Oil"), ("bitcoin", "Bitcoin"), ("us10y", "10-year yield"))
AFTER = 5          # trading days after the spike over which the market move is measured
SHUFFLES = 2000    # random sets of days for the shuffle test
GROUPS = (("news", "World news and politics", ("news", "politics")), ("tech", "Technology", ("tech",)))


def _moves(s: pd.Series) -> pd.Series:
    """Each day's move over the next ``AFTER`` trading days, from the close before it (log change),
    indexed by the day the move starts after: a spike on day t is matched with the close before t
    to the close ``AFTER`` sessions later, so a same-day reaction counts."""
    x = pd.to_numeric(s, errors="coerce").dropna()
    x.index = pd.to_datetime(x.index)
    x = x[~x.index.duplicated(keep="last")].sort_index()
    x = x[x > 0]
    lx = np.log(x.to_numpy(float))
    fwd = np.full(len(x), np.nan)
    fwd[:-AFTER] = lx[AFTER:] - lx[:-AFTER]
    return pd.Series(fwd, x.index).dropna()


def _match(moves: pd.Series, days: list[pd.Timestamp]) -> np.ndarray:
    """The move starting at the last close before each day (NaN-free, one per day that has one)."""
    idx = moves.index
    out = []
    for d in days:
        k = idx.searchsorted(d) - 1  # the last close strictly before the spike day
        if 0 <= k < len(idx):
            out.append(moves.iloc[k])
    return np.asarray(out, float)


def _era_draws(moves: pd.Series, days: list[pd.Timestamp], rng: np.random.Generator, shuffles: int) -> np.ndarray:
    """``shuffles`` sets of random days, each spike's stand-in drawn from the same calendar quarter
    as the spike, so a market's calm and wild years are matched: spikes that merely cluster in a
    volatile era do not look like spikes that move the market. Returns the |move| draws."""
    idx = moves.index
    quarter = (idx.year * 4 + (idx.month - 1) // 3).to_numpy()
    starts = {q: int(i) for q, i in zip(*np.unique(quarter, return_index=True))}
    counts = dict(zip(*np.unique(quarter, return_counts=True)))
    pos = [idx.searchsorted(d) - 1 for d in days]
    pos = [k for k in pos if 0 <= k < len(idx)]
    qs = quarter[pos]
    lo = np.array([starts[q] for q in qs]); n = np.array([counts[q] for q in qs])
    pick = lo[None, :] + np.floor(rng.random((shuffles, len(qs))) * n[None, :]).astype(int)
    return np.abs(moves.to_numpy())[pick]


def market_study(data: dict[str, pd.Series], every: list[dict] | None = None, seed: int = 0) -> dict | None:
    """For each kind of spike and each market: the median size of the market's move over the next
    week after a spike, against its median over all weeks, and a shuffle test: how often random
    days, as many as there were spikes, gave a median move at least as large. Spike days shared by
    several series count once. A second shuffle draws each random day from the same calendar quarter
    as its spike (``p_era``), so a market's wild years cannot pass for a reaction to spikes that
    happen to fall in them; a pair passes only if that stricter p survives the Benjamini-Hochberg
    cut across every pair."""
    from .monitor import false_discoveries
    if every is None:
        every = [sp for sid in data if _domain(sid) in DOMAINS and not sid.endswith("_composite") for sp in find(sid, data[sid])]
    rng = np.random.default_rng(seed)
    rows = []
    for key, label, areas in GROUPS:
        days = sorted({sp["peak_date"].normalize() for sp in every if _domain(sp["series_id"]) in areas})
        if len(days) < 5:
            continue
        for mid, name in MARKETS:
            if mid not in data:
                continue
            mv = _moves(data[mid])
            if len(mv) < 60:
                continue
            lo, hi = mv.index[0], mv.index[-1]
            inside = [d for d in days if lo < d <= hi]
            hit = _match(mv, inside)
            if len(hit) < 5:
                continue
            size, usual = float(np.median(np.abs(hit))), float(np.median(np.abs(mv)))
            pool = np.abs(mv.to_numpy())
            draws = np.median(pool[rng.integers(0, len(pool), size=(SHUFFLES, len(hit)))], axis=1)
            p = float((1 + (draws >= size).sum()) / (SHUFFLES + 1))
            era = np.median(_era_draws(mv, inside, rng, SHUFFLES), axis=1)
            p_era = float((1 + (era >= size).sum()) / (SHUFFLES + 1))
            usual_era = float(np.median(era))
            rows.append({"group": key, "group_label": label, "market": mid, "name": name, "n": int(len(hit)),
                         "size": round(size, 5), "usual": round(usual, 5), "ratio": round(size / usual, 3) if usual else None,
                         "median": round(float(np.median(hit)), 5), "up": int((hit > 0).sum()), "p": round(p, 4),
                         "usual_era": round(usual_era, 5), "ratio_era": round(size / usual_era, 3) if usual_era else None,
                         "p_era": round(p_era, 4)})
    if not rows:
        return None
    cut = false_discoveries([r["p_era"] for r in rows])
    plain = false_discoveries([r["p"] for r in rows])
    for r in rows:
        r["passes"] = bool(cut >= 0 and r["p_era"] <= cut)
        r["passes_plain"] = bool(plain >= 0 and r["p"] <= plain)
    return {"rows": rows, "after": AFTER, "shuffles": SHUFFLES, "passing": int(sum(r["passes"] for r in rows)),
            "passing_plain": int(sum(r["passes_plain"] for r in rows)), "tests": len(rows)}


def market_verdict(st: dict | None) -> str:
    if not st:
        return "Not enough spikes and market history for the market test yet."
    rows = st["rows"]
    big = max(rows, key=lambda r: r["ratio"] or 0)
    text = (f"Across {st['tests']} pairs of spike kind and market, the biggest gap was {big['name']} after {big['group_label'].lower()} spikes: "
            f"a median move of {big['size']:.1%} over the next {st['after']} trading days against {big['usual']:.1%} usually "
            f"({big['ratio']:.2f} times, shuffle p {big['p']:.3f}).")
    if "p_era" in big:
        text += (f" Against days from the same quarters, when the market was as calm or as wild, the move was "
                 f"{big['ratio_era']:.2f} times usual (p {big['p_era']:.3f}).")
    if st["passing"]:
        names = ", ".join(f"{r['name']} after {r['group_label'].lower()} spikes" for r in rows if r["passes"])
        text += f" {st['passing']} pair{'s' if st['passing'] != 1 else ''} passed the false-discovery cut against same-quarter days: {names}."
    elif st.get("passing_plain"):
        names = ", ".join(f"{r['name']} after {r['group_label'].lower()} spikes" for r in rows if r.get("passes_plain"))
        text += (f" {names} passed against random days from any year but not against days from the same quarters, "
                 "so the gap comes from when the spikes happened (the market's wilder years), not from the spikes. "
                 "This data shows no reliable link between attention spikes and bigger market moves.")
    else:
        text += " None passed the false-discovery cut for testing every pair at once, so this data shows no reliable link between attention spikes and bigger market moves."
    return text
