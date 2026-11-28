"""The fast lane: does anything we follow move before markets do?

Trading desks win when they learn something before the rest of the market has. This module asks
that question of every source the app already follows, honestly and out of sample:

1. **Lead-lag scan.** For every market, every other market and every news, politics and Wikipedia
   attention series is tried as an early signal at three lags (the cross-market lead-lag test in
   Vibe-Trading's correlation-analysis skill). A link has to show on the years before ``TEST_FROM``
   and then hold, with the same sign, on the years after, which it never saw. The scan reports how
   many held against how many chance alone would give.
2. **Fear clock.** Market fear (the VIX) overreacts and then fades. An Ornstein-Uhlenbeck fit (the
   half-life method in Vibe-Trading's quant library) on the last three years before each day gives
   how fast fear returns to normal and which way it should go next; scored on held-out days with a
   block bootstrap so the interval is honest.
3. **Risk first: how big a move to expect.** AutoHedge sizes risk before it acts. For every market
   the size of next week's move is forecast from its own recent swings, and the VIX and attention
   spikes are added only when they earn their place on the training years (screened on a validation
   slice, never on the test years). The result is a range for next week meant to hold 8 times in 10,
   with its held-out coverage beside it.

Timing is strict: anything that closes after the US market (crypto, the euro, news and Wikipedia
days, which end at midnight UTC) is only used from the day after.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import catalog

TEST_FROM = "2021-01-01"  # every number shown is from on or after this day; nothing after it trains anything it is scored on
LATE = {"bitcoin", "ethereum", "solana", "xrp", "eurusd", "usdjpy", "gbpusd"}  # close after the US close
LAGS = (0, 1, 2)  # extra trading days between the signal and the day it predicts
MIN_DAYS = 500
HALF_WIN = 750  # the fear clock learns from the last three years before each day
ZQ = 0.8  # ranges are meant to hold 8 times in 10
WEEK = 5
VOL_BASE = ["rv5", "rv20", "rv60", "abs1"]
VOL_EXTRA = ["vix", "vix_chg5", "mkt_abs1", "attn"]
OUT = Path("results/web/fastlane.json")


def markets(specs=None) -> list[str]:
    specs = specs or catalog.CATALOG
    return [s.id for s in specs if s.domain == "markets" and s.freq in ("B", "D")]


def attention(specs=None) -> list[str]:
    specs = specs or catalog.CATALOG
    return [s.id for s in specs if s.source in ("gdelt", "wikipedia") or (s.source == "composite" and s.domain != "markets")]


def frame(data: dict[str, pd.Series], specs=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Prices on the US trading calendar, their daily log changes, and attention jumps known by the
    end of the day before each trading day."""
    mk = {k: data[k] for k in markets(specs) if k in data and len(data[k].dropna()) > 60}
    anchor = "sp500" if "sp500" in mk else (max(mk, key=lambda k: len(mk[k])) if mk else None)
    if anchor is None:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    days = pd.DatetimeIndex(mk[anchor].dropna().index).normalize().unique().sort_values()
    px = pd.DataFrame({k: _daily(v).reindex(days, method="ffill", limit=3) for k, v in mk.items()})
    lr = np.log(px.where(px > 0)).diff()
    att = {k: _daily(data[k]) for k in attention(specs) if k in data and len(data[k].dropna()) > 60}
    if att:
        a = pd.DataFrame(att).asfreq("D")
        la = np.log(a.where(a > 0))
        jump = (la - la.rolling(7, min_periods=4).mean().shift(1)) / la.diff().rolling(90, min_periods=30).std()
        jump = jump.clip(-6, 8).shift(1).reindex(days, method="ffill", limit=4)  # known by the end of the day before
    else:
        jump = pd.DataFrame(index=days)
    return px, lr, jump


