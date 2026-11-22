"""The track record in plain words: every sealed forecast read as a call anyone can check.

Each weekly forecast gives, for every series and every day ahead, the chance that the value will be
higher than the last one it saw (``p_up`` in the ledger). Read plainly, that is a call: "gold will be
higher" at 64%, or "war will be in the news less" at 71%. When the day comes the call was right or
wrong. This module turns the sealed ledger into those calls and keeps the score:

- **standing calls**: for each series and each day, the newest call sealed before that day (what the
  app was saying going into it), so one day of one series counts once however many forecasts
  covered it;
- the **running tally** since the first sealed forecast: right, wrong and the share right, overall,
  by area, by how sure the call was, and against two yardsticks (a coin flip, and the best single
  guess for each area picked with hindsight);
- **every day's calls** with what happened;
- **what it says now**: the newest call for about a week ahead, per series, in the same words.

Nothing here is new forecasting: it only reads ``predictions/ledger.csv`` and ``predictions/scored.csv``
as they were sealed.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

MODEL = "timesfm-2.5"
# How sure a call was, in words. The bottom band is called a toss-up because it has been one:
# on the first month's record, calls at 50-60% were right about half the time.
BANDS = [(0.8, "very likely", "Very likely"), (0.7, "likely", "Likely"), (0.6, "leans", "Leans"), (0.0, "tossup", "Toss-up")]
WEEK = {"B": 5, "D": 7}  # steps for "about a week ahead"

# kind: how a rise and a fall read for this series.
WORDS = {
    "price": ("will be higher", "will be lower", "went up", "went down"),
    "talk": ("will be in the news more", "will be in the news less", "more in the news", "less in the news"),
    "interest": ("will get more attention", "will get less attention", "more attention", "less attention"),
    "temp": ("will be warmer", "will be cooler", "warmer", "cooler"),
    "ice": ("will grow", "will shrink", "grew", "shrank"),
    "count": ("will be more frequent", "will be less frequent", "more", "fewer"),
    "share": ("will rise", "will fall", "rose", "fell"),
    "rain": ("will get rain (1 mm or more)", "will stay dry", "rained", "stayed dry"),
}
RAIN = 1.0  # millimetres in a day that count as rain: the usual meteorological "rain day"
NAMES = {
    "news_war": ("War", "talk"), "news_election": ("Elections", "talk"), "news_inflation": ("Inflation", "talk"),
    "news_climate": ("Climate change", "talk"), "news_pandemic": ("Disease outbreaks", "talk"), "news_protest": ("Protests", "talk"),
    "news_composite": ("The big news topics", "talk"),
    "politics_sanctions": ("Sanctions", "talk"), "politics_tariffs": ("Tariffs", "talk"), "politics_ceasefire": ("Ceasefires and peace talks", "talk"),
    "politics_coup": ("Coups", "talk"), "politics_impeachment": ("Impeachments", "talk"), "politics_referendum": ("Referendums", "talk"),
    "politics_composite": ("The big political topics", "talk"),
    "sp500": ("The S&P 500", "price"), "msci_world": ("World stocks", "price"), "nasdaq100": ("The Nasdaq-100", "price"),
    "aapl": ("Apple stock", "price"), "nvda": ("NVIDIA stock", "price"), "tsla": ("Tesla stock", "price"), "xom": ("Exxon stock", "price"),
    "msft": ("Microsoft stock", "price"), "amzn": ("Amazon stock", "price"), "googl": ("Google (Alphabet) stock", "price"),
    "ethereum": ("Ether", "price"), "natgas": ("Natural gas", "price"), "eurusd": ("The euro against the dollar", "price"),
    "gold": ("Gold", "price"), "silver": ("Silver", "price"), "us10y": ("The 10-year US interest rate", "price"),
    "tlt": ("Long US bonds", "price"), "vix": ("Market fear (VIX)", "price"), "oil_wti": ("Oil", "price"),
    "copper": ("Copper", "price"), "bitcoin": ("Bitcoin", "price"),
    "wiki_llm": ("Large language models", "interest"), "wiki_ai": ("AI", "interest"), "wiki_quantum": ("Quantum computing", "interest"),
    "wiki_crispr": ("CRISPR", "interest"), "wiki_ev": ("Electric cars", "interest"), "wiki_fusion": ("Fusion power", "interest"),
    "wiki_humanoid": ("Humanoid robots", "interest"), "wiki_battery": ("Solid-state batteries", "interest"),
    "wiki_gene_therapy": ("Gene therapy", "interest"), "wiki_self_driving": ("Self-driving cars", "interest"),
    "wiki_starship": ("SpaceX Starship", "interest"),
    "wiki_smr": ("Small nuclear reactors", "interest"), "wiki_ar": ("Augmented reality", "interest"), "tech_composite": ("The big technologies", "interest"),
    "adoption_solar": ("Solar's share of electricity", "share"), "adoption_wind": ("Wind's share of electricity", "share"),
    "adoption_internet": ("People online", "share"), "adoption_ev": ("Electric cars' share of sales", "share"),
    "space_launches": ("Space launches", "share"),
    "weather_world_air": ("The world's air", "temp"), "weather_world_sea": ("The oceans", "temp"),
    "weather_arctic_ice": ("Arctic sea ice", "ice"), "weather_london": ("London", "temp"), "weather_new_delhi": ("New Delhi", "temp"),
    "weather_tokyo": ("Tokyo", "temp"), "weather_sydney": ("Sydney", "temp"), "weather_los_angeles": ("Los Angeles", "temp"), "weather_new_york": ("New York", "temp"),
    "quakes_m45": ("Big earthquakes", "count"),
    "rain_london": ("London", "rain"), "rain_new_delhi": ("New Delhi", "rain"), "rain_tokyo": ("Tokyo", "rain"),
    "rain_sydney": ("Sydney", "rain"), "rain_los_angeles": ("Los Angeles", "rain"), "rain_new_york": ("New York", "rain"),
}
AREAS = [("markets", "Markets"), ("news", "World news"), ("politics", "Politics"), ("tech", "Technology"), ("weather", "Weather")]


def is_rain(series_id: str) -> bool:
    return NAMES.get(series_id, ("", ""))[1] == "rain"


def chance_up(series_id: str, row) -> float:
    """The chance the call is about: of rain (1 mm or more) for a rain series, read from the
    forecast's 10th, 50th and 90th percentiles, else of ending higher than the last value."""
    if is_rain(series_id):
        from .frames import p_up3
        return p_up3(float(row["q10"]), float(row["q50"]), float(row["q90"]), RAIN)
    return float(row["p_up"])


