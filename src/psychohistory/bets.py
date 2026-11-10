"""Betting odds: what people who put money on it think will happen in the world.

The project's own event odds are about attention (will coverage of a topic spike?). Prediction
markets answer a different and very human question: will this thing actually happen? Once a day
(``psychohistory bets``, run by the forecast workflow) the most-traded open yes/no questions on
Polymarket are read from its public Gamma API (no key needed) and their "yes" prices, which are the
crowd's chance, are sealed in ``predictions/bet_ledger.csv`` with a SHA-256 fingerprint per day
(``bet_seals.csv``), exactly like the project's own forecasts.

When a question resolves, every sealed price for it is opened and scored with the Brier score
(``bet_scored.csv``). Two calls per question are reported, so a question watched for months does
not count more than one watched for a week:

* first seen: the crowd's chance the first day it was sealed (its longest-range call);
* a week out: the last price sealed at least seven days before the question was settled.

The idea of reading Polymarket's open, forward-looking markets ranked by volume comes from
TradingAgents (Xiao et al., 2024; Apache-2.0), whose Polymarket vendor does the same for its
trading agents. This module is our own code. Prices are a crowd's view, not this project's
forecast: no model here reads them.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import ledger

API = "https://gamma-api.polymarket.com"
SITE = "https://polymarket.com"
BET_LEDGER = Path("predictions/bet_ledger.csv")
BET_SCORED = Path("predictions/bet_scored.csv")
BET_SEALS = Path("predictions/bet_seals.csv")
COLUMNS = ["made_on", "model", "market_id", "question", "area", "url", "end_date", "p_yes", "volume", "week_change"]
SCORED = COLUMNS + ["settled_on", "outcome", "brier"]
MODEL = "polymarket"
TOP = 40              # questions sealed per day
MIN_VOLUME = 50_000   # dollars traded: thinner markets are one trader's opinion
MIN_DAYS = 3          # questions settling sooner are mostly sports games and minute-by-minute prices
MAX_DAYS = 400
WEEK = 7
SETTLED = 0.98        # a closed market's winning side trades at about 1; anything less is not settled
BUDGET = 240.0        # seconds for checking which sealed questions have resolved
BUCKETS = (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0001)

# Sports games and short price bets fill the volume ranking but say little about the world.
SKIP = re.compile(r"\b(vs\.?|v\.|o/u|over/under|spread|moneyline|handicap|up or down|nba|nfl|nhl|mlb|ufc|premier league|"
                  r"champions league|la liga|serie a|bundesliga|grand prix|super bowl|world series|stanley cup|"
                  r"tweets?|mentions?|say \")\b", re.I)
# Which part of the project a question belongs to, so the app can file it beside the right topics.
AREAS = (
    ("politics", r"elect|president|prime minister|senate|congress|house of rep|parliament|governor|mayor|"
                 r"vote|referendum|party|nominee|cabinet|impeach|supreme court|minister|chancellor|coalition|poll"),
    ("markets", r"fed\b|federal reserve|interest rate|rates? cut|recession|inflation|cpi|gdp|s&p|nasdaq|dow|"
                r"stock|bitcoin|btc|ethereum|eth\b|gold|silver|oil|crude|tariff|treasur|yield|unemployment|ipo"),
    ("tech", r"\bai\b|openai|gpt|gemini|anthropic|claude|model|spacex|starship|tesla|robotaxi|nvidia|apple|"
             r"google|microsoft|meta\b|quantum|fusion|chip|launch|rocket|crypto"),
    ("weather", r"hurricane|storm|temperature|heat|snow|rain|earthquake|wildfire|flood|climate|tornado"),
)

log = logging.getLogger(__name__)


def _json_list(value) -> list:
    """Gamma sends ``outcomes`` and ``outcomePrices`` as JSON text inside the JSON ("[\\"Yes\\", \\"No\\"]")."""
    if isinstance(value, list):
        return value
    try:
        out = json.loads(value or "[]")
        return out if isinstance(out, list) else []
    except (TypeError, ValueError):
        return []


def _float(value, default=np.nan) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _end(market: dict) -> date | None:
    text = str(market.get("endDate") or market.get("endDateIso") or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def area_of(question: str) -> str:
    for area, pattern in AREAS:
        if re.search(pattern, question, re.I):
            return area
    return "news"


def url_of(market: dict) -> str:
    """The market's page: its event's page when Gamma names one (that is what polymarket.com links to)."""
    events = market.get("events") or []
    slug = (events[0] or {}).get("slug") if events and isinstance(events[0], dict) else None
    if slug:
        return f"{SITE}/event/{slug}"
    return f"{SITE}/market/{market['slug']}" if market.get("slug") else SITE


def yes_price(market: dict) -> float | None:
    """The price of "Yes" in a two-outcome yes/no market (the crowd's chance), else None."""
    outcomes = [str(o).strip().lower() for o in _json_list(market.get("outcomes"))]
    prices = [_float(p) for p in _json_list(market.get("outcomePrices"))]
    if outcomes != ["yes", "no"] or len(prices) != 2 or not all(np.isfinite(prices)):
        return None
    p = prices[0]
    return p if 0.0 <= p <= 1.0 else None


def pick(markets: list[dict], today: date, top: int = TOP) -> list[dict]:
    """The questions worth sealing today: open yes/no markets settling in 3 to 400 days, with real
    money behind them, sports and short price bets left out, most traded first, one per question."""
    out, seen = [], set()
    for m in markets:
        question = " ".join(str(m.get("question") or "").split())
        end, p, volume = _end(m), yes_price(m), _float(m.get("volumeNum", m.get("volume")), 0.0)
        if not question or m.get("closed") or m.get("active") is False or p is None or end is None:
            continue
        if not MIN_DAYS <= (end - today).days <= MAX_DAYS or volume < MIN_VOLUME or SKIP.search(question):
            continue
        key = question.lower()
        if key in seen or not m.get("id"):
            continue
        seen.add(key)
        out.append({"market_id": str(m["id"]), "question": question, "area": area_of(question), "url": url_of(m),
                    "end_date": end.isoformat(), "p_yes": round(p, 4), "volume": round(volume),
                    "week_change": round(_float(m.get("oneWeekPriceChange"), 0.0), 4)})
    out.sort(key=lambda r: -r["volume"])
    return out[:top]


def fetch_open(get=None, pages: int = 3, limit: int = 100) -> list[dict]:
    """The most-traded open markets from Gamma (a few pages of the volume ranking)."""
    get = get or _get
    out = []
    for page in range(pages):
        batch = get("/markets", {"active": "true", "closed": "false", "order": "volumeNum", "ascending": "false",
                                 "limit": limit, "offset": page * limit})
        if not isinstance(batch, list) or not batch:
            break
        out += batch
    return out


def _get(path: str, params: dict | None = None):
    from .data.http import get as http_get
    return http_get(API + path, params=params, retries=3, timeout=30.0).json()


def batch(markets: list[dict], made_on: str) -> pd.DataFrame:
    rows = [{"made_on": made_on, "model": MODEL, **m} for m in markets]
    return pd.DataFrame(rows, columns=COLUMNS)


def read(path: Path) -> pd.DataFrame | None:
    if not path.exists() or path.stat().st_size <= 1:
        return None
    return pd.read_csv(path, dtype={"market_id": str, "made_on": str, "end_date": str})


def append(rows: pd.DataFrame, path: Path = BET_LEDGER) -> pd.DataFrame:
    """Add a day's prices (a same-day re-run replaces that day's rows); older days are never touched."""
    old = read(path)
    if old is not None:
        rows = pd.concat([old[old["made_on"] != rows["made_on"].iloc[0]] if len(rows) else old, rows], ignore_index=True)
    rows = rows.sort_values(["made_on", "market_id"]).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False)
    return rows