def _daily(s: pd.Series) -> pd.Series:
    s = s.dropna().copy()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize() if getattr(s.index, "tz", None) else pd.DatetimeIndex(s.index).normalize()
    return s[~s.index.duplicated(keep="last")].sort_index().astype(float)


def _shift(target: str, source: str) -> int:
    """A day's delay when either side closes after the US market, so no signal is used before it exists."""
    return 1 if (target in LATE or source in LATE) else 0


def _ic(x: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < 60:
        return float("nan"), n
    rx, ry = pd.Series(x[ok]).rank().to_numpy(), pd.Series(y[ok]).rank().to_numpy()
    rx, ry = rx - rx.mean(), ry - ry.mean()
    den = math.sqrt(float((rx ** 2).sum() * (ry ** 2).sum()))
    return (float((rx * ry).sum() / den) if den > 0 else float("nan")), n


def scan(px: pd.DataFrame, lr: pd.DataFrame, jump: pd.DataFrame, test_from: str = TEST_FROM) -> dict:
    """Every source against every market's next-day move at every lag: first on the years before
    ``test_from``, then on the years after for the links that showed."""
    cut = pd.Timestamp(test_from)
    rows = []
    for t in lr.columns:
        y = lr[t].shift(-1)  # tomorrow's move, from today's close
        train, test = (y.index < cut), (y.index >= cut)
        if train.sum() < MIN_DAYS // 2 or test.sum() < 120:
            continue
        sources = [(s, lr[s], "market") for s in lr.columns if s != t] + [(s, jump[s], "attention") for s in jump.columns]
        for s, x, kind in sources:
            for lag in LAGS:
                sig = x.shift(lag + (_shift(t, s) if kind == "market" else 0)).to_numpy()
                a, na = _ic(sig[train], y.to_numpy()[train])
                if not np.isfinite(a):
                    continue
                b, nb = _ic(sig[test], y.to_numpy()[test])
                rows.append({"target": t, "source": s, "kind": kind, "lag": lag, "ic_train": a, "n_train": na, "ic_test": b, "n_test": nb})
    df = pd.DataFrame(rows)
    if df.empty:
        return {"tested": 0, "showed": 0, "held": 0, "expected": 0.0, "links": []}
    df["showed"] = df["ic_train"].abs() > 1.96 / np.sqrt(df["n_train"])
    df["held"] = df["showed"] & (np.sign(df["ic_test"]) == np.sign(df["ic_train"])) & (df["ic_test"].abs() > 1.96 / np.sqrt(df["n_test"]))
    shown = df[df["showed"]].copy()
    shown["verdict"] = np.where(shown["held"], "held", np.where(np.sign(shown["ic_test"]) == np.sign(shown["ic_train"]), "faded", "flipped"))
    shown = shown.reindex(shown["ic_train"].abs().sort_values(ascending=False).index)
    links = [{"target": r.target, "source": r.source, "kind": r.kind, "lag": int(r.lag), "ic_train": round(float(r.ic_train), 3),
              "ic_test": round(float(r.ic_test), 3) if np.isfinite(r.ic_test) else None, "verdict": r.verdict}
             for r in shown.head(40).itertuples()]
    held = df[df["held"]]
    return {"tested": int(len(df)), "showed": int(df["showed"].sum()), "held": int(len(held)),
            "expected": round(float(df["showed"].sum()) * 0.025, 1),  # same sign and significant by luck alone
            "held_links": [{"target": r.target, "source": r.source, "lag": int(r.lag), "ic_train": round(float(r.ic_train), 3),
                            "ic_test": round(float(r.ic_test), 3)} for r in held.reindex(held["ic_test"].abs().sort_values(ascending=False).index).head(12).itertuples()],
            "links": links, "test_from": test_from}


def ou_fit(x: np.ndarray) -> tuple[float, float]:
    """Daily pull back to the mean (theta) and the mean, from x_{t+1} - x_t = a + b x_t."""
    dx, xx = np.diff(x), x[:-1]
    slope, icpt = np.polyfit(xx, dx, 1)
    if not np.isfinite(slope) or slope >= 0:
        return 0.0, float(np.mean(x))
    theta = min(-slope, 0.99)
    return float(theta), float(icpt / -slope)


def fear_walk(level: pd.Series, h: int, test_from: str = TEST_FROM, refit: int = 21) -> pd.DataFrame:
    """Expected change of log fear over ``h`` days from a fit on the three years before, against what happened."""
    s = np.log(level.dropna().where(level.dropna() > 0)).dropna()
    idx, out = s.index, []
    for k0 in range(int(np.searchsorted(idx, pd.Timestamp(test_from))), len(s), refit):
        tr = s.iloc[max(0, k0 - HALF_WIN - h): k0 - h].to_numpy()  # values whose next-day moves were known by then
        if len(tr) < 250:
            continue
        theta, mu = ou_fit(tr)
        for i in range(k0, min(k0 + refit, len(s) - h)):
            out.append((idx[i], (mu - s.iloc[i]) * (1 - (1 - theta) ** h), s.iloc[i + h] - s.iloc[i], math.log(2) / theta if theta > 0 else float("inf")))
    return pd.DataFrame(out, columns=["date", "expect", "real", "half"]).set_index("date")


def _boot(hits: np.ndarray, block: int = 21, draws: int = 400, seed: int = 0) -> tuple[float, float]:
    nb = len(hits) // block
    if nb < 4:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    bs = [np.mean(np.concatenate([hits[j * block:(j + 1) * block] for j in rng.integers(0, nb, nb)])) for _ in range(draws)]
    return float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))