def name(series_id: str) -> str:
    return NAMES.get(series_id, (series_id, "price"))[0]


def sentence(series_id: str, up: bool) -> str:
    """The call in words: "Gold will be higher", "War will be in the news less"."""
    n, kind = NAMES.get(series_id, (series_id, "price"))
    return f"{n} {WORDS[kind][0 if up else 1]}"


def outcome_words(series_id: str, up: bool) -> str:
    return WORDS[NAMES.get(series_id, (series_id, "price"))[1]][2 if up else 3]


def band(chance: float) -> tuple[str, str]:
    for floor, key, label in BANDS:
        if chance >= floor:
            return key, label
    return BANDS[-1][1], BANDS[-1][2]


def standing(scored: pd.DataFrame | None, model: str = MODEL) -> pd.DataFrame:
    """One call per series per day: the newest one sealed before the day, read as up or down, with
    what happened. Days where the value did not move at all are left out (neither call was right)."""
    cols = ["series_id", "domain", "made_on", "last_date", "target_date", "step", "last_value", "actual", "p_up", "q50",
            "up", "chance", "went_up", "right", "change", "delta", "band"]
    if scored is None or scored.empty or "p_up" not in scored:
        return pd.DataFrame(columns=cols)
    s = scored[(scored["model"] == model) & scored["p_up"].notna() & scored["actual"].notna()].copy()
    if s.empty:
        return pd.DataFrame(columns=cols)
    for c in ("made_on", "last_date", "target_date"):
        s[c] = pd.to_datetime(s[c], errors="coerce", format="mixed")
    s = s.dropna(subset=["made_on", "last_date", "target_date"])
    s = s[s["made_on"] < s["target_date"]]
    s = s.sort_values(["made_on", "step"]).groupby(["series_id", "target_date"]).tail(1)  # the newest call going into the day
    rain = np.array([is_rain(x) for x in s["series_id"]], dtype=bool)
    s = s[rain | (s["actual"] != s["last_value"]).to_numpy()].copy()  # a dry day after a dry day still settles a rain call
    rain = np.array([is_rain(x) for x in s["series_id"]], dtype=bool)
    if "q50" not in s:
        s["q50"] = np.nan
    s["p_up"] = [chance_up(sid, row) if rn else row["p_up"] for sid, rn, (_, row) in zip(s["series_id"], rain, s.iterrows())] if rain.any() else s["p_up"]
    s["up"] = s["p_up"] >= 0.5
    s["chance"] = np.where(s["up"], s["p_up"], 1 - s["p_up"])
    s["went_up"] = np.where(rain, s["actual"] >= RAIN, s["actual"] > s["last_value"])
    s["right"] = s["up"] == s["went_up"]
    with np.errstate(divide="ignore", invalid="ignore"):
        s["change"] = np.where(rain, np.nan, s["actual"] / s["last_value"] - 1)
    s["delta"] = np.where(rain, s["actual"], s["actual"] - s["last_value"])
    s["band"] = [band(c)[0] for c in s["chance"]]
    return s.sort_values(["target_date", "domain", "series_id"])[cols].reset_index(drop=True)