def seal(entries: pd.DataFrame, path: Path = BET_SEALS, today: str | None = None) -> pd.DataFrame:
    return ledger.write_seals(entries, path, today=today, columns=COLUMNS, order=("market_id",))


def verify(entries: pd.DataFrame | None, path: Path = BET_SEALS) -> pd.DataFrame | None:
    if entries is None:
        return None
    return ledger.verify(entries, path, columns=COLUMNS, order=("market_id",))


def outcome_of(market: dict) -> float | None:
    """1 if a closed market settled "Yes", 0 if "No", None while it is open, disputed or void."""
    if not market.get("closed"):
        return None
    p = yes_price(market)
    if p is None:
        return None
    if p >= SETTLED:
        return 1.0
    if p <= 1 - SETTLED:
        return 0.0
    return None


def settle(entries: pd.DataFrame | None, scored: pd.DataFrame | None, today: date, get=None,
           budget: float = BUDGET, clock=time.monotonic) -> pd.DataFrame:
    """Score every sealed price of each question that has settled. Only questions past their end
    date and not yet scored are asked about, oldest first, within ``budget`` seconds."""
    get = get or _get
    done = scored if scored is not None else pd.DataFrame(columns=SCORED)
    if entries is None or entries.empty:
        return done
    known = set(done["market_id"].astype(str))
    due = (entries[(entries["end_date"] <= today.isoformat()) & ~entries["market_id"].astype(str).isin(known)]
           .sort_values("end_date")["market_id"].astype(str).unique())
    start, fresh = clock(), []
    for market_id in due:
        if clock() - start > budget:
            break
        try:
            market = get(f"/markets/{market_id}")
        except Exception as exc:  # one missing market must not stop the scoring
            log.warning("bets: could not check market %s: %s", market_id, exc)
            continue
        outcome = outcome_of(market if isinstance(market, dict) else {})
        if outcome is None:
            continue
        settled_on = str(market.get("closedTime") or market.get("endDate") or today.isoformat())[:10]
        mine = entries[entries["market_id"].astype(str) == market_id]
        fresh.append(mine.assign(settled_on=settled_on, outcome=outcome, brier=(mine["p_yes"] - outcome) ** 2))
    if fresh:
        done = pd.concat([done, *fresh], ignore_index=True) if len(done) else pd.concat(fresh, ignore_index=True)
    return done[SCORED].sort_values(["settled_on", "market_id", "made_on"]).reset_index(drop=True)