def fear_clock(px: pd.DataFrame, test_from: str = TEST_FROM) -> dict | None:
    if "vix" not in px or px["vix"].dropna().shape[0] < HALF_WIN + 300:
        return None
    level = px["vix"].dropna()
    record = []
    for h in (1, WEEK, 21):
        w = fear_walk(level, h, test_from)
        w = w[w["expect"] != 0]
        if len(w) < 120:
            continue
        hit = (np.sign(w["expect"]) == np.sign(w["real"])).to_numpy().astype(float)
        strong = (w["expect"].abs() >= w["expect"].abs().quantile(0.75)).to_numpy()
        lo, hi = _boot(hit)
        record.append({"h": h, "n": int(len(w)), "hit": round(float(hit.mean()), 3), "lo": round(lo, 3), "hi": round(hi, 3),
                       "strong": round(float(hit[strong].mean()), 3), "n_strong": int(strong.sum())})
    if not record:
        return None
    x = np.log(level.iloc[-HALF_WIN:].to_numpy())
    theta, mu = ou_fit(x)
    now = float(level.iloc[-1])
    ahead = {h: float(math.exp(math.log(now) + (mu - math.log(now)) * (1 - (1 - theta) ** h))) for h in (WEEK, 21)}
    week = next((r for r in record if r["h"] == WEEK), record[0])
    return {"now": round(now, 2), "date": level.index[-1].date().isoformat(), "normal": round(math.exp(mu), 2),
            "half_life": round(math.log(2) / theta, 1) if theta > 0 else None,
            "week": round(ahead[WEEK], 2), "month": round(ahead[21], 2),
            "falls": bool(ahead[WEEK] < now), "chance": week["hit"], "record": record, "test_from": test_from}


def vol_feats(t: str, px: pd.DataFrame, lr: pd.DataFrame, jump: pd.DataFrame) -> pd.DataFrame:
    r = lr[t]
    lag = 1 if t in LATE else 0
    f = {"rv5": np.log(r.rolling(5).std().shift(lag) + 1e-6), "rv20": np.log(r.rolling(20).std().shift(lag) + 1e-6),
         "rv60": np.log(r.rolling(60).std().shift(lag) + 1e-6), "abs1": np.log(r.abs().shift(lag) + 1e-4)}
    if "vix" in px:
        lv = np.log(px["vix"].where(px["vix"] > 0))
        f["vix"], f["vix_chg5"] = lv.shift(lag), lv.diff(5).shift(lag)
    if "sp500" in lr:
        f["mkt_abs1"] = np.log(lr["sp500"].abs().shift(lag) + 1e-4)
    if len(jump.columns):
        f["attn"] = jump.max(axis=1)
    return pd.DataFrame(f)