def _score(rows: pd.DataFrame) -> dict:
    n = int(len(rows)); right = int(rows["right"].sum()) if n else 0
    return {"n": n, "right": right, "wrong": n - right, "share": round(right / n, 4) if n else None}


def _p_better_than_coin(right: int, n: int) -> float | None:
    """One-sided binomial p of doing at least this well by flipping a coin (calls on neighbouring
    days of one series are not independent, so read it as a rough guide)."""
    if not n:
        return None
    return float(sum(math.comb(n, k) for k in range(right, n + 1)) / 2 ** n) if n <= 1000 else \
        float(0.5 * math.erfc((right - 0.5 - n / 2) / math.sqrt(n / 4) / math.sqrt(2)))


def record(calls: pd.DataFrame) -> dict | None:
    """The running tally: overall, by area, by how sure, the last seven days, and the yardsticks."""
    if calls is None or calls.empty:
        return None
    out = {"total": _score(calls), "first": calls["target_date"].min().date().isoformat(),
           "last": calls["target_date"].max().date().isoformat(),
           "since": calls["made_on"].min().date().isoformat(), "series": int(calls["series_id"].nunique()),
           "days": int(calls["target_date"].nunique())}
    out["total"]["p_coin"] = _p_better_than_coin(out["total"]["right"], out["total"]["n"])
    end = calls["target_date"].max()
    out["week"] = _score(calls[calls["target_date"] > end - pd.Timedelta(days=7)])
    areas = []
    for key, label in AREAS:
        mine = calls[calls["domain"] == key]
        if mine.empty:
            continue
        sc = _score(mine)
        ups = float(mine["went_up"].mean())
        hind = max(ups, 1 - ups)  # always calling the direction that turned out more common
        areas.append({"key": key, "label": label, **sc, "hindsight": round(hind, 4),
                      "hindsight_call": "up" if ups >= 0.5 else "down",
                      "p_coin": _p_better_than_coin(sc["right"], sc["n"])})
    out["areas"] = areas
    out["bands"] = []
    for floor, key, label in BANDS:
        mine = calls[calls["band"] == key]
        if not mine.empty:
            out["bands"].append({"key": key, "label": label, "floor": floor, **_score(mine),
                                 "said": round(float(mine["chance"].mean()), 4),
                                 "areas": {a: _score(mine[mine["domain"] == a]) for a, _ in AREAS if (mine["domain"] == a).any()}})
    streak, last = 0, None
    for _, day in calls.groupby("target_date"):
        if len(day) < 5:  # a day only a handful of calls have reached yet says little
            continue
        good = day["right"].mean() >= 0.5
        streak = streak + 1 if good == last else 1
        last = good
    out["streak"] = {"days": streak, "good": bool(last)}
    return out