def calls(scored: pd.DataFrame | None) -> pd.DataFrame:
    """One "first seen" and one "a week out" call per settled question (see the module notes)."""
    if scored is None or scored.empty:
        return pd.DataFrame(columns=["call", *SCORED])
    s = scored.sort_values("made_on")
    first = s.groupby("market_id", as_index=False).head(1).assign(call="first seen")
    gap = (pd.to_datetime(s["settled_on"]) - pd.to_datetime(s["made_on"])).dt.days
    week = s[gap >= WEEK].groupby("market_id", as_index=False).tail(1).assign(call="a week out")
    return pd.concat([first, week], ignore_index=True)


def record(scored: pd.DataFrame | None) -> dict:
    """The crowd's sealed record: Brier per call against a coin flip (0.25) and against always
    saying the base rate, plus a calibration table (said about X%, happened Y% of the time)."""
    table = calls(scored)
    out = {"settled": int(table["market_id"].nunique()) if len(table) else 0, "calls": [], "calibration": []}
    for call, g in table.groupby("call", sort=False):
        base = float(g["outcome"].mean())
        climate = float(((base - g["outcome"]) ** 2).mean())
        brier = float(g["brier"].mean())
        right = float(((g["p_yes"] > 0.5) == (g["outcome"] > 0.5)).mean())
        out["calls"].append({"call": call, "questions": int(len(g)), "brier": round(brier, 4),
                             "skill_vs_coin": round(1 - brier / 0.25, 3),
                             "skill_vs_base": round(1 - brier / climate, 3) if climate > 0 else None,
                             "favourite_won": round(right, 3), "happened": round(base, 3)})
    week = table[table["call"] == "a week out"]
    if len(week):
        bins = pd.cut(week["p_yes"], BUCKETS, right=False, labels=False)
        for b, g in week.groupby(bins):
            lo, hi = BUCKETS[int(b)], min(BUCKETS[int(b) + 1], 1.0)
            out["calibration"].append({"from": lo, "to": round(hi, 2), "questions": int(len(g)),
                                       "said": round(float(g["p_yes"].mean()), 3), "happened": round(float(g["outcome"].mean()), 3)})
    return out