def _fit(tr: pd.DataFrame, cols: list[str]):
    A = np.c_[np.ones(len(tr)), tr[cols].to_numpy()]
    beta = np.linalg.lstsq(A, tr["y"].to_numpy(), rcond=None)[0]
    k = float(np.quantile(tr["fut"].abs().to_numpy() / np.exp(A @ beta), ZQ))
    return beta, k


def _width(df: pd.DataFrame, cols: list[str], beta, k) -> np.ndarray:
    return k * np.exp(np.c_[np.ones(len(df)), df[cols].to_numpy()] @ beta)


def iscore(w: np.ndarray, fut: np.ndarray) -> np.ndarray:
    """Interval score of the range +-w around no change: its width plus a penalty for each miss."""
    return 2 * w + (2 / (1 - ZQ)) * np.maximum(np.abs(fut) - w, 0)


def screen(tr: pd.DataFrame, extra: list[str]) -> list[str]:
    """Forward selection on the last 30% of the training days only: an extra signal stays when it
    makes the range at least half a percent better there."""
    cut = int(len(tr) * 0.7)
    a, v = tr.iloc[:cut], tr.iloc[cut:]
    cols = list(VOL_BASE)
    best = iscore(_width(v, cols, *_fit(a, cols)), v["fut"].to_numpy()).mean()
    while True:
        trial = [(iscore(_width(v, cols + [c], *_fit(a, cols + [c])), v["fut"].to_numpy()).mean(), c) for c in extra if c not in cols]
        if not trial:
            return cols
        s, c = min(trial)
        if s >= best * 0.995:
            return cols
        cols, best = cols + [c], s


def sizing(t: str, px: pd.DataFrame, lr: pd.DataFrame, jump: pd.DataFrame, test_from: str = TEST_FROM, refit: int = 63) -> dict | None:
    """Walk forward: refit every quarter on the days before, score the next quarter's weekly moves."""
    X = vol_feats(t, px, lr, jump)
    extra = [c for c in VOL_EXTRA if c in X]
    fut = lr[t].rolling(WEEK).sum().shift(-WEEK)
    df = pd.concat([X, np.log(fut.abs() + 1e-4).rename("y"), fut.rename("fut")], axis=1).dropna()
    if len(df) < MIN_DAYS + 120:
        return None
    idx = df.index
    test = np.where(idx >= pd.Timestamp(test_from))[0]
    parts, picked = [], []
    for k in range(0, len(test), refit):
        b = test[k:k + refit]
        tr = df[df.index < idx[b[0]] - pd.Timedelta(days=WEEK * 2 + 2)]  # purged: training moves had all settled
        if len(tr) < MIN_DAYS:
            continue
        cols = screen(tr, extra)
        picked += [c for c in cols if c not in VOL_BASE]
        te = df.iloc[b]
        parts.append(pd.DataFrame({"base": _width(te, VOL_BASE, *_fit(tr, VOL_BASE)), "fast": _width(te, cols, *_fit(tr, cols)),
                                   "fut": te["fut"].to_numpy()}, index=idx[b]))
    if not parts:
        return None
    w = pd.concat(parts)
    sb, sf = iscore(w["base"].to_numpy(), w["fut"].to_numpy()).mean(), iscore(w["fast"].to_numpy(), w["fut"].to_numpy()).mean()
    # today's range for the coming week, from every day so far (the latest five have not settled, so they are left out)
    live = X.dropna()
    tr = df[df.index < live.index[-1] - pd.Timedelta(days=WEEK * 2 + 2)]
    cols = screen(tr, extra) if len(tr) >= MIN_DAYS else list(VOL_BASE)
    width = float(_width(live.iloc[[-1]], cols, *_fit(tr, cols))[0]) if len(tr) >= MIN_DAYS else float("nan")
    uses = sorted(set(picked), key=picked.count, reverse=True)
    return {"id": t, "n": int(len(w)), "inside_base": round(float((w["fut"].abs() <= w["base"]).mean()), 3),
            "inside": round(float((w["fut"].abs() <= w["fast"]).mean()), 3), "gain": round(float(1 - sf / sb), 4),
            "move": round(float(math.expm1(width)), 4) if np.isfinite(width) else None, "uses_now": [c for c in cols if c not in VOL_BASE],
            "uses": uses[:3], "date": live.index[-1].date().isoformat()}