# "Calls it stands behind": only the calls sure enough to have been right TARGET of the time on
# earlier days. The bar is learned from settled calls only and then tested on later ones it never saw.
TARGET = 0.80
GRID = (0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9)
MIN_LEARN = 30
FOUND = "2026-11-18"  # the day the rule was set: calls for later days are its live test


def learn_bar(calls: pd.DataFrame) -> float | None:
    """The lowest sureness at which settled calls were right TARGET of the time or more."""
    for th in GRID:
        mine = calls[calls["chance"] >= th]
        if len(mine) >= MIN_LEARN and mine["right"].mean() >= TARGET:
            return th
    return None


def confident(calls: pd.DataFrame, found: str = FOUND) -> dict | None:
    """Learn the bar on the first half of the settled days, test it on the second half; then the
    bar learned on every settled day, and its live record on days after ``found``."""
    if calls is None or calls.empty:
        return None
    days_ = sorted(calls["target_date"].unique())
    split = days_[len(days_) // 2]
    early, late = calls[calls["target_date"] < split], calls[calls["target_date"] >= split]
    out = {"target": TARGET, "split": pd.Timestamp(split).date().isoformat(), "found": found}
    bar = learn_bar(early)
    if bar is not None and len(late):
        kept = late[late["chance"] >= bar]
        out["test"] = {"bar": bar, "learned": _score(early[early["chance"] >= bar]), **_score(kept),
                       "coverage": round(len(kept) / len(late), 4), "all_late": _score(late),
                       "areas": [{"key": k, "label": l, **_score(kept[kept["domain"] == k]),
                                  "of": int((late["domain"] == k).sum())} for k, l in AREAS if (late["domain"] == k).any()]}
    live_bar = learn_bar(calls[calls["target_date"] <= pd.Timestamp(found)])
    out["bar"] = live_bar
    if live_bar is not None:
        after = calls[(calls["target_date"] > pd.Timestamp(found)) & (calls["chance"] >= live_bar)]
        out["live"] = _score(after)
    return out


# Range calls: "the S&P 500 will be between X and Y". The model's own 80% range is widened (or
# narrowed) by a factor k learned, for every call, only from calls that had already settled before it
# was made: the k that would have held RANGE_AIM of them, from the same area once it has RANGE_MIN
# settled calls, otherwise from every area. Each range is therefore checked on a day it never saw.
RANGE_AIM = 0.90  # aim above 80% on past days, because the model's ranges have kept getting too narrow.
# Chosen after looking at Oct-Nov 2026 (aiming at 80% held 71%, 85% held 77%, 90% held 83%), so the
# clean test of the rule is its live record on days after RANGE_FOUND.
RANGE_MIN = 40
RANGE_FOUND = "2026-11-18"  # the day the rule was set: ranges for later days are its live test


def range_rows(scored: pd.DataFrame | None, freqs: dict[str, str] | None = None, model: str = MODEL) -> pd.DataFrame:
    """The newest sealed range going into each day of each daily or market-day series, with the
    widening ``need`` that would just have covered what happened (1 = the model's own 80% range)."""
    cols = ["series_id", "domain", "made_on", "target_date", "last_value", "actual", "q10", "q50", "q90", "need"]
    if scored is None or scored.empty or not {"q10", "q50", "q90", "made_on", "target_date", "actual", "model"} <= set(scored.columns):
        return pd.DataFrame(columns=cols)
    s = scored[(scored["model"] == model) & scored["actual"].notna() & scored["q10"].notna()
               & scored["q50"].notna() & scored["q90"].notna()].copy()
    if freqs is not None:
        s = s[s["series_id"].isin([k for k, f in freqs.items() if f in WEEK])]
    for c in ("made_on", "target_date"):
        s[c] = pd.to_datetime(s[c], errors="coerce", format="mixed")
    s = s.dropna(subset=["made_on", "target_date"])
    s = s[s["made_on"] < s["target_date"]]
    if s.empty:
        return pd.DataFrame(columns=cols)
    s = s.sort_values(["made_on", "step"]).groupby(["series_id", "target_date"]).tail(1)
    lo_w = (s["q50"] - s["q10"]).clip(lower=1e-12)
    hi_w = (s["q90"] - s["q50"]).clip(lower=1e-12)
    s["need"] = np.maximum((s["q50"] - s["actual"]) / lo_w, (s["actual"] - s["q50"]) / hi_w).clip(lower=0)
    return s.sort_values(["target_date", "domain", "series_id"])[cols].reset_index(drop=True)


def widen(settled: pd.DataFrame, domain: str, aim: float | None = None) -> float | None:
    """The widening that would have held ``aim`` of the settled ranges in this area (or in every
    area while this one has fewer than RANGE_MIN); None until there are enough to learn from."""
    mine = settled[settled["domain"] == domain]
    use = mine if len(mine) >= RANGE_MIN else settled
    return float(np.quantile(use["need"], RANGE_AIM if aim is None else aim)) if len(use) >= RANGE_MIN else None


def bounds(series_id: str, q10: float, q50: float, q90: float, k: float) -> tuple[float, float]:
    lo, hi = q50 - k * (q50 - q10), q50 + k * (q90 - q50)
    if NAMES.get(series_id, ("", "price"))[1] != "temp" and q10 >= 0:
        lo = max(lo, 0.0)  # prices, counts and rain do not go below zero
    return lo, hi


def ranges(rows: pd.DataFrame) -> pd.DataFrame:
    """Every settled range with the k it would have used on the day it was made, and whether the
    day landed inside. Calls made before there was enough to learn from are left out."""
    if rows is None or rows.empty:
        return pd.DataFrame(columns=[*(rows.columns if rows is not None else []), "k", "lo", "hi", "inside", "raw_inside"])
    ks = {}
    for (made, dom) in rows[["made_on", "domain"]].drop_duplicates().itertuples(index=False):
        ks[(made, dom)] = widen(rows[rows["target_date"] < made], dom)
    out = rows.copy()
    out["k"] = [ks[(m, d)] for m, d in zip(out["made_on"], out["domain"])]
    out = out[out["k"].notna()].copy()
    if out.empty:
        return out.assign(lo=[], hi=[], inside=[], raw_inside=[])
    b = [bounds(r.series_id, r.q10, r.q50, r.q90, r.k) for r in out.itertuples()]
    out["lo"] = [x[0] for x in b]
    out["hi"] = [x[1] for x in b]
    out["inside"] = (out["actual"] >= out["lo"]) & (out["actual"] <= out["hi"])
    out["raw_inside"] = (out["actual"] >= out["q10"]) & (out["actual"] <= out["q90"])
    return out.reset_index(drop=True)


def _inside(rows: pd.DataFrame) -> dict:
    n = int(len(rows)); i = int(rows["inside"].sum()) if n else 0
    return {"n": n, "inside": i, "outside": n - i, "share": round(i / n, 4) if n else None,
            "raw": round(float(rows["raw_inside"].mean()), 4) if n else None}


def range_record(r: pd.DataFrame, found: str = RANGE_FOUND) -> dict | None:
    """How often the day landed inside the range: overall, by area, by series, and live since ``found``."""
    if r is None or r.empty:
        return None
    width = ((r["hi"] - r["lo"]) / r["last_value"].abs().replace(0, np.nan)).median()
    out = {"aim": RANGE_AIM, "level": 0.8, "found": found, "total": _inside(r),
           "since": r["target_date"].min().date().isoformat(), "days": int(r["target_date"].nunique()),
           "k": round(float(r.sort_values("made_on")["k"].iloc[-1]), 3), "width": round(float(width), 4) if pd.notna(width) else None,
           "areas": [{"key": k, "label": l, **_inside(r[r["domain"] == k]),
                      "width": round(float(((g["hi"] - g["lo"]) / g["last_value"].abs().replace(0, np.nan)).median()), 4)}
                     for k, l in AREAS if len(g := r[r["domain"] == k])],
           "series": {sid: [int(g["inside"].sum()), int(len(g))] for sid, g in r.groupby("series_id")}}
    out["live"] = _inside(r[r["target_date"] > pd.Timestamp(found)])
    return out


def lines(scored: pd.DataFrame | None, show=("timesfm-2.5", "radiant", "seldon")) -> dict:
    """For every series, what really happened on each settled day and what each forecaster's newest
    sealed call said it would be (its median), for the actual-against-forecasters charts."""
    out: dict = {}
    for m in show:
        c = standing(scored, m)
        for sid, g in c.groupby("series_id"):
            item = out.setdefault(sid, {"actual": {}, "m": {}})
            for d, a in zip(g["target_date"], g["actual"]):
                item["actual"][d.date().isoformat()] = float(f"{a:.5g}")
            item["m"][m] = [[d.date().isoformat(), float(f"{q:.5g}")] for d, q in zip(g["target_date"], g["q50"]) if pd.notna(q)]
    for item in out.values():
        item["actual"] = sorted(item["actual"].items())
    return out


def models(scored: pd.DataFrame | None) -> list[dict]:
    """The same tally for every model in the ledger, on the days each one covered."""
    if scored is None or scored.empty:
        return []
    out = []
    for m in sorted(scored["model"].dropna().unique()):
        c = standing(scored, m)
        if len(c):
            out.append({"model": m, **_score(c)})
    return sorted(out, key=lambda r: -(r["share"] or 0))


def days(calls: pd.DataFrame, titles: dict[str, str] | None = None, rng: pd.DataFrame | None = None) -> list[dict]:
    """Every day's calls with what happened, newest day first; with the range call for the same day
    (low, high, landed inside) where there is one."""
    look = {} if rng is None or rng.empty else {(a, b): [float(f"{lo:.4g}"), float(f"{hi:.4g}"), bool(i)]
                                                for a, b, lo, hi, i in zip(rng["series_id"], rng["target_date"], rng["lo"], rng["hi"], rng["inside"])}
    out = []
    for d, day in calls.groupby("target_date"):
        rows = [[r.series_id, r.domain, sentence(r.series_id, bool(r.up)), round(float(r.chance), 3), bool(r.right),
                 round(float(r.change), 4) if pd.notna(r.change) else None, r.made_on.date().isoformat(), r.last_date.date().isoformat(),
                 outcome_words(r.series_id, bool(r.went_up)), NAMES.get(r.series_id, ("", "price"))[1],
                 round(float(r.delta), 3), look.get((r.series_id, r.target_date))] for r in day.itertuples()]
        rows.sort(key=lambda x: (-x[3]))
        out.append({"date": d.date().isoformat(), **_score(day), "calls": rows})
    return out[::-1]


def now(ledger: pd.DataFrame | None, calls: pd.DataFrame, freqs: dict[str, str], model: str = MODEL,
        settled: pd.DataFrame | None = None, rng: pd.DataFrame | None = None) -> list[dict]:
    """The newest call for about a week ahead for every series, with its record so far, and the range
    it gives for the same day widened by what every settled range so far has needed."""
    if ledger is None or ledger.empty or "p_up" not in ledger:
        return []
    led = ledger[(ledger["model"] == model) & ledger["p_up"].notna()].copy()
    led["made_on"] = pd.to_datetime(led["made_on"], errors="coerce", format="mixed")
    led = led.dropna(subset=["made_on"])
    out = []
    for sid, g in led.groupby("series_id"):
        freq = freqs.get(sid, "D")
        if freq not in WEEK:
            continue
        newest = g[g["made_on"] == g["made_on"].max()]
        row = newest[newest["step"] == (1 if is_rain(sid) else WEEK[freq])]  # rain: tomorrow; a week out it is the season talking
        if row.empty:
            continue
        r = row.iloc[0]
        p = chance_up(sid, r); up = p >= 0.5; chance = p if up else 1 - p
        mine = calls[calls["series_id"] == sid] if calls is not None and len(calls) else pd.DataFrame()
        lo = hi = None
        k = widen(settled, r["domain"]) if settled is not None and len(settled) else None
        if k is not None and pd.notna(r.get("q10")) and pd.notna(r.get("q90")) and pd.notna(r.get("q50")):
            lo, hi = (float(f"{v:.4g}") for v in bounds(sid, r["q10"], r["q50"], r["q90"], k))
        mr = rng[rng["series_id"] == sid] if rng is not None and len(rng) else pd.DataFrame()
        out.append({"id": sid, "domain": r["domain"], "name": name(sid), "call": sentence(sid, up), "up": up,
                    "kind": NAMES.get(sid, ("", "price"))[1], "lo": lo, "hi": hi,
                    "range_record": [int(mr["inside"].sum()), int(len(mr))] if len(mr) else None,
                    "chance": round(chance, 3), "band": band(chance)[0], "made_on": r["made_on"].date().isoformat(),
                    "target": str(r["target_date"])[:10], "from": str(r["last_date"])[:10],
                    "record": _score(mine) if len(mine) else None})
    out.sort(key=lambda x: -x["chance"])
    return out


def payload(scored: pd.DataFrame | None, ledger: pd.DataFrame | None, freqs: dict[str, str]) -> dict | None:
    calls = standing(scored)
    rec = record(calls)
    if rec is None and (ledger is None or ledger.empty):
        return None
    settled = range_rows(scored, freqs)
    rng = ranges(settled)
    return {"model": MODEL, "record": rec, "models": models(scored), "days": days(calls, rng=rng) if len(calls) else [],
            "confident": confident(calls), "lines": lines(scored), "ranges": range_record(rng),
            "now": now(ledger, calls, freqs, settled=settled, rng=rng), "bands": [[f, k, l] for f, k, l in BANDS]}


def describe(p: dict | None) -> str:
    if not p or not p.get("record"):
        return "No sealed call has come due yet."
    r = p["record"]; t = r["total"]
    lines = [f"Track record since {r['since']}: {t['right']} right, {t['wrong']} wrong ({t['share']:.0%}) on {t['n']} calls "
             f"across {r['series']} series and {r['days']} days. Last 7 days: {r['week']['right']}-{r['week']['wrong']}.", ""]
    lines.append("By area (coin flip 50%; 'hindsight' = always calling the direction that turned out more common):")
    for a in r["areas"]:
        lines.append(f"  {a['label']:<11} {a['right']:>4}-{a['wrong']:<4} {a['share']:>5.0%}   hindsight {a['hindsight']:.0%} (always {a['hindsight_call']})")
    lines += ["", "How sure it was against how often it was right:"]
    for b in r["bands"]:
        lines.append(f"  {b['label']:<12} said {b['said']:.0%} on average, right {b['share']:.0%} ({b['right']} of {b['n']})")
    g = p.get("ranges")
    if g:
        t = g["total"]
        lines += ["", f"Range calls ('between X and Y', aimed at 80%): the day landed inside {t['inside']} of {t['n']} ({t['share']:.0%}); "
                  f"the model's own 80% ranges held {t['raw']:.0%}. Each widening was learned only from ranges already settled."]
        for a in g["areas"]:
            wide = f", median width {a['width']:.1%} of the level" if a["key"] != "weather" else ""
            lines.append(f"  {a['label']:<11} inside {a['inside']:>4} of {a['n']:<4} {a['share']:>5.0%}   (own range {a['raw']:.0%}{wide})")
    if p.get("now"):
        lines += ["", "What it says now (about a week ahead):"]
        for c in p["now"][:15]:
            rec = c["record"]
            lines.append(f"  {c['call']:<55} {c['chance']:.0%}" + (f"   record {rec['right']}-{rec['wrong']}" if rec else ""))
    return "\n".join(lines)