def payload(entries: pd.DataFrame | None, scored: pd.DataFrame | None, seals: pd.DataFrame | None = None,
            top: int = 24) -> dict | None:
    """For the app: the newest sealed day's questions (with how the price moved since the first
    sealed day), the record so far and the seal check."""
    if entries is None or entries.empty:
        return None
    day = str(entries["made_on"].max())
    now = entries[entries["made_on"] == day].sort_values("volume", ascending=False).head(top)
    first = entries.sort_values("made_on").groupby("market_id").head(1).set_index("market_id")
    items = []
    for r in now.itertuples(index=False):
        f = first.loc[r.market_id] if r.market_id in first.index else None
        items.append({"id": str(r.market_id), "q": r.question, "area": r.area, "url": r.url, "end": str(r.end_date),
                      "p": float(r.p_yes), "wk": float(r.week_change) if pd.notna(r.week_change) else 0.0,
                      "vol": int(r.volume), "since": str(f["made_on"]) if f is not None else day,
                      "p0": float(f["p_yes"]) if f is not None else float(r.p_yes)})
    checked = None
    if seals is not None and len(seals):
        checked = {"batches": int(len(seals)), "ok": int((seals["status"] == "ok").sum())}
    return {"made_on": day, "days": int(entries["made_on"].nunique()), "items": items, "record": record(scored),
            "seals": checked, "source": SITE}


def describe(entries: pd.DataFrame | None, scored: pd.DataFrame | None, top: int = 12) -> str:
    """The crowd's newest odds and record, as text for the terminal."""
    data = payload(entries, scored, top=top)
    if data is None:
        return "No betting odds sealed yet; run `psychohistory bets` with a connection."
    lines = [f"Betting odds from Polymarket, sealed {data['made_on']} ({data['days']} days sealed so far)", ""]
    for it in data["items"]:
        move = f" ({it['wk']:+.0%} this week)" if abs(it["wk"]) >= 0.005 else ""
        lines.append(f"  {it['p']:>4.0%}  {it['q']}  [settles {it['end']}]{move}")
    rec = data["record"]
    lines += ["", f"Settled so far: {rec['settled']} question{'' if rec['settled'] == 1 else 's'}."]
    for c in rec["calls"]:
        lines.append(f"  {c['call']}: Brier {c['brier']:.3f} over {c['questions']} questions, "
                     f"{c['skill_vs_coin']:+.0%} against a coin flip, favourite won {c['favourite_won']:.0%}")
    return "\n".join(lines)


def run(ledger_path: Path = BET_LEDGER, scored_path: Path = BET_SCORED, seals_path: Path = BET_SEALS,
        today: date | None = None, get=None) -> dict:
    """Seal today's betting odds and score the questions that have settled. Returns counts."""
    today = today or datetime.now(timezone.utc).date()
    picked = pick(fetch_open(get), today)
    entries = read(ledger_path)
    if picked:
        append(batch(picked, today.isoformat()), ledger_path)
        entries = read(ledger_path)  # seal what the file holds, so `verify` reads the same numbers back
        seal(entries, seals_path, today=today.isoformat())
    scored = settle(entries, read(scored_path), today, get=get)
    if len(scored):
        scored_path.parent.mkdir(parents=True, exist_ok=True)
        scored.to_csv(scored_path, index=False)
    return {"sealed": len(picked), "settled": int(scored["market_id"].nunique()) if len(scored) else 0,
            "days": int(entries["made_on"].nunique()) if entries is not None else 0}


__all__ = ["pick", "fetch_open", "settle", "record", "payload", "describe", "run", "area_of", "yes_price", "outcome_of"]