def payload(data: dict[str, pd.Series], specs=None, test_from: str = TEST_FROM) -> dict | None:
    px, lr, jump = frame(data, specs)
    if px.empty or len(px) < MIN_DAYS + 120:
        return None
    from .tally import NAMES  # plain names, as the Track record writes them
    names = {s.id: NAMES.get(s.id, (s.description, ""))[0] for s in (specs or catalog.CATALOG)}
    sized = [r for r in (sizing(t, px, lr, jump, test_from) for t in px.columns) if r]
    sized.sort(key=lambda r: -(r["move"] or 0))
    return {"scan": scan(px, lr, jump, test_from), "fear": fear_clock(px, test_from), "sizing": sized,
            "names": {k: names.get(k, k) for k in set(px.columns) | set(jump.columns)}, "test_from": test_from,
            "through": px.index[-1].date().isoformat()}


def write(p: dict | None, path: Path = OUT) -> Path | None:
    if p is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(p, separators=(",", ":"), allow_nan=False, default=lambda o: None))
    return path


def describe(p: dict | None) -> str:
    if not p:
        return "The fast lane needs at least two years of daily market history."
    s, lines = p["scan"], []
    lines.append(f"Fast lane, scored from {p['test_from']} on days no fit had seen (data through {p['through']}).")
    lines.append(f"Lead-lag scan: {s['tested']:,} source-to-market links tried; {s['showed']:,} showed before {p['test_from']}; "
                 f"{s['held']} still held after it, against about {s['expected']} by luck alone.")
    for l in s.get("held_links", [])[:5]:
        lines.append(f"  {l['source']} -> {l['target']} (lag {l['lag']}): {l['ic_train']:+.3f} before, {l['ic_test']:+.3f} after")
    f = p.get("fear")
    if f:
        lines.append(f"Fear clock: VIX {f['now']} on {f['date']}, normal about {f['normal']}, half-life {f['half_life']} trading days; "
                     f"expects {f['week']} in a week and {f['month']} in a month.")
        for r in f["record"]:
            lines.append(f"  {r['h']:>2} days ahead: right {r['hit']:.1%} of {r['n']} days (95% {r['lo']:.1%}-{r['hi']:.1%}); strongest quarter {r['strong']:.1%}")
    if p["sizing"]:
        g = np.mean([r["gain"] for r in p["sizing"]])
        better = sum(r["gain"] > 0 for r in p["sizing"])
        lines.append(f"Risk first, next week's move: ranges held {np.mean([r['inside'] for r in p['sizing']]):.1%} (aim 80%); "
                     f"fast signals made the range better for {better} of {len(p['sizing'])} markets (mean {g:+.2%}).")
        for r in p["sizing"][:6]:
            lines.append(f"  {r['id']:<12} +-{(r['move'] or 0):.1%} this week; held {r['inside']:.0%}; uses {', '.join(r['uses_now']) or 'its own swings'}")
    return "\n".join(lines)
