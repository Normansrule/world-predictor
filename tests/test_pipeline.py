"""Offline tests: synthetic data, baseline models only (no network, no TimesFM download)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from psychohistory import backtest, catalog, cli, data, ledger
from psychohistory.catalog import SeriesSpec
from psychohistory.metrics import score
from psychohistory.models import QUANTILES, DriftForecaster, Forecast, MeanForecaster, NaiveForecaster


def synthetic(n=400, seed=0, trend=0.05, start="2020-01-01", freq="D"):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    values = 100 + trend * t + 5 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 1, n).cumsum() * 0.3
    return pd.Series(values, index=pd.date_range(start, periods=n, freq=freq))


@pytest.mark.parametrize("model", [NaiveForecaster(), DriftForecaster(), MeanForecaster()])
def test_baselines_return_sorted_deciles(model):
    out = model.forecast([synthetic().to_numpy(), synthetic(50).to_numpy()], horizon=10)
    assert len(out) == 2
    for f in out:
        assert f.point.shape == (10,)
        assert f.quantiles.shape == (10, len(QUANTILES))
        assert np.all(np.diff(f.quantiles, axis=1) >= 0)


def test_perfect_forecast_scores_zero_error():
    train = np.arange(50.0)
    actual = np.arange(50.0, 60.0)
    perfect = Forecast(actual.copy(), np.tile(actual[:, None], (1, 9)))
    m = score(train, actual, perfect)
    assert m["mae"] == 0 and m["mase"] == 0 and m["coverage80"] == 1 and m["direction"] == 1


def test_prob_above_reads_the_deciles():
    from psychohistory.metrics import prob_above

    deciles = np.arange(1.0, 10.0)  # 10% quantile = 1 ... 90% quantile = 9
    assert prob_above(deciles, 5.0) == pytest.approx(0.5)
    assert prob_above(deciles, 3.0) == pytest.approx(0.7)
    assert prob_above(deciles, -100.0) == pytest.approx(0.95)
    assert prob_above(deciles, 100.0) == pytest.approx(0.05)


def test_brier_rewards_confident_correct_calls():
    train = np.arange(50.0)
    actual = np.arange(50.0, 60.0)
    confident = Forecast(actual.copy(), np.tile(actual[:, None], (1, 9)) + np.linspace(-1, 1, 9))
    assert score(train, actual, confident)["brier"] == pytest.approx(0.05**2)


class RecordingModel:
    """Fails the test if any context contains data from on or after its forecast origin."""

    name = "recorder"

    def __init__(self):
        self.contexts = []

    def forecast(self, contexts, horizon):
        self.contexts.extend(contexts)
        return NaiveForecaster().forecast(contexts, horizon)


def test_backtest_never_sees_the_future():
    # Values equal their own index, so the last context value tells us where the context ended.
    series = pd.Series(np.arange(300.0), index=pd.date_range("2021-01-01", periods=300))
    spec = SeriesSpec("x", "news", "gdelt", horizon=20)
    model = RecordingModel()
    results = backtest.backtest_series(spec, series, [model], windows=5)
    assert len(results) == 5
    for context, origin in zip(model.contexts, results["origin"]):
        assert series.index[int(context[-1])].date() == origin


def test_drift_beats_naive_on_a_trend():
    series = pd.Series(np.arange(500.0) * 2 + np.random.default_rng(1).normal(0, 0.5, 500))
    series.index = pd.date_range("2020-01-01", periods=500)
    spec = SeriesSpec("trend", "markets", "yahoo", horizon=10)
    results = backtest.backtest_series(spec, series, [DriftForecaster(), NaiveForecaster()], windows=8)
    summary = backtest.summarize(results)
    assert summary.set_index("model").loc["drift", "skill"] > 0.5


def test_skill_by_step_shows_drift_advantage_growing_with_horizon():
    series = pd.Series(np.arange(500.0) * 2 + np.random.default_rng(2).normal(0, 3, 500))
    series.index = pd.date_range("2020-01-01", periods=500)
    spec = SeriesSpec("trend", "markets", "yahoo", horizon=20)
    steps = []
    backtest.backtest_series(spec, series, [DriftForecaster(), NaiveForecaster()], windows=10, step_rows=steps)
    by_step = backtest.skill_by_step(pd.DataFrame(steps)).set_index(["model", "step"])["skill"]
    assert by_step[("drift", 20)] > by_step[("drift", 1)]
    table = backtest.horizon_table(backtest.skill_by_step(pd.DataFrame(steps)), "drift")
    assert list(table.columns) == ["domain", "1 step", "2-5", "6-10", "11-20"]


def test_calibration_buckets_match_given_odds():
    results = pd.DataFrame(
        {
            "model": "m",
            "domain": "markets",
            "p_up": [0.9, 0.9, 0.9, 0.9, 0.1, 0.1],
            "went_up": [1.0, 1.0, 1.0, 0.0, 0.0, 0.0],
        }
    )
    table = backtest.calibration(results, "m").set_index("odds given")
    assert table.loc["80%-100%", "happened"] == pytest.approx(0.75)
    assert table.loc["0%-20%", "happened"] == pytest.approx(0.0)
    assert table.loc["80%-100%", "forecasts"] == 4


def test_load_model_is_cached():
    from psychohistory.models import load_model

    assert load_model("naive") is load_model("naive")


def test_composite_scales_members_to_their_mean():
    a = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2024-01-01", periods=3))
    b = pd.Series([100.0, 200.0, 300.0, 400.0], index=pd.date_range("2024-01-01", periods=4))
    combined = data.composite([a, b])
    assert len(combined) == 3
    np.testing.assert_allclose(combined.to_numpy(), [0.5, 1.0, 1.5])


def test_ledger_predict_then_score():
    series = synthetic(200)
    spec = SeriesSpec("demo", "tech", "wikipedia", freq="D", horizon=5)
    history = series.iloc[:-5]
    rows = ledger.predict([spec], {"demo": history}, NaiveForecaster(), made_on=date(2024, 1, 1))
    assert list(rows["target_date"]) == [d.date().isoformat() for d in series.index[-5:]]
    scored = ledger.score(rows, {"demo": series})
    assert len(scored) == 5
    assert scored["in_band80"].dtype == bool
    table = ledger.ledger_summary(scored)
    assert table.loc[0, "predictions"] == 5


def test_latest_picks_newest_run_and_final_step():
    spec = SeriesSpec("demo", "tech", "wikipedia", freq="D", horizon=3)
    old = ledger.predict([spec], {"demo": synthetic(100)}, NaiveForecaster(), made_on=date(2024, 1, 1))
    new = ledger.predict([spec], {"demo": synthetic(120)}, NaiveForecaster(), made_on=date(2024, 2, 1))
    latest = ledger.latest(pd.concat([old, new]))
    assert len(latest) == 1
    assert latest.loc[0, "target_date"] == new["target_date"].iloc[-1]
    assert latest.loc[0, "median_change"] == pytest.approx(0.0)
    assert 0.0 <= latest.loc[0, "p_up"] <= 1.0


def test_catalog_ids_are_unique_and_composites_resolve():
    ids = [s.id for s in catalog.CATALOG]
    assert len(ids) == len(set(ids))
    for spec in catalog.CATALOG:
        assert spec.domain in catalog.DOMAINS
        if spec.source == "composite":
            for member in spec.params["members"]:
                assert catalog.CATALOG.index(catalog.by_id(member)) < catalog.CATALOG.index(spec)


def test_cli_end_to_end_from_cache(tmp_path):
    specs = [catalog.by_id("sp500"), catalog.by_id("aapl"), catalog.by_id("wiki_llm"), catalog.by_id("news_war")]
    for i, spec in enumerate(specs):
        path = data.cache_path(spec, tmp_path / "data")
        path.parent.mkdir(parents=True, exist_ok=True)
        synthetic(600, seed=i, freq=spec.freq).to_frame("value").to_csv(path, index_label="date")
    common = ["--data-dir", str(tmp_path / "data"), "--out-dir", str(tmp_path / "results"),
              "--ledger", str(tmp_path / "ledger.csv"), "--scored", str(tmp_path / "scored.csv"),
              "--model", "drift"]
    series_args = sum((["--series", s.id] for s in specs), [])
    cli.main(["backtest", *common, *series_args, "--windows", "4"])
    cli.main(["predict", *common, *series_args])
    cli.main(["score", *common])
    cli.main(["report", *common])
    report = (tmp_path / "results" / "REPORT.md").read_text()
    assert "Seldon" in report and "sp500" in report
    assert "## 8. What the model expects next" in report and "plots/sp500.png" in report
    assert (tmp_path / "results" / "plots" / "skill_by_domain.png").exists()
    assert (tmp_path / "results" / "plots" / "sp500.png").exists()
    assert (tmp_path / "results" / "plots" / "outlook.png").stat().st_size > 1000
    assert "plots/outlook.png" in report
    assert (tmp_path / "results" / "plots" / "skill_by_step.png").exists()
    assert "## 5. How far ahead can it see?" in report and "11-20" in report
    assert "## 6. Are its odds honest?" in report and "happened" in report
    assert "## In plain English" in report and "plots/replay.gif" in report
    assert (tmp_path / "results" / "plots" / "replay.gif").stat().st_size > 1000
    board = (tmp_path / "results" / "dashboard.html").read_text()
    assert "In plain English" in board and "Replay:" in board
    assert "SCOREBOARD" in board and "Why crowds are predictable" in board
    for theme in ("light", "dark"):
        svg = (tmp_path / "results" / "plots" / f"scorecard-{theme}.svg").read_text()
        assert "Updated" in svg and "%" in svg
    assert "plotly" in board and "What the model expects next" in board and "S&P 500 index" in board
    sealed = pd.read_csv(tmp_path / "ledger.csv")
    assert set(sealed["model"]) == {"drift", "seldon", "seldon-laws", "radiant", "radiant-core"}  # both Seldons and both Radiants are sealed beside the model
    assert (sealed["model"] == "drift").sum() == sum(s.horizon for s in specs)


def test_timesfm25_wrapper_maps_deciles(monkeypatch):
    """TimesFM 2.5 returns (n, h, 10) with the mean first; the wrapper must keep deciles 0.1..0.9."""
    import sys
    import types

    from psychohistory.models import TimesFM25Forecaster

    class FakeModel:
        @classmethod
        def from_pretrained(cls, checkpoint):
            return cls()

        def compile(self, config):
            self.config = config

        def forecast(self, horizon, inputs):
            n = len(inputs)
            point = np.zeros((n, horizon))
            quantiles = np.broadcast_to(np.arange(10.0), (n, horizon, 10)).copy()
            return point, quantiles

    fake = types.SimpleNamespace(TimesFM_2p5_200M_torch=FakeModel, ForecastConfig=lambda **kw: kw)
    monkeypatch.setitem(sys.modules, "timesfm", fake)
    out = TimesFM25Forecaster().forecast([np.arange(20.0)], horizon=3)
    assert out[0].quantiles.shape == (3, 9)
    np.testing.assert_array_equal(out[0].q(0.1), [1, 1, 1])
    np.testing.assert_array_equal(out[0].q(0.9), [9, 9, 9])


def test_auto_ets_deciles_are_ordered_and_centered():
    pytest.importorskip("statsforecast")
    from psychohistory.models import StatsForecastForecaster

    out = StatsForecastForecaster("ets").forecast([synthetic(200).to_numpy(), synthetic(120, seed=3).to_numpy()], 7)
    assert len(out) == 2
    for f in out:
        assert f.quantiles.shape == (7, 9)
        assert np.all(np.diff(f.quantiles, axis=1) >= 0)
        np.testing.assert_allclose(f.q(0.5), f.point)


@pytest.mark.parametrize("style", ["bolt", "chronos2"])
def test_chronos_wrapper_handles_both_output_shapes(monkeypatch, style):
    import sys
    import types

    from psychohistory.models import ChronosForecaster

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, checkpoint, device_map):
            return cls()

        def predict_quantiles(self, inputs, prediction_length, quantile_levels):
            n, q = len(inputs), np.arange(1.0, 10.0)
            if style == "bolt":
                return np.broadcast_to(q, (n, prediction_length, 9)).copy(), np.full((n, prediction_length), 5.0)
            return [np.broadcast_to(q, (1, prediction_length, 9)).copy() for _ in inputs], [np.full((1, prediction_length), 5.0) for _ in inputs]

    fake_torch = types.SimpleNamespace(tensor=lambda x, dtype=None: np.asarray(x), float32=None)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "chronos", types.SimpleNamespace(BaseChronosPipeline=FakePipeline))
    out = ChronosForecaster().forecast([np.arange(30.0), np.arange(40.0)], horizon=4)
    assert len(out) == 2
    assert out[0].quantiles.shape == (4, 9) and out[0].point.shape == (4,)
    np.testing.assert_array_equal(out[1].q(0.9), [9, 9, 9, 9])


def test_compare_adds_rivals_to_backtest_and_ledger(tmp_path):
    spec = catalog.by_id("gold")
    path = data.cache_path(spec, tmp_path / "data")
    path.parent.mkdir(parents=True, exist_ok=True)
    synthetic(400, freq="B").to_frame("value").to_csv(path, index_label="date")
    common = ["--data-dir", str(tmp_path / "data"), "--out-dir", str(tmp_path / "results"),
              "--ledger", str(tmp_path / "ledger.csv"), "--scored", str(tmp_path / "scored.csv"),
              "--series", "gold", "--model", "drift", "--compare", "mean"]
    cli.main(["backtest", *common, "--windows", "3"])
    cli.main(["predict", *common])
    assert {"drift", "mean", "naive"} <= set(pd.read_csv(tmp_path / "results" / "backtest_windows.csv")["model"])
    assert set(pd.read_csv(tmp_path / "ledger.csv")["model"]) == {"drift", "mean", "seldon", "seldon-laws", "radiant", "radiant-core"}


def test_bass_recovers_an_s_curve():
    from psychohistory.models import BassForecaster, bass_curve

    t = np.arange(1, 31) + 6
    truth = 40 * bass_curve(t, 0.003, 0.45)
    history, future = truth[:26], truth[26:]
    out = BassForecaster().forecast([history], horizon=4)[0]
    assert np.max(np.abs(out.point - future)) < 0.05 * truth.max()
    assert np.all(np.diff(out.quantiles, axis=1) >= 0)


def test_combine_averages_points_and_quantiles():
    from psychohistory.models import combine

    a = Forecast(np.zeros(3), np.zeros((3, 9)))
    b = Forecast(np.full(3, 2.0), np.full((3, 9), 4.0))
    c = combine([a, b])
    np.testing.assert_allclose(c.point, 1.0)
    np.testing.assert_allclose(c.quantiles, 2.0)


def test_ensemble_and_bass_show_up_in_backtest_and_ledger(tmp_path):
    from psychohistory.models import bass_curve

    gold, solar = catalog.by_id("gold"), catalog.by_id("adoption_solar")
    for spec, values, freq in [
        (gold, synthetic(300, freq="B").to_numpy(), "B"),
        (solar, 20 * bass_curve(np.arange(1, 41) + 5, 0.002, 0.4), "YS"),
    ]:
        path = data.cache_path(spec, tmp_path / "data")
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.Series(values, index=pd.date_range("1985-01-01", periods=len(values), freq=freq)).to_frame("value").to_csv(
            path, index_label="date"
        )
    common = ["--data-dir", str(tmp_path / "data"), "--out-dir", str(tmp_path / "results"),
              "--ledger", str(tmp_path / "ledger.csv"), "--scored", str(tmp_path / "scored.csv"),
              "--series", "gold", "--series", "adoption_solar", "--model", "drift", "--compare", "mean", "--ensemble"]
    cli.main(["backtest", *common, "--windows", "3"])
    cli.main(["predict", *common])
    results = pd.read_csv(tmp_path / "results" / "backtest_windows.csv")
    assert "ensemble" in set(results["model"])
    assert set(results[results["model"] == "bass"]["series_id"]) == {"adoption_solar"}
    assert "ensemble" in set(pd.read_csv(tmp_path / "ledger.csv")["model"])


def test_crowds_are_more_predictable_than_people(tmp_path):
    from psychohistory import simulate

    tide, people = simulate.simulate_crowd(n_agents=2000, steps=200, seed=1)
    table = simulate.crowd_predictability(tide, people, sizes=(1, 10, 100, 1000))
    shares = table["predictable_share"].to_numpy()
    assert shares[0] < 0.4 and shares[-1] > 0.9
    assert np.all(np.diff(shares) > -0.05)  # grows with crowd size, allowing a little sampling noise


def test_simulate_command_writes_animation(tmp_path, capsys):
    cli.main(["simulate", "--out-dir", str(tmp_path)])
    assert (tmp_path / "plots" / "seldon_crowd.gif").stat().st_size > 1000
    assert "predictable_share" in capsys.readouterr().out


def test_scorecard_shows_numbers_or_placeholders():
    from psychohistory import story

    empty = story.scorecard_svg(story.scorecard(None, "timesfm-2.5"), "timesfm-2.5")
    assert "after the first forecast run" in empty and "Placeholder" in empty
    card = {"news": {"skill": 0.12, "edge": 9, "direction": 0.58, "forecasts": 10},
            "markets": {"skill": -0.03, "edge": 0, "direction": 0.5, "forecasts": 10}}
    svg = story.scorecard_svg(card, "timesfm-2.5", "dark", "2026-10-14")
    assert "+12%" in svg and "−3%" in svg and "about 9 days" in svg and "no edge at any distance" in svg
    assert "Updated 2026-10-14 · 20 backtest forecasts" in svg


def test_time_vault_track_record(tmp_path):
    from psychohistory import story

    spec = catalog.by_id("sp500")
    full = synthetic(400, freq="B")
    rows = pd.concat([
        ledger.predict([spec], {spec.id: full.iloc[:cut]}, DriftForecaster(), made_on=date(2024, 1, 1))
        .assign(made_on=str(cut))
        for cut in (300, 330, 360)
    ])
    scored = ledger.score(rows, {spec.id: full})
    record = story.track_record(scored, "drift")
    assert record["opened"].is_monotonic_increasing and record["opened"].iloc[-1] == len(scored)
    assert record["inside80"].between(0, 1).all() and record["brier"].between(0, 1).all()
    assert story.track_record(scored, "no-such-model").empty
    path = story.plot_track_record(scored, "drift", tmp_path)
    assert path is not None and path.stat().st_size > 1000


def test_web_app_data_and_site(tmp_path):
    import json

    specs = [catalog.by_id("sp500"), catalog.by_id("gold"), catalog.by_id("wiki_ai")]
    for i, spec in enumerate(specs):
        path = data.cache_path(spec, tmp_path / "data")
        path.parent.mkdir(parents=True, exist_ok=True)
        synthetic(500, seed=i, freq=spec.freq).to_frame("value").to_csv(path, index_label="date")
    common = ["--data-dir", str(tmp_path / "data"), "--out-dir", str(tmp_path / "results"),
              "--ledger", str(tmp_path / "ledger.csv"), "--scored", str(tmp_path / "scored.csv"), "--model", "drift"]
    series_args = sum((["--series", s.id] for s in specs), [])
    cli.main(["backtest", *common, *series_args, "--windows", "3"])
    cli.main(["predict", *common, *series_args])
    cli.main(["export", *common])
    text = (tmp_path / "results" / "web" / "data.js").read_text()
    assert text.startswith("window.WP_DATA=") and text.rstrip().endswith(";")
    payload = json.loads(text[len("window.WP_DATA="):].rstrip().rstrip(";"))
    assert payload["meta"]["model"] == "drift" and not payload["meta"]["demo"]
    assert payload["outlook"][0]["id"] == "sp500" and payload["outlook"][0]["fan"]
    assert payload["replay"]["forecasts"] and payload["series"] and payload["crowd"]["share"]["1"] < 0.5
    assert len(payload["evidence"]["sp500"]) == 3  # one record per backtest window, behind each skill number
    assert set(payload["run"]["stages"]) == {"backtest", "predict"}
    lab = payload["lab"]
    assert lab["challenger"] == "seldon" and {b["model"] for b in lab["board"]} == {"drift", "seldon"}
    first = lab["series"][0]
    for r in first["rounds"]:
        assert len(r["model"]) == len(r["seldon"]) == first["horizon"]
        assert r["at"] + first["horizon"] <= len(first["history"])  # the answer is in the history, after the cut
    # Series pages: the windows sit back to back on one shared run of actual values
    for sid, t in payload["track"].items():
        assert len(t["days"]) == len(t["actual"]) and t["days"][0] == 0 and t["days"] == sorted(t["days"])
        for (_, at, q10, q50, q90), nxt in zip(t["windows"], t["windows"][1:] + [None]):
            assert len(q10) == len(q50) == len(q90) and all(a <= b <= c for a, b, c in zip(q10, q50, q90))
            assert at + len(q50) == (nxt[1] if nxt else len(t["actual"]))
    cli.main(["site", *common, "--site-dir", str(tmp_path / "site")])
    built = tmp_path / "site"
    for rel in ("index.html", "sw.js", "manifest.webmanifest", "app/index.html", "app/js/app.js", "app/js/charts.js",
                "app/js/trace.js", "app/js/series.js", "app/data/pipeline.js", "app/css/app.css"):
        assert (built / rel).exists(), rel
    assert (built / "app" / "data" / "data.js").read_text() == text


def test_demo_payload_is_marked_and_complete():
    from psychohistory import web

    payload = web.demo_payload()
    assert payload["meta"]["demo"] is True
    for key in ("headlines", "domains", "horizon", "calibration", "series", "outlook", "vault", "track", "opened"):
        assert payload[key], key
    assert payload["scorecard"]["news"]["skill"] is not None


def test_progress_tracker_matches_repository():
    from psychohistory import progress

    root = Path(__file__).resolve().parents[1]
    areas = progress.load()
    for area in areas:
        for item in area["items"]:
            if item["done"]:
                assert item.get("evidence"), f"{item['title']}: ticked with no evidence"
                assert (root / item["evidence"]).exists(), f"{item['title']}: missing {item['evidence']}"
    readme = (root / "README.md").read_text()
    assert progress.render_markdown(areas) in readme, "README progress block is stale: run scripts/make_readme_art.py"
    for name in ("index.html", "app/index.html", "app/js/app.js", "app/js/charts.js", "sw.js", "manifest.webmanifest"):
        assert (root / "site" / name).exists()


def test_source_files_are_not_gitignored():
    """A broad ignore pattern once kept src/psychohistory/data/ out of the first push."""
    import shutil
    import subprocess

    root = Path(__file__).resolve().parents[1]
    if shutil.which("git") is None or not (root / ".git").exists():
        pytest.skip("not a git checkout")
    source = {".py", ".js", ".css", ".html", ".json", ".svg", ".webmanifest", ".md"}
    files = [str(p.relative_to(root)) for d in ("src", "site", "scripts", "docs")
             for p in (root / d).rglob("*") if p.is_file() and p.suffix in source]
    ignored = subprocess.run(["git", "check-ignore", "--no-index", *files], cwd=root,
                             capture_output=True, text=True).stdout.split()
    assert not ignored, f"these files would never be committed: {ignored}"


class _Response:
    def __init__(self, text="", payload=None, status=200):
        self.text, self._payload, self.status_code = text, payload, status

    def json(self):
        if self._payload is None:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


def test_owid_reads_short_lowercase_columns(monkeypatch):
    from psychohistory.data import owid

    csv = "entity,code,year,solar_share_elec\nWorld,OWID_WRL,2020,3.2\nWorld,OWID_WRL,2021,3.7\nChad,TCD,2021,1.0\n"
    monkeypatch.setattr(owid, "get", lambda *a, **k: _Response(text=csv))
    series = owid.fetch("share-electricity-solar")
    assert list(series.round(1)) == [3.2, 3.7]
    assert series.index[0].year == 2020


def test_weather_sources_parse_their_published_formats(monkeypatch):
    from psychohistory.data import weather

    meteo = {"daily": {"time": ["2026-01-01", "2026-01-02", "2026-01-03"], "temperature_2m_max": [8.1, 9.4, None]}}
    monkeypatch.setattr(weather, "get", lambda *a, **k: _Response(payload=meteo))
    city = weather.city(51.51, -0.13)
    assert list(city) == [8.1, 9.4]  # the archive's not-yet-filled last day is left out, not zero

    reanalyzer = [{"name": "2024", "data": [13.0 + i / 1000 for i in range(366)]},
                  {"name": "2025", "data": [13.5] * 200 + [None] * 166},
                  {"name": "1982-2011 mean", "data": [12.0] * 366}]
    world = weather.parse_reanalyzer(reanalyzer, start="2024-01-01")
    assert world.index[0] == pd.Timestamp("2024-01-01") and world.index[365] == pd.Timestamp("2024-12-31")
    assert len(world) == 366 + 200 and world.iloc[-1] == 13.5  # leap year kept whole, the climatology line skipped

    ice = ("Year, Month, Day,     Extent,    Missing, Source Data\n"
           " YYYY,    MM,  DD, 10^6 sq km, 10^6 sq km, Source data product web sites\n"
           " 2025,    01,  01,     12.901,      0.000, ['x']\n"
           " 2025,    01,  02,  -9999.000,      0.000, ['x']\n"
           " 2025,    01,  03,     12.950,      0.000, ['x']\n")
    extent = weather.parse_sea_ice(ice, start="2025-01-01")
    assert list(extent) == [12.901, 12.95] and extent.index[-1] == pd.Timestamp("2025-01-03")


def test_quake_counts_keep_quiet_days_as_zero():
    from psychohistory.data import quakes

    times = pd.Series(["2026-03-01T01:00:00.000Z", "2026-03-01T23:59:00.000Z", "2026-03-03T12:00:00.000Z"])
    counts = quakes.daily_counts(times, "2026-03-01", "2026-03-04")
    assert list(counts) == [2.0, 0.0, 1.0, 0.0]


def test_new_domains_are_wired_through_every_view():
    from psychohistory import events, radiant, report, story, web, yearbook

    for domain in ("politics", "weather"):
        specs = catalog.select([domain])
        assert len(specs) >= 7 and all(data.source_url(s) or s.source == "composite" for s in specs)
        assert domain in report.DOMAIN_TITLES and domain in story.DOMAIN_PLAIN
        assert domain in dict(web.RADIANT_AREAS) and {radiant.area(s) for s in specs} == {domain}
    assert events.eligible(catalog.by_id("politics_coup")) and not events.eligible(catalog.by_id("weather_london"))
    grouped = {sid for _, _, ids in yearbook.GROUPS for sid in ids}
    assert {s.id for s in catalog.select(["politics", "weather"])} <= grouped
    assert all(s.horizon == 14 for s in catalog.WEATHER)


def test_gdelt_retries_when_rate_limited(monkeypatch):
    from psychohistory.data import gdelt

    payload = {"timeline": [{"data": [{"date": "20260101T000000Z", "value": 1.5}, {"date": "20260102T000000Z", "value": 2.0}]}]}
    replies = iter([_Response("Please limit requests to one every 5 seconds"), _Response(payload=payload)])
    monkeypatch.setattr(gdelt, "get", lambda *a, **k: next(replies))
    monkeypatch.setattr(gdelt.time, "sleep", lambda s: None)
    series = gdelt.fetch('"war"')
    assert list(series) == [1.5, 2.0]


def test_gdelt_stops_waiting_once_its_back_off_budget_is_spent(monkeypatch):
    from psychohistory.data import gdelt

    waits = []
    monkeypatch.setattr(gdelt, "get", lambda *a, **k: _Response("Please limit requests to one every 5 seconds"))
    monkeypatch.setattr(gdelt.time, "sleep", waits.append)
    monkeypatch.setattr(gdelt, "_waited", 0.0)
    monkeypatch.setattr(gdelt, "BUDGET", 50.0)
    with pytest.raises(gdelt.Busy):
        gdelt.fetch('"war"')
    assert sum(w for w in waits if w >= 15) == 45.0  # 15 + 30, then the next 60 s would pass the budget
    with pytest.raises(gdelt.Busy):  # and the next series does not start waiting again
        gdelt.fetch('"peace"')
    assert sum(w for w in waits if w >= 15) == 45.0


def test_a_failed_download_falls_back_to_the_cached_copy(tmp_path, monkeypatch):
    from psychohistory import cli

    spec = catalog.by_id("news_election")
    path = data.cache_path(spec, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    synthetic(120, seed=2).to_frame("value").to_csv(path, index_label="date")

    def busy(**kwargs):
        raise RuntimeError("GDELT still busy")

    monkeypatch.setitem(data.SOURCES, "gdelt", busy)
    series = data.fetch(spec, tmp_path, refresh=True)
    assert len(series) == 120 and "busy" in series.attrs["stale"]
    status = tmp_path / "run_status.json"
    loaded = cli._load([spec, catalog.by_id("news_war")], tmp_path, refresh=True, status=status, stage="fetch")
    stage = __import__("json").loads(status.read_text())["stages"]["fetch"]
    assert list(loaded) == ["news_election"] and "news_election" in stage["stale"] and "news_war" in stage["skipped"]


def test_composite_survives_a_missing_member(tmp_path, monkeypatch):
    composite_spec = catalog.by_id("news_composite")
    members = composite_spec.params["members"]
    for i, member in enumerate(members[1:]):
        spec = catalog.by_id(member)
        path = data.cache_path(spec, tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        synthetic(200, seed=i).to_frame("value").to_csv(path, index_label="date")

    def unavailable(**kwargs):
        raise ValueError("GDELT is down")

    monkeypatch.setitem(data.SOURCES, "gdelt", unavailable)
    series = data.fetch(composite_spec, tmp_path)
    assert len(series) == 200


def test_engine_artwork_is_in_sync(tmp_path):
    """The landing page's exploded engine and the README diagram come from one drawing."""
    import shutil
    import xml.dom.minidom

    from psychohistory import engine_art

    root = Path(__file__).resolve().parents[1]
    copy = tmp_path / "index.html"
    shutil.copy(root / "site" / "index.html", copy)
    assert engine_art.update_site(copy)
    assert copy.read_text() == (root / "site" / "index.html").read_text(), "run scripts/make_readme_art.py"
    assert copy.read_text().count('class="explode__layer') == len(engine_art.LAYERS)
    for theme in engine_art.THEMES:
        svg = engine_art.readme_svg(theme)
        xml.dom.minidom.parseString(svg)  # well-formed
        assert svg == (root / "docs" / "assets" / f"engine-{theme}.svg").read_text()


def test_skipped_series_are_recorded(tmp_path, monkeypatch):
    """A source that fails leaves a visible, explained gap for the app instead of silently vanishing."""
    import json

    spec = catalog.by_id("aapl")
    path = data.cache_path(spec, tmp_path / "data")
    path.parent.mkdir(parents=True, exist_ok=True)
    synthetic(300, freq="B").to_frame("value").to_csv(path, index_label="date")

    def rate_limited(**kwargs):
        raise ValueError("HTTP 429 from GDELT")

    monkeypatch.setitem(data.SOURCES, "gdelt", rate_limited)
    monkeypatch.setitem(data.SOURCES, "yahoo", lambda **kwargs: synthetic(300, freq="B"))
    cli.main(["fetch", "--data-dir", str(tmp_path / "data"), "--out-dir", str(tmp_path / "results"),
              "--series", "aapl", "--series", "news_war"])
    status = json.loads((tmp_path / "results" / "run_status.json").read_text())
    fetch = status["stages"]["fetch"]
    assert fetch["ok"] == ["aapl"]
    assert "429" in fetch["skipped"]["news_war"] and fetch["at"].endswith("Z")


def test_pipeline_inventory_matches_code(tmp_path):
    """Every stage the app and docs/ARCHITECTURE.md describe points at code and tests that exist."""
    from psychohistory import inventory

    root = Path(__file__).resolve().parents[1]
    info = inventory.payload()
    ids = {s["id"] for s in info["stages"]}
    assert {a for edge in info["edges"] for a in edge} <= ids
    for stage in info["stages"]:
        for code in stage["code"]:
            assert (root / code["path"]).exists(), code["path"]
            if code["symbol"]:
                assert code["line"], f"{code['symbol']} not found in {code['path']}"
        for test in stage["tests"]:
            assert test["line"], f"{stage['id']}: no test named {test['name']}"
    assert [c["id"] for c in info["catalog"]] == [s.id for s in catalog.CATALOG]
    assert all(c["url"].startswith("https://") for c in info["catalog"] if c["source"] != "composite")
    stale = "run scripts/make_readme_art.py"
    built = inventory.write_pipeline_js(tmp_path / "pipeline.js").read_text()
    assert (root / "site" / "app" / "data" / "pipeline.js").read_text() == built, stale
    assert (root / "docs" / "ARCHITECTURE.md").read_text() == inventory.architecture_md(), stale


def test_seldon_follows_a_weekly_rhythm_and_a_trend():
    from psychohistory import seldon

    t = np.arange(400)
    rhythm = 50 + 0.05 * t + 6 * np.sin(2 * np.pi * t / 7)  # attention with a weekly cycle and slow growth
    forecast, council = seldon.predict(rhythm[:-14], 14)
    assert council.cycle == 7 and council.replays == seldon.REPLAYS
    assert set(council.weights) == set(seldon.LAWS)
    naive_error = np.mean(np.abs(rhythm[-15] - rhythm[-14:]))
    assert np.mean(np.abs(forecast.point - rhythm[-14:])) < 0.3 * naive_error
    assert abs(sum(council.weights.values()) - 1) < 1e-9
    assert np.all(np.diff(forecast.quantiles, axis=1) >= 0)


def test_seldon_never_peeks_past_the_forecast_date():
    from psychohistory import seldon

    series = synthetic(400, seed=3)
    spec = SeriesSpec("x", "markets", "yahoo", horizon=20)
    model = seldon.SeldonForecaster()
    results = backtest.backtest_series(spec, series, [model, NaiveForecaster()], windows=6)
    rows = results[results["model"] == "seldon-laws"].sort_values("origin")
    assert len(rows) == 6
    # Changing the last window's future must not change any earlier Seldon forecast.
    changed = series.copy()
    changed.iloc[-20:] += 50
    again = backtest.backtest_series(spec, changed, [model, NaiveForecaster()], windows=6)
    again = again[again["model"] == "seldon-laws"].sort_values("origin")
    assert np.allclose(again["mae"].to_numpy()[:-1], rows["mae"].to_numpy()[:-1])
    # Every replay ends before the forecast date.
    assert all(t + 20 <= 300 for t in seldon.replay_dates(300, 20))


def test_seldon_range_is_honest_on_a_random_walk():
    from psychohistory import seldon

    rng = np.random.default_rng(7)
    inside = []
    for _ in range(60):
        walk = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 520)))
        forecast, _ = seldon.predict(walk[:-20], 20)
        inside.append(np.mean((walk[-20:] >= forecast.q(0.1)) & (walk[-20:] <= forecast.q(0.9))))
    assert 0.65 <= np.mean(inside) <= 0.95  # an 80% range should catch reality about 8 times in 10


def test_seldon_handles_short_and_negative_series():
    from psychohistory import seldon

    for y in (np.array([5.0]), np.array([1.0, 2.0]), np.linspace(-3, 3, 40), np.r_[np.zeros(30), np.nan, 1.0]):
        forecast, council = seldon.predict(y, 6)
        assert forecast.quantiles.shape == (6, 9) and np.all(np.isfinite(forecast.quantiles))
        assert seldon.explain(council)
    assert not seldon.predict(np.linspace(-3, 3, 40), 6)[1].log  # negative values are not logged


def test_full_seldon_starts_as_the_model_and_earns_its_share():
    from psychohistory import seldon

    def window(day, laws_error, model_error=1.0):
        actual = np.full(5, 100.0)
        return seldon.Window("news", pd.Timestamp("2026-01-01") + pd.Timedelta(days=int(day)), 101.0,
                             actual + model_error, actual + laws_error, actual)
    good = [window(d, 0.0) for d in range(12)]  # the laws were spot on, the model was not
    assert seldon.learn_share(good[: seldon.MIN_POOL - 1]) == 0.0  # too few windows: all to the model
    assert seldon.learn_share(good) == 1.0
    assert seldon.learn_share([window(d, 3.0) for d in range(12)]) == 0.0  # laws worse: no share
    # Only windows finished by the forecast date count, and only from the same area.
    assert seldon.share_for(good, "news", "2026-01-03") == 0.0
    assert seldon.share_for(good, "markets") == 0.0 and seldon.share_for(good, "news") == 1.0
    base = Forecast(np.full(3, 10.0), np.tile(np.linspace(8, 12, 9), (3, 1)))
    laws = Forecast(np.full(3, 20.0), np.tile(np.linspace(18, 22, 9), (3, 1)))
    assert np.allclose(seldon.blend(base, laws, 0.0).quantiles, base.quantiles)
    assert np.allclose(seldon.blend(base, laws, 0.5).point, 15.0)


def test_full_seldon_in_the_backtest_never_peeks():
    kept, frames = [], []
    spec = SeriesSpec("x", "news", "gdelt", horizon=14)
    series = synthetic(500, seed=4)
    from psychohistory.seldon import SeldonForecaster
    backtest.backtest_series(spec, series, [DriftForecaster(), SeldonForecaster(), NaiveForecaster()], windows=10, keep=kept)
    first = backtest.add_seldon(kept, "drift").sort_values("origin")
    assert len(first) == 10 and np.isclose(first["share"].iloc[0], 1 / 3)  # laws, core, no change start equal
    changed = series.copy()
    changed.iloc[-14:] += 40
    kept2 = []
    backtest.backtest_series(spec, changed, [DriftForecaster(), SeldonForecaster(), NaiveForecaster()], windows=10, keep=kept2)
    again = backtest.add_seldon(kept2, "drift").sort_values("origin")
    assert np.allclose(again["mae"].to_numpy()[:-1], first["mae"].to_numpy()[:-1])


def test_full_seldon_replays_exactly_from_a_laws_only_run(tmp_path):
    """A run from before the full Seldon kept the model's and the laws' paths; replaying the blend
    from them must match scoring it live, and the laws' rows must be renamed for what they were."""
    from psychohistory.seldon import SeldonForecaster
    spec = SeriesSpec("x", "news", "gdelt", horizon=14)
    series = synthetic(500, seed=4) + np.linspace(0, 30, 500)
    kept, paths = [], []
    live = backtest.backtest_series(spec, series, [DriftForecaster(), SeldonForecaster(), NaiveForecaster()], windows=16,
                                    keep=kept, path_rows=paths, paths_for=("drift", "seldon-laws"))
    truth = backtest.add_seldon_blend(kept, "drift").sort_values("origin")
    assert (truth["share"] > 0).any()  # the laws earn a share, so the replay has something to blend
    old = {"seldon-laws": "seldon"}  # how the run named the laws back then
    live.replace({"model": old}).to_csv(tmp_path / "w.csv", index=False)
    pd.DataFrame(paths).replace({"model": old}).to_csv(tmp_path / "p.csv", index=False)
    results, upgraded_paths, upgraded = backtest.upgrade_run(pd.read_csv(tmp_path / "w.csv"), pd.read_csv(tmp_path / "p.csv"), "drift")
    assert upgraded and {"seldon", "seldon-laws"} <= set(results["model"]) and "seldon" in set(upgraded_paths["model"])
    replay = results[results["model"] == "seldon"].sort_values("origin")
    for column in ("mae", "mase", "coverage80", "direction", "share"):
        assert np.allclose(replay[column].to_numpy(float), truth[column].to_numpy(float), equal_nan=True), column
    again, _, twice = backtest.upgrade_run(results, upgraded_paths, "drift")
    assert not twice and len(again) == len(results)


def test_seldon_own_council_leaves_timesfm_out_and_learns_only_from_the_past():
    from psychohistory import radiant, seldon
    assert "timesfm-2.5" not in seldon.OWN and set(seldon.OWN) == {"laws", "core", "naive", "rival"}
    real = np.full(5, 100.0)
    good = {"laws": real + 1, "core": real + 6, "naive": real + 6, "rival": real + 6}
    past = [radiant.Window("markets", pd.Timestamp("2026-01-0%d" % d), good, real) for d in range(1, 6)]
    later = [radiant.Window("markets", pd.Timestamp("2026-03-01"), {**good, "laws": real + 50}, real)]
    other = [radiant.Window("news", pd.Timestamp("2026-01-02"), {**good, "laws": real + 50}, real)]
    assert np.allclose(seldon.own_weights([], "markets"), 0.25)
    w = seldon.own_weights(past + later + other, "markets", "2026-02-01")
    assert w[0] > 0.9 and np.allclose(w, seldon.own_weights(past, "markets", "2026-02-01"))
    f = {e: Forecast(v, v[:, None] + np.linspace(-4, 4, 9)) for e, v in (("laws", real + 1), ("core", real + 6), ("naive", real))}
    mixed, used = seldon.own_mix(f, np.array([0.5, 0.25, 0.25, 0.0]))
    assert np.isclose(used.sum(), 1) and used[3] == 0 and np.allclose(mixed.q(0.5), 0.5 * 101 + 0.25 * 106 + 0.25 * 100)


def test_sealed_laws_only_days_are_named_for_their_maker():
    rows = pd.DataFrame({"made_on": ["d1", "d1", "d2", "d2", "d2"],
                         "model": ["timesfm-2.5", "seldon", "timesfm-2.5", "seldon", "seldon-laws"]})
    named = ledger.name_by_maker(rows)
    assert list(named["model"]) == ["timesfm-2.5", "seldon-laws", "timesfm-2.5", "seldon", "seldon-laws"]
    assert list(rows["model"])[1] == "seldon"  # the file's own rows are left as they are


def test_desk_note_for_any_market(tmp_path):
    from psychohistory import desk
    spec = desk.spec_for("MSFT")
    assert spec.domain == "markets" and spec.params == {"ticker": "MSFT"} and spec.freq == "B"
    assert desk.spec_for("ETH-USD").freq == "D" and desk.spec_for("gold").id == "gold"
    assert desk.spec_for("gold", horizon=5).horizon == 5
    dates = pd.bdate_range("2021-01-04", periods=700)
    prices = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(3).normal(0.0003, 0.01, 700))), index=dates)
    from psychohistory.seldon import SeldonForecaster
    note = desk.build(desk.spec_for("ACME", horizon=10), prices, DriftForecaster(), [SeldonForecaster(), NaiveForecaster()],
                      levels=[prices.iloc[-1] * 1.5], windows=6)
    assert len(note.table) == 10 and {"drift_q50", "seldon_q90", "seldon-laws_p_up"} <= set(note.table)
    assert note.windows == 6 and {"drift", "seldon", "seldon-laws", "naive"} <= set(note.record["model"])
    top = note.levels.iloc[-1]
    assert top["level"] == pytest.approx(prices.iloc[-1] * 1.5) and top["drift"] <= 0.05 + 1e-9  # far above: tail is capped at 5%
    assert note.levels["drift"].is_monotonic_decreasing
    assert 0.05 < note.vol["realized"] < 0.3 and 0.05 < note.vol["drift"] < 0.5  # about 16% a year was simulated
    files = desk.write(note, tmp_path)
    text = files[0].read_text()
    assert "## Track record on this asset" in text and "Not investment advice" in text
    assert pd.read_csv(files[1]).shape[0] == 10
    import json
    assert json.loads(files[2].read_text())["ticker"] == "ACME"


def test_implied_vol_reads_a_lognormal_range():
    from psychohistory import desk
    sigma, steps = 0.2 / np.sqrt(252), 20  # 20% a year
    q10, q90 = 100 * np.exp(-1.2816 * sigma * np.sqrt(steps)), 100 * np.exp(1.2816 * sigma * np.sqrt(steps))
    assert desk.implied_vol(q10, q90, steps, "B") == pytest.approx(0.2, rel=1e-3)
    assert desk.implied_vol(-1, 5, steps, "B") is None


def test_markets_desk_data_lists_every_market_with_its_models():
    from psychohistory import web
    payload = web.demo_payload()
    markets = payload["markets"]
    assert set(markets) == {s.id for s in catalog.CATALOG if s.domain == "markets"}
    gold = markets["gold"]
    assert gold["ticker"] == "GC=F" and gold["freq"] == "B"
    skills = [r[1] for r in gold["models"] if r[1] is not None]
    assert skills == sorted(skills, reverse=True)


def _weekly_ledger(weeks: int, model: str, noise: float, band: float, seed: int = 0) -> pd.DataFrame:
    """A scored ledger of ``weeks`` weekly batches on two random-walk series: the model's middle is
    the truth plus ``noise`` (in units of a day's move) and its 80% range is +-``band`` of that."""
    rng = np.random.default_rng(seed)
    rows = []
    for sid in ("a", "b"):
        dates = pd.date_range("2024-01-01", periods=weeks * 7 + 40, freq="D")
        values = 100 + np.cumsum(rng.normal(0, 1, len(dates)))
        for w in range(weeks):
            t = w * 7 + 10
            for step in range(1, 15):
                actual, last = values[t + step], values[t]
                mid = actual + rng.normal(0, noise)
                rows.append({"made_on": dates[t].date().isoformat(), "model": model, "series_id": sid, "domain": "markets",
                             "scale": "individual", "last_date": dates[t].date().isoformat(), "last_value": last, "step": step,
                             "target_date": dates[t + step].date().isoformat(), "q10": mid - band, "q50": mid, "q90": mid + band,
                             "point": mid, "p_up": 0.5, "actual": actual})
    frame = pd.DataFrame(rows)
    frame["abs_error"] = (frame["actual"] - frame["point"]).abs()
    frame["naive_abs_error"] = (frame["actual"] - frame["last_value"]).abs()
    frame["in_band80"] = (frame["actual"] >= frame["q10"]) & (frame["actual"] <= frame["q90"])
    frame["direction_correct"] = 1.0
    frame["brier"] = 0.25
    return frame


def test_monitor_tells_skill_from_luck_and_raises_drift_alarms():
    from psychohistory import monitor
    sharp = _weekly_ledger(20, "good", noise=0.3, band=0.1, seed=1)  # far better than "no change", range too narrow
    tests = monitor.vs_naive(sharp).set_index("domain")
    assert tests.loc["all", "verdict"] == "better than no change" and tests.loc["all", "p"] < 0.01
    assert monitor.vs_naive(sharp.head(14 * 2)).loc[0, "verdict"].startswith("too early")
    raised = monitor.alarms(sharp)
    assert set(raised["alarm"]) == {"range too narrow"} and set(raised["series_id"]) == {"a", "b"}
    months = monitor.by_month(sharp)
    mine = months[(months["model"] == "good") & (months["domain"] == "all")]
    assert len(mine) >= 4 and (mine["skill"] > 0.5).all()
    assert mine["cum_forecasts"].is_monotonic_increasing and mine["cum_forecasts"].iloc[-1] == len(sharp)
    honest = _weekly_ledger(20, "wide", noise=0.3, band=50, seed=2)
    assert set(monitor.alarms(honest)["alarm"]) == {"range too wide"}
    backtest = pd.DataFrame({"model": ["bad"], "series_id": ["a"], "skill": [0.3]})
    bad = _weekly_ledger(20, "bad", noise=8, band=12, seed=3)  # much worse than "no change"
    kinds = set(monitor.alarms(bad, backtest)["alarm"])
    assert {"edge lost", "worse than no change"} <= kinds
    payload = monitor.payload(pd.concat([sharp, bad]), backtest.assign(domain="markets", coverage80=0.8))
    assert payload["forecasts"] == len(sharp) + len(bad) and payload["months"] and payload["alarms"] and payload["expected"]


def test_diebold_mariano_is_the_t_test_without_lags_and_alarms_control_false_discoveries():
    from psychohistory import monitor
    d = np.random.default_rng(0).normal(0.5, 1, 400)
    stat, p = monitor.diebold_mariano(d, 0)
    assert stat == pytest.approx(d.mean() / np.sqrt(d.var(ddof=1) / len(d)), rel=1e-9) and p < 1e-6
    assert monitor.t_sf(2.0, 3) == pytest.approx(0.0696, abs=1e-4)  # Student's t, not the normal curve
    assert monitor.t_sf(2.776, 4) == pytest.approx(0.025, abs=1e-4)
    assert monitor.diebold_mariano(d[:4], 3) != monitor.diebold_mariano(d[:4], 3)  # four batches cannot carry three lags
    assert monitor.false_discoveries([0.001, 0.03, 0.04, 0.045, 0.9]) == 0.001  # each later one misses its 0.05 * k/5
    assert monitor.false_discoveries([0.001, 0.02, 0.03, 0.04, 0.9]) == 0.04  # step-up: 0.04 <= 0.05 * 4/5 lets all four through
    assert monitor.false_discoveries([0.5, 0.9]) == -1
    assert monitor.diebold_mariano(np.r_[1.0], 0)[1] != monitor.diebold_mariano(np.r_[1.0], 0)[1]  # NaN: not enough data


def test_sealed_batches_are_fingerprinted_and_edits_are_caught(tmp_path):
    series = synthetic(200)
    spec = SeriesSpec("demo", "tech", "wikipedia", freq="D", horizon=5)
    first = ledger.predict([spec], {"demo": series.iloc[:-20]}, NaiveForecaster(), made_on=date(2024, 1, 1))
    path, seals = tmp_path / "ledger.csv", tmp_path / "seals.csv"
    entries = ledger.append(first, path)
    ledger.write_seals(pd.read_csv(path), seals, today="2024-01-01")
    second = ledger.predict([spec], {"demo": series.iloc[:-10]}, DriftForecaster(), made_on=date(2024, 1, 8))
    ledger.append(second, path)
    ledger.write_seals(pd.read_csv(path), seals, today="2024-01-08")
    checked = ledger.verify(pd.read_csv(path), seals)
    assert list(checked["status"]) == ["ok", "ok"] and list(checked["fingerprinted_on"]) == ["2024-01-01", "2024-01-08"]
    tampered = pd.read_csv(path)
    tampered.loc[(tampered["made_on"] == "2024-01-01") & (tampered["step"] == 3), "q50"] += 0.001
    assert list(ledger.verify(tampered, seals)["status"]) == ["changed", "ok"]
    assert list(ledger.verify(tampered[tampered["made_on"] != "2024-01-01"], seals)["status"]) == ["missing", "ok"]
    # Re-fingerprinting never rewrites an old batch's seal, so the edit stays visible.
    ledger.write_seals(tampered, seals, today="2024-01-09")
    assert list(ledger.verify(tampered, seals)["status"]) == ["changed", "ok"]
    assert len(entries) == 5


def test_head_to_head_counts_series_won_on_the_same_windows():
    rows = []
    for k, (domain, edge) in enumerate([("news", 0.5), ("news", 0.8), ("markets", 1.2)]):
        for model, mae in (("timesfm-2.5", 1.0), ("seldon", edge), ("naive", 1.5)):
            rows.append({"series_id": f"s{k}", "domain": domain, "scale": "individual", "model": model, "origin": "2026-01-01",
                         "mae": mae, "mase": mae, "smape": 0.1, "direction": 0.5, "coverage80": 0.8,
                         "pinball": mae, "brier": 0.2})
    duel = backtest.head_to_head(pd.DataFrame(rows), "timesfm-2.5").set_index("domain")
    assert duel.loc["news", "wins"] == 2 and duel.loc["news", "winner"] == "seldon"
    assert duel.loc["markets", "losses"] == 1 and duel.loc["markets", "winner"] == "timesfm-2.5"
    assert duel.loc["all", "series"] == 3 and duel.loc["all", "winner"] == "seldon"
    assert backtest.head_to_head(pd.DataFrame(rows).query("model != 'seldon'"), "timesfm-2.5").empty


def test_ask_reads_your_csv_and_answers_a_level(tmp_path, capsys):
    path = tmp_path / "mine.csv"
    s = synthetic(120, freq="B")
    s.to_frame("close").to_csv(path, index_label="date")  # with a header row, which is skipped
    cli.main(["ask", "--csv", str(path), "--model", "drift", "--horizon", "5", "--above", str(float(s.iloc[-1])),
              "--save", str(tmp_path / "steps.csv"), "--out-dir", str(tmp_path / "results")])
    out = capsys.readouterr().out
    assert "80% sure it lands between" in out and "Chance it ends above" in out
    steps = pd.read_csv(tmp_path / "steps.csv")
    assert len(steps) == 5 and (steps["model_q10"] <= steps["model_q50"]).all() and (steps["model_q50"] <= steps["model_q90"]).all()
    assert pd.Timestamp(steps["date"].iloc[0]).dayofweek < 5  # weekday data is dated in weekdays


def test_ask_seals_a_catalog_series_with_seldon(tmp_path, capsys):
    spec = catalog.by_id("sp500")
    path = data.cache_path(spec, tmp_path / "data")
    path.parent.mkdir(parents=True, exist_ok=True)
    synthetic(600, freq=spec.freq).to_frame("value").to_csv(path, index_label="date")
    common = ["--data-dir", str(tmp_path / "data"), "--out-dir", str(tmp_path / "results"),
              "--ledger", str(tmp_path / "ledger.csv"), "--model", "drift"]
    cli.main(["backtest", *common, "--series", "sp500", "--windows", "4"])
    cli.main(["ask", "sp500", *common, "--horizon", "3", "--seal"])
    out = capsys.readouterr().out
    assert "Seldon middle" in out and "Sealed 6 rows" in out
    sealed = pd.read_csv(tmp_path / "ledger.csv")
    assert set(sealed["model"]) == {"drift", "seldon"} and sealed["p_up"].between(0, 1).all()


def test_opened_forecasts_flag_values_sealed_before_release(tmp_path, capsys):
    from psychohistory import web

    scored = pd.DataFrame({
        "made_on": ["2026-10-18", "2026-10-18"], "model": ["drift", "drift"], "series_id": ["wiki_ai", "wiki_ai"],
        "domain": ["tech", "tech"], "scale": ["individual"] * 2, "last_date": ["2026-10-15"] * 2, "last_value": [10.0, 10.0],
        "step": [3, 4], "target_date": ["2026-10-18", "2026-10-19"], "q10": [8.0, 8.0], "q50": [10.0, 10.5], "q90": [12.0, 13.0],
        "point": [10.0, 10.5], "p_up": [0.5, 0.6], "actual": [11.0, 14.0], "abs_error": [1.0, 3.5], "naive_abs_error": [1.0, 4.0],
        "in_band80": [True, False], "direction_correct": [np.nan, 1.0], "brier": [0.25, 0.16],
    })
    rows = web.opened_payload(scored, "drift")
    assert [r[3] for r in rows] == ["2026-10-19", "2026-10-18"]  # newest first
    assert [r[11] for r in rows] == [0, 1]  # the 18th was sealed on the 18th, before that value was out
    assert rows[0][10] == 1  # it ended higher than the last value
    scored.to_csv(tmp_path / "scored.csv", index=False)
    cli.main(["record", "wiki_ai", "--scored", str(tmp_path / "scored.csv"), "--out-dir", str(tmp_path / "none"), "--model", "drift"])
    out = capsys.readouterr().out
    assert "1 of 2 inside the 80% range" in out and "before the value was published" in out
    with pytest.raises(SystemExit):
        cli.main(["record", "gold", "--scored", str(tmp_path / "scored.csv"), "--out-dir", str(tmp_path / "none"), "--model", "drift"])


def _garch_prices(n=900, alpha=0.10, beta=0.85, seed=3, start="2020-01-01", freq="B"):
    """Prices whose daily log returns follow a GARCH(1,1) with daily variance 1e-4 in the long run."""
    rng = np.random.default_rng(seed)
    var, h, r = 1e-4, 1e-4, np.empty(n)
    for t in range(n):
        r[t] = np.sqrt(h) * rng.standard_normal()
        h = var * (1 - alpha - beta) + alpha * r[t] ** 2 + beta * h
    prices = 100 * np.exp(np.concatenate([[0.0], r.cumsum()]))
    return pd.Series(prices, index=pd.date_range(start, periods=n + 1, freq=freq))


def test_garch_finds_clustering_and_beats_last_months_volatility():
    from psychohistory import volatility

    prices = _garch_prices()
    fit = volatility.fit_garch(volatility.log_returns(prices.to_numpy()))
    assert 0.85 <= fit["alpha"] + fit["beta"] < 1 and 0.03 <= fit["alpha"] <= 0.2
    # Far ahead, the forecast decays to the long-run variance.
    assert volatility.garch_variance(fit, 2000) == pytest.approx(fit["var"], rel=0.05)
    # A 10% / 90% range of exp(+-1.2816 x 0.02 x sqrt(4)) implies a per-step volatility of 0.02.
    q10, q90 = np.exp(-1.2815516 * 0.04), np.exp(1.2815516 * 0.04)
    assert volatility.implied_variance(q10, q90, 4) == pytest.approx(0.02 ** 2, rel=1e-6)
    spec = SeriesSpec("demo_market", "markets", "yahoo", freq="B", horizon=21)
    rows = volatility.backtest(spec, prices)
    table = volatility.summarize(rows).set_index(["series_id", "span", "model"])
    assert table.loc[("all", "1 month", "garch"), "skill"] > 0.05
    assert table.loc[("all", "1 week", "last-month"), "skill"] == 0
    assert set(rows["span"]) == {"1 week", "1 month"}


def test_volatility_backtest_never_sees_the_future():
    from psychohistory import volatility

    prices = _garch_prices(600)
    spec = SeriesSpec("demo_market", "markets", "yahoo", freq="B", horizon=21)
    origin = prices.index[400]
    changed = prices.copy()
    changed.iloc[402:] *= np.exp(np.linspace(0, 1.5, len(changed) - 402))  # a storm after the origin
    before = volatility.backtest(spec, prices)
    after = volatility.backtest(spec, changed)
    key = (before["origin"] == origin.date().isoformat())
    assert key.any()
    pd.testing.assert_series_equal(before.loc[key, "vol"].reset_index(drop=True),
                                   after.loc[after["origin"] == origin.date().isoformat(), "vol"].reset_index(drop=True))


def test_volatility_forecasts_are_sealed_fingerprinted_and_scored(tmp_path):
    from psychohistory import volatility

    prices = _garch_prices(500)
    spec = SeriesSpec("demo_market", "markets", "yahoo", freq="B", horizon=21)
    sealed = ledger.predict([spec], {"demo_market": prices.iloc[:-30]}, DriftForecaster(), made_on=date(2024, 1, 1))
    rows = volatility.forecast_rows([spec], {"demo_market": prices.iloc[:-30]}, sealed, made_on=date(2024, 1, 1))
    assert set(rows["model"]) == {"garch", "ewma", "last-month", "drift"} and set(rows["horizon"]) == {5, 21}
    path, seals = tmp_path / "vol_ledger.csv", tmp_path / "vol_seals.csv"
    entries = volatility.append(rows, path)
    ledger.write_seals(entries, seals, today="2024-01-01", **volatility.LAYOUT)
    assert list(ledger.verify(pd.read_csv(path), seals, **volatility.LAYOUT)["status"]) == ["ok"] * 4
    tampered = pd.read_csv(path)
    tampered.loc[tampered["model"] == "garch", "vol"] *= 0.9
    assert (ledger.verify(tampered, seals, **volatility.LAYOUT).set_index("model")["status"]["garch"]) == "changed"
    scored = volatility.score(entries, {"demo_market": prices}, {"demo_market": "B"})
    assert len(scored) == len(entries) and (scored["qlike"] >= 0).all()
    # Scoring uses only the window after the seal: the returns from last_date to target_date.
    window = prices[(prices.index >= pd.Timestamp(scored["last_date"].iloc[0])) & (prices.index <= pd.Timestamp(scored["target_date"].iloc[0]))]
    expected = volatility.annual(float(np.mean(np.diff(np.log(window.to_numpy())) ** 2)), "B")
    assert scored["realized"].iloc[0] == pytest.approx(expected)
    live = volatility.live_record(scored)
    assert set(live["verdict"]) <= {"the baseline", "too early: 1 of 4 weekly batches"}


def test_world_wire_keeps_last_weeks_headlines_when_a_topic_fails(tmp_path):
    from psychohistory import web, wire

    specs = [catalog.by_id("gold"), catalog.by_id("news_war"), catalog.by_id("adoption_internet")]
    asked = []

    def fetcher(query, records):
        asked.append(query)
        if query == '"war"':
            raise RuntimeError("GDELT busy")
        return [{"title": "Gold edges up", "url": "https://example.org/a", "domain": "example.org", "country": "UK", "seen": "2026-10-26T08:00Z"}]

    path = tmp_path / "wire.json"
    first = wire.fetch(specs, fetcher=lambda q, records: [{"title": f"Old {q}", "url": "https://example.org/old"}])
    wire.write(first, path)
    news = wire.fetch(specs, fetcher=fetcher)
    assert asked == ['"gold price"', '"war"'] and "adoption_internet" not in news["topics"]  # no query, no fetch
    assert set(news["failed"]) == {"news_war"}
    wire.write(news, path)
    saved = wire.read(path)
    assert saved["topics"]["news_war"]["stale"] and saved["topics"]["news_war"]["articles"][0]["title"] == 'Old "war"'
    assert saved["topics"]["gold"]["articles"][0]["title"] == "Gold edges up"
    app = web.wire_payload(saved)
    assert app["topics"]["gold"]["articles"][0][:3] == ["Gold edges up", "https://example.org/a", "example.org"]
    assert app["topics"]["news_war"]["stale"] is True
    assert web.wire_payload(None) == {"fetched": None, "topics": {}}


def test_terminal_ships_with_the_app():
    site = Path(__file__).resolve().parents[1] / "site"
    index = (site / "app" / "index.html").read_text()
    assert 'id="view-terminal"' in index and "js/terminal.js" in index
    assert "app/js/terminal.js" in (site / "sw.js").read_text()
    js = (site / "app" / "js" / "terminal.js").read_text()
    assert "wp-calls-v1" in js and "settled" in js  # the book is the Studio's, and settled calls keep their outcome


def test_event_odds_read_the_tails_and_need_no_future():
    from psychohistory import events

    # A split normal on three quantiles: the 90% quantile itself is a 10% event, the middle a 50% one.
    assert events.probability(1.0, 2.0, 4.0, 4.0, above=True) == pytest.approx(0.10, abs=1e-6)
    assert events.probability(1.0, 2.0, 4.0, 1.0, above=False) == pytest.approx(0.10, abs=1e-6)
    assert events.probability(1.0, 2.0, 4.0, 2.0, above=True) == pytest.approx(0.5, abs=1e-6)
    assert events.probability(1.0, 2.0, 4.0, 40.0, above=True) < 0.01  # the tail goes on past q90
    series = synthetic(900, seed=4).abs() + 5
    spec = SeriesSpec("demo_news", "news", "gdelt", freq="D", horizon=28)
    origins = series.index[[400, 500, 600, 700]]
    paths = pd.DataFrame([{"series_id": "demo_news", "model": "demo", "origin": o.date().isoformat(), "step": 28,
                           "q10": series[o] * 0.8, "q50": series[o], "q90": series[o] * 1.2,
                           "actual": series.iloc[series.index.get_loc(o) + 28]} for o in origins])
    rows = events.backtest(spec, series, paths)
    assert set(rows["model"]) == {"demo", "climatology", "persistence"} and set(rows["event"]) == {"spike", "lull"}
    assert len(rows) == 4 * 2 * 3 and rows["p"].between(0, 1).all()
    assert rows[rows["model"] == "climatology"]["p"].between(0.08, 0.12).all()  # one day in ten, by construction
    changed = series.copy()
    changed.iloc[701:] *= 3  # the future after the last origin changes; its threshold and odds must not
    paths2 = paths.assign(actual=[changed.iloc[changed.index.get_loc(o) + 28] for o in origins])
    again = events.backtest(spec, changed, paths2)
    pd.testing.assert_series_equal(rows["threshold"], again["threshold"])
    pd.testing.assert_series_equal(rows["p"], again["p"])
    table = events.summarize(rows)
    assert {"all", "news", "demo_news"} <= set(table["scope"])
    clim = table[(table["scope"] == "all") & (table["model"] == "climatology")]
    assert (clim["skill_clim"] == 0).all()


def test_event_odds_are_sealed_fingerprinted_and_scored(tmp_path):
    from psychohistory import events

    series = synthetic(600, seed=5).abs() + 5
    spec = SeriesSpec("demo_news", "news", "gdelt", freq="D", horizon=28)
    sealed = ledger.predict([spec], {"demo_news": series.iloc[:-40]}, DriftForecaster(), made_on=date(2024, 1, 1))
    rows = events.forecast_rows([spec], {"demo_news": series}, sealed)
    assert set(rows["model"]) == {"drift", "climatology", "persistence"} and set(rows["event"]) == {"spike", "lull"}
    assert (rows["last_date"] == series.index[-41].date().isoformat()).all()  # thresholds from the history up to the forecast
    path, seals = tmp_path / "event_ledger.csv", tmp_path / "event_seals.csv"
    entries = events.append(rows, path)
    ledger.write_seals(entries, seals, today="2024-01-01", **events.LAYOUT)
    assert list(ledger.verify(pd.read_csv(path), seals, **events.LAYOUT)["status"]) == ["ok"] * 3
    tampered = pd.read_csv(path)
    tampered.loc[tampered["model"] == "drift", "p"] = 0.99
    assert ledger.verify(tampered, seals, **events.LAYOUT).set_index("model")["status"]["drift"] == "changed"
    scored = events.score(entries, {"demo_news": series}, {"demo_news": "news"})
    assert len(scored) == len(rows) and scored["outcome"].isin([0.0, 1.0]).all()
    assert ((scored["p"] - scored["outcome"]) ** 2).round(12).equals(scored["brier"].round(12))
    assert events.live_record(scored)["verdict"].str.startswith(("too early", "a baseline")).all()


def test_year_ledger_dashes_untracked_days_and_compares_on_common_days():
    from psychohistory import yearbook

    days = pd.date_range("2026-01-01", "2026-03-31", freq="D")
    gold = pd.Series(np.linspace(100, 130, len(days)), index=days)
    models = ["timesfm-2.5", yearbook.SELDON, yearbook.LAWS]
    # Backtest paths: TimesFM and the laws for every day of March, Seldon only for half of it.
    rows = []
    for d in pd.date_range("2026-03-01", "2026-03-31"):
        for m, bump in (("timesfm-2.5", 1.0), (yearbook.LAWS, 2.0)) + (((yearbook.SELDON, 0.5),) if d.day <= 15 else ()):
            rows.append({"series_id": "gold", "model": m, "origin": "2026-02-28", "date": d, "q50": gold[d] + bump})
    paths = pd.DataFrame(rows)
    # A sealed forecast for 10 March beats the backtest one.
    sealed = pd.DataFrame([{"series_id": "gold", "model": "timesfm-2.5", "made_on": "2026-03-02", "target_date": "2026-03-10",
                            "q50": 999.0, "last_value": 120.0}])
    t = yearbook.series_table("gold", gold, paths, sealed, models, 2026)
    assert len(t["a"]) == 365 and t["a"][days.get_loc("2026-02-01")] is not None and t["a"][100] is None  # April on: dashes
    i10 = (pd.Timestamp("2026-03-10") - pd.Timestamp("2026-01-01")).days
    assert t["timesfm-2.5"][i10] == 999.0 and t["src"][i10] == "s" and t["o"][i10] == 120.0
    assert t["timesfm-2.5"][0] is None and t["src"][0] == "-"  # nobody forecast 1 January
    s = yearbook.compare(t, models)
    assert s["days"] == 14  # days all three forecast from the same kind of record (10 March: sealed vs backtest, left out)
    assert s["models"][yearbook.SELDON]["mape"] < s["models"][yearbook.LAWS]["mape"]
    assert s["models"][yearbook.SELDON]["closest"] > 0.9
    assert "p" not in s["models"]["timesfm-2.5"] and s["models"][yearbook.LAWS]["dm"] is not None
    lagged = yearbook.compare(t, models, lag=3)
    assert lagged["models"][yearbook.LAWS]["mape"] == s["models"][yearbook.LAWS]["mape"]
    book = yearbook.build({"gold": gold}, paths, None, "timesfm-2.5", year=2026, today=date(2026, 3, 31))
    assert [g["key"] for g in book["groups"]][:3] == ["gold", "silver", "bonds"]
    bonds = next(g for g in book["groups"] if g["key"] == "bonds")
    assert {x["id"] for x in bonds["series"]} == {"us10y", "tlt"} and all(x["stats"]["days"] == 0 for x in bonds["series"])
    lead = {x["model"]: x for x in book["leaders"]}
    assert lead["timesfm-2.5"]["beats"] is None and lead[yearbook.SELDON]["beats"] == 1 and lead[yearbook.LAWS]["beats"] == 0
    assert lead["timesfm-2.5"]["better"] is None and lead[yearbook.LAWS]["better"] == 0
    frame = yearbook.table_frame(book)
    assert set(frame["series_id"]) == {"gold"} and len(frame) == 90 and frame["actual"].notna().all()


def test_radiant_learns_only_from_the_past_and_earns_its_weights():
    from psychohistory import radiant

    y = np.exp(np.cumsum(np.random.default_rng(3).normal(0.001, 0.01, 400))) * 100
    f, beta = radiant.core_predict(y[:300], 21)
    assert beta is not None and f.quantiles.shape == (21, 9) and np.all(np.diff(f.quantiles, axis=1) >= 0)
    changed = y.copy()
    changed[300:] *= 3  # the future is different: the forecast from the first 300 points must not move
    assert np.allclose(radiant.core_predict(changed[:300], 21)[0].point, f.point)
    assert radiant.core_predict(y[:20], 21)[1] is None  # too little history: no change
    # The mix starts with most of the weight on the model and moves it to whichever expert was right.
    assert np.allclose(radiant.weights([]), radiant.PRIOR)
    actual = np.full(5, 100.0)

    def window(day, good):
        paths = {e: actual + (0.0 if e == good else 5.0) for e in radiant.EXPERTS}
        return radiant.Window("markets", pd.Timestamp("2026-01-01") + pd.Timedelta(days=day), paths, actual)
    learned = radiant.weights([window(d, "core") for d in range(6)], "markets")
    assert learned[radiant.EXPERTS.index("core")] > 0.9
    assert np.allclose(radiant.weights([window(d, "core") for d in range(6)], "markets", "2025-12-31"), radiant.PRIOR)
    assert np.allclose(radiant.weights([window(d, "core") for d in range(6)], "news"), radiant.PRIOR)  # other areas do not count


def test_radiant_rival_is_optional_and_earns_its_weight():
    from psychohistory import radiant

    # Without the rival, the mix starts exactly where it did before the rival joined.
    assert np.allclose(radiant.present(radiant.weights([], rival=False), {"model", "laws", "core", "naive"})[:4], (0.7, 0.1, 0.1, 0.1))
    # With it, the two foundation models start level.
    start = radiant.weights([])
    assert start[radiant.EXPERTS.index("model")] == start[radiant.EXPERTS.index("rival")] and abs(start.sum() - 1) < 1e-9
    actual = np.full(5, 100.0)
    old = {e: actual + 5.0 for e in ("model", "laws", "core", "naive")}
    absent = [radiant.Window("tech", pd.Timestamp("2026-01-01") + pd.Timedelta(days=d), old, actual) for d in range(6)]
    assert np.allclose(radiant.weights(absent, "tech"), radiant.PRIOR)  # not charged or credited where it did not run
    right = [radiant.Window("tech", pd.Timestamp("2026-01-01") + pd.Timedelta(days=d), old | {"rival": actual}, actual)
             for d in range(6)]
    assert radiant.weights(right, "tech")[radiant.EXPERTS.index("rival")] > 0.9
    flat = Forecast(np.full(3, 1.0), np.ones((3, 3)))
    mixed = radiant.mix({"model": flat, "laws": flat, "core": flat, "naive": flat}, radiant.weights(right, "tech"))
    assert np.allclose(mixed.point, 1.0)  # a heavily weighted rival that did not run drops out cleanly


def test_radiant_learns_yearly_series_apart_from_daily_ones():
    from psychohistory import backtest, radiant

    solar = next(s for s in catalog.CATALOG if s.source == "owid")
    daily = next(s for s in catalog.CATALOG if s.domain == solar.domain and s.source != "owid")
    assert radiant.area(solar) == radiant.YEARLY and radiant.area(daily) == daily.domain
    assert radiant.domains_of(catalog.CATALOG)[solar.id] == radiant.YEARLY  # yearly series now take part
    # In the backtest, a rival that is right on every yearly window earns weight there, step by step,
    # and only from windows that had finished before each origin.
    years = pd.date_range("1990-01-01", periods=40, freq="YS")
    series = pd.Series(np.linspace(1.0, 40.0, 40), index=years)

    def flat(v, h):
        return Forecast(np.full(h, v), np.full((h, len(QUANTILES)), v))
    kept = []
    for t in range(10, 40 - solar.horizon + 1, solar.horizon):
        h, truth = solar.horizon, series.to_numpy()[t: t + solar.horizon]
        f = {n: flat(series.iloc[t - 1], h) for n in ("timesfm-2.5", backtest.LAWS, radiant.CORE, "naive")}
        f[radiant.RIVAL] = Forecast(truth, np.column_stack([truth] * len(QUANTILES)))
        kept.append({"spec": solar, "series": series, "t": t, "context": series.to_numpy()[:t], "forecasts": f})
    rows = backtest.add_radiant(kept, "timesfm-2.5")
    assert rows["weight_rival"].iloc[0] == pytest.approx(radiant.PRIOR[-1])  # nothing had finished yet
    assert rows["weight_rival"].is_monotonic_increasing and rows["weight_rival"].iloc[-1] > 0.9


def test_radiant_vote_shows_the_split_each_area_earned():
    from psychohistory import radiant, web

    gold = next(s for s in catalog.CATALOG if s.id == "gold")
    days = pd.bdate_range("2025-01-01", periods=400)
    series = pd.Series(np.linspace(100.0, 140.0, 400), index=days)
    rows = []
    for origin in range(200, 400 - 5, 5):  # back-to-back five-day windows: the laws are exact, TimesFM is 5% high
        for step in range(1, 6):
            real = float(series.iloc[origin + step])
            for name, value in (("timesfm-2.5", real * 1.05), ("seldon-laws", real), (radiant.CORE, real * 1.05)):
                rows.append({"series_id": gold.id, "model": name, "origin": days[origin].date().isoformat(),
                             "date": days[origin + step].date().isoformat(), "step": step, "q10": value, "q50": value,
                             "q90": value, "actual": real})
    vote = web.radiant_vote_payload(pd.DataFrame(rows), {gold.id: series}, "timesfm-2.5")
    markets = next(a for a in vote["areas"] if a["key"] == "markets")
    laws = vote["keys"].index("laws")
    assert vote["experts"][laws] == "Crowd laws" and not markets["rival"] and markets["windows"] == 39
    assert markets["now"][laws] > 0.9 and markets["now"][vote["keys"].index("rival")] == 0  # Chronos never ran: no share
    assert abs(sum(markets["now"]) - 1) < 0.01 and abs(sum(markets["start"]) - 1) < 0.01
    shares = [p[1][laws] for p in markets["points"]]
    assert [p[0] for p in markets["points"]] == sorted(p[0] for p in markets["points"]) and shares == sorted(shares)
    assert web.radiant_vote_payload(None, {}, "timesfm-2.5") is None


def test_radiant_lab_replays_the_shipped_mix():
    import importlib.util

    from psychohistory import radiant

    spec = importlib.util.spec_from_file_location("radiant_replay", Path(__file__).resolve().parents[1] / "scripts" / "radiant_replay.py")
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    actual = np.full(5, 100.0)
    windows = []
    for day in range(8):
        paths = {"model": actual + 4, "laws": actual + 9, "core": actual - 6, "naive": actual + 1, "rival": actual - 2 + day % 3}
        w = radiant.Window("markets", pd.Timestamp("2026-01-05") + pd.Timedelta(days=7 * day), paths, actual)
        w.series_id, w.origin = "gold", w.end - pd.Timedelta(days=6)
        windows.append(w)
    for w in windows:  # the lab's default mixer is Radiant exactly as it ships
        flat = {e: Forecast(np.asarray(v, float), np.column_stack([v] * len(QUANTILES))) for e, v in w.paths.items()}
        shipped = radiant.mix(flat, radiant.weights(windows, "markets", w.origin, rival=True)).point
        assert np.allclose(lab.mixer()(w, windows), shipped)
    assert lab.smape([100.0], [100.0]) == 0 and not lab.is_late(windows[0])


def test_leaderboard_ranks_every_model_and_counts_wins_against_the_benchmark():
    from psychohistory import web

    ids = [s.id for s in catalog.CATALOG if s.source != "owid"][:4] + [next(s.id for s in catalog.CATALOG if s.source == "owid")]
    rows = []
    for k, sid in enumerate(ids):
        spec = catalog.by_id(sid)
        for m, err in (("timesfm-2.5", 0.10), ("radiant", 0.09 if k % 2 == 0 else 0.11), ("chronos-bolt", 0.095), ("bass", 0.5)):
            if m == "bass" and k:
                continue  # fits only one series: left off the board
            rows.append({"series_id": sid, "domain": spec.domain, "scale": spec.scale, "model": m, "mae": err, "mase": 1, "smape": err,
                         "direction": 0.5, "coverage80": 0.8, "pinball": 1, "brier": 0.25, "skill": 0.1, "prob_skill": 0.1})
    board = web.leaderboard_payload(pd.DataFrame(rows), "timesfm-2.5")
    names = [r["model"] for r in board["rows"]]
    assert names == ["chronos-bolt", "radiant", "timesfm-2.5"] and "yearly" in board["areas"]
    radiant_row = next(r for r in board["rows"] if r["model"] == "radiant")
    assert radiant_row["beats"] == 3 and radiant_row["of"] == 5
    assert next(r for r in board["rows"] if r["model"] == "timesfm-2.5")["beats"] is None
    assert web.leaderboard_payload(None, "timesfm-2.5") is None


def test_wire_stops_at_its_time_budget():
    from psychohistory import wire

    ticks = iter(range(0, 10_000, 250))  # every look at the clock is 250 s later
    specs = [s for s in catalog.CATALOG if wire.query_for(s)][:4]
    out = wire.fetch(specs, fetcher=lambda q, records: [{"title": q}], budget=600, clock=lambda: next(ticks))
    assert len(out["topics"]) == 2 and all("budget" in v for v in out["failed"].values()) and len(out["failed"]) == 2


def test_alert_tiers_and_three_point_odds():
    from psychohistory import frames

    assert [frames.tier(p) for p in (0.74, 0.75, 0.86, 0.95, 0.99, None)] == [None, "watch", "major", "world", "world", None]
    assert frames.p_up3(90, 100, 110, 100) == pytest.approx(0.5)
    assert frames.p_up3(101, 110, 120, 100) == pytest.approx(0.95)  # the whole 80% range above today
    assert frames.p_up3(80, 90, 99, 100) == pytest.approx(0.05)


def test_long_view_widens_with_the_years_and_never_claims_certainty():
    from psychohistory import frames

    rng = np.random.default_rng(1)
    values = 100 * np.exp(np.cumsum(0.07 + rng.normal(0, 0.15, 30)))
    one, ten = frames.long_view(values, 1), frames.long_view(values, 10)
    assert 0.5 < one["p"] < ten["p"] <= frames.P_CAP
    assert ten["high"] - ten["low"] > one["high"] - one["low"]
    assert frames.long_view(values[:4], 1) is None  # too few years to say anything
    annual = frames.annual(pd.Series(1.0, index=pd.date_range("2020-03-01", "2022-12-31", freq="D")), "D")
    assert list(annual.index) == [2021, 2022]  # 2020 is incomplete


def test_confident_calls_are_tuned_early_and_checked_late():
    from psychohistory import frames

    rng = np.random.default_rng(0)
    rows = []
    for k in range(1600):
        p = rng.uniform(0.2, 0.8)
        up = float(rng.uniform() < p)  # honest odds: stronger leans are right more often
        rows.append({"model": "m", "area": "news", "frame": "week", "p": p, "up": up, "late": k >= 800})
    rule = frames.tune(pd.DataFrame(rows))[0]
    assert rule["reached"] and rule["early_rate"] >= 0.70 and rule["lean"] > 0
    assert rule["late_calls"] < rule["late_windows"]  # it abstains on the weak leans
    assert rule["late_rate"] > rule["late_all_rate"]


def test_today_payload_in_the_demo():
    from psychohistory import web

    F = web.demo_payload()["frames"]
    assert {"frames", "tiers", "items", "alerts", "record", "rules", "target"} <= set(F)
    assert [f for f, _ in F["frames"]] == ["day", "week", "month", "year", "y5", "y10"]
    assert all(a["p"] >= 0.75 for a in F["alerts"])


def test_app_shell_keeps_few_buttons_and_help():
    root = Path(__file__).resolve().parents[1] / "site" / "app"
    html = (root / "index.html").read_text()
    assert 'id="help"' in html and 'id="help-btn"' in html
    assert html.count('class="primary"') == 5
    js = (root / "js" / "today.js").read_text()
    for key in ("wp-watch-v1", "wp-tour-v1", "data-csv", "data-share", "fromOutlook"):
        assert key in js


def test_brief_scores_due_mind_changes_and_streaks():
    from psychohistory import brief

    def row(made_on, sid, step, target, last, q10, q50, q90, actual=None, model="timesfm-2.5"):
        r = {"made_on": made_on, "model": model, "series_id": sid, "domain": "markets", "scale": "aggregate", "last_date": made_on,
             "last_value": last, "step": step, "target_date": target, "q10": q10, "q50": q50, "q90": q90, "point": q50, "p_up": 0.6}
        if actual is not None:
            r |= {"actual": actual, "abs_error": abs(actual - q50), "naive_abs_error": abs(actual - last),
                  "in_band80": q10 <= actual <= q90, "direction_correct": float((actual > last) == (q50 > last)), "brier": 0.1}
        return r

    # Five batches of next-step calls on "a": all right. On "b": all wrong, and the last one far outside its range.
    scored = pd.DataFrame([row(f"2026-11-0{d}", "a", 1, f"2026-11-0{d + 1}", 100, 99, 101, 103, 102) for d in range(1, 6)]
                          + [row(f"2026-11-0{d}", "b", 1, f"2026-11-0{d + 1}", 100, 99, 101, 103, 99.5) for d in range(1, 5)]
                          + [row("2026-11-05", "b", 1, "2026-11-06", 100, 99, 101, 103, 80)])
    due = brief.came_due(scored, "timesfm-2.5")
    assert due["until"] == "2026-11-06" and due["models"][0][0] == "timesfm-2.5" and due["models"][0][1] == 10
    assert due["surprises"][0]["id"] == "b" and due["surprises"][0]["miss"] == pytest.approx(19 / 4, rel=1e-3)
    assert [c["id"] for c in due["nailed"]] == ["a"]  # inside its range and the right direction
    st = brief.streaks(scored, "timesfm-2.5")
    assert st["hot"][0]["id"] == "a" and st["hot"][0]["run"] == 5
    assert st["cold"][0]["id"] == "b" and st["cold"][0]["run"] == 5

    # A change of mind is read at today's level for both batches, so a new starting point alone is no change.
    ledger_rows = pd.DataFrame([row("2026-11-04", "a", 2, "2026-11-06", 100, 95, 98, 101), row("2026-11-05", "a", 1, "2026-11-06", 100, 99, 102, 105),
                                row("2026-11-04", "c", 2, "2026-11-06", 50, 45, 50, 55), row("2026-11-05", "c", 1, "2026-11-06", 60, 45, 50, 55)])
    rev = brief.revisions(ledger_rows, "timesfm-2.5")
    a = next(x for x in rev["items"] if x["id"] == "a")
    assert a["p_old"] < 0.5 < a["p_new"] and a["flip"]
    c = next(x for x in rev["items"] if x["id"] == "c")
    assert c["shift"] == 0 and not c["flip"] and c["moved"] == pytest.approx(0.2)
    b = brief.build(ledger_rows, scored, "timesfm-2.5")
    assert "# The brief" in b["text"] and "changed its mind" in b["text"] and brief.build(None, None, "timesfm-2.5") is None


def test_offline_copy_is_one_file_with_no_network(tmp_path):
    import re

    from psychohistory import offline, web

    site = web.build_site(tmp_path / "site", payload=web.demo_payload())
    copy = site / offline.FILE_NAME
    assert copy.exists()  # build_site makes it, so the local app can hand it out
    html = copy.read_text()
    assert "<script src=" not in html and 'href="css/' not in html and "fonts.googleapis" not in html
    assert "window.WP_DATA=" in html and "window.WP_OFFLINE" in html and "WPOffline" in html and "WPToday" in html
    assert not re.search(r'(href|src)="\.\./', html)  # every link back to the site points at GitHub Pages
    # A closing tag inside the data can never end an inlined script early.
    (site / "app" / "data" / "data.js").write_text('window.WP_DATA={"meta":{"note":"</script><b>"}};')
    assert "</script><b>" not in offline.bundle(site, tmp_path / "x.html").read_text()
    sw = (Path(__file__).resolve().parents[1] / "site" / "sw.js").read_text()
    assert "app/js/offline.js" in sw  # the service worker keeps the offline module too


def test_radiant_ranges_widen_only_where_too_narrow():
    from psychohistory import radiant
    from psychohistory.models import Forecast

    inside = [radiant.band_ratios([0] * 30, [1] * 30, [2] * 30, [1.5] * 30)]  # every outcome inside its range
    outside = [radiant.band_ratios([0] * 30, [1] * 30, [2] * 30, [1.5] * 10 + [4.0] * 20)]  # two in three land 3 halves out
    assert radiant.band_scale(inside) == 1.0 and radiant.band_scale([]) == 1.0
    assert radiant.band_scale(outside) == pytest.approx(3.0)
    f = Forecast(np.array([1.0]), np.array([[0.0, .25, .5, .75, 1.0, 1.25, 1.5, 1.75, 2.0]]))
    wide = radiant.widen(f, 2.0)
    assert wide.q(0.5)[0] == 1.0 and wide.q(0.1)[0] == -1.0 and wide.q(0.9)[0] == 3.0 and radiant.widen(f, 1.0) is f
    paths = pd.DataFrame({"series_id": "s", "model": "m", "origin": "2026-01-01", "date": pd.date_range("2026-01-02", periods=30).astype(str),
                          "step": range(1, 31), "q10": 0.0, "q50": 1.0, "q90": 2.0, "actual": [1.5] * 10 + [4.0] * 20})
    assert radiant.scales_from_paths(paths, "m", {"s": "yearly"}) == {"yearly": pytest.approx(3.0)}
    assert radiant.scales_from_paths(paths, "m", {"s": "yearly"}, at="2026-01-05") == {}  # that window had not finished


def test_world_events_give_odds_a_week_and_a_month_ahead_with_the_news():
    from psychohistory import events, worldevents

    now = pd.DataFrame([
        {"made_on": "2026-11-06", "model": m, "series_id": "news_election", "event": ev, "last_date": "2026-11-05", "last_value": 5.0,
         "threshold": cut, "horizon": 28, "target_date": "2026-12-03", "p": p}
        for ev, cut in (("spike", 6.0), ("lull", 3.0)) for m, p in (("timesfm-2.5", 0.4), ("seldon", 0.45), ("climatology", 0.1), ("persistence", 0.2))])
    ledger_rows = pd.DataFrame([{"made_on": "2026-11-06", "model": m, "series_id": "news_election", "domain": "news", "step": s,
                                 "target_date": f"2026-11-{6 + s:02d}" if s < 20 else "2026-12-03", "last_value": 5.0,
                                 "q10": 4.5, "q50": 6.5 if s == 7 else 5.5, "q90": 9.0, "p_up": 0.7} for m in ("timesfm-2.5", "seldon") for s in (7, 28)])
    summary = pd.DataFrame([{"scope": "all", "event": ev, "model": m, "brier": b, "skill_clim": 0.2, "forecasts": 300}
                            for ev in ("spike", "lull") for m, b in (("timesfm-2.5", 0.06), ("seldon", 0.05))])
    wire = {"fetched": "2026-11-07T03:00Z", "topics": {"news_election": {"articles": [
        {"title": "A vote", "url": "https://example.org/a", "domain": "example.org"}, {"title": "bad", "url": "javascript:alert(1)"}]}}}
    data = {"news_election": pd.Series(np.linspace(3, 5, 60), index=pd.date_range("2026-09-07", periods=60))}
    out = worldevents.build(ledger_rows, now, summary, None, wire, data, "timesfm-2.5")
    assert out["lead"] == {"spike": "seldon", "lull": "seldon"}  # the lowest backtest Brier speaks
    it = out["items"][0]
    assert it["month"]["spike"] == 0.45 and it["base"]["spike"]["climatology"] == 0.1
    assert it["week"]["spike"] == pytest.approx(events.probability(4.5, 6.5, 9.0, 6.0, True), abs=1e-3) and it["week"]["spike"] > 0.5
    assert it["week"]["higher"] > 0.5 and it["week_target"] == "2026-11-13"
    assert [a["title"] for a in it["news"]] == ["A vote"]  # only http(s) links reach the page
    assert len(it["trend"]) == 60 and it["momentum"] > 0
    assert worldevents.build(None, None, None, None, None, {}, "timesfm-2.5") is None

    rows = pd.DataFrame([{"series_id": "s", "origin": "2026-01-01", "event": "spike", "model": "climatology", "threshold": 10.0, "p": 0.1}])
    paths = pd.DataFrame([{"series_id": "s", "model": "m", "origin": "2026-01-01", "step": 7, "q10": 9.0, "q50": 11.0, "q90": 13.0, "actual": 12.0}])
    by = events.skill_by_step(rows, paths, steps=(7,))
    assert by.iloc[0]["model"] == "m" and by.iloc[0]["skill_clim"] > 0  # said likely, and it happened


def test_wire_asks_the_oldest_topics_first():
    from psychohistory import catalog, wire

    specs = [catalog.by_id(i) for i in ("sp500", "news_war", "news_election", "wiki_ai")]
    old = {"fetched": "2026-11-07T03:00Z", "topics": {"news_election": {"fetched": "2026-11-07T03:00Z"}, "sp500": {"stale": True},
                                                       "wiki_ai": {"fetched": "2026-11-01T03:00Z"}}}
    order = [s.id for s in wire.prioritize(specs, old)]
    assert order == ["news_war", "sp500", "wiki_ai", "news_election"]  # never fetched, stale, oldest, newest
    assert [s.id for s in wire.prioritize(specs, None)][:3] == ["news_war", "news_election", "wiki_ai"]  # event topics before markets


def _poly(i, q, p, vol=1e6, end="2026-12-31", closed=False):
    return {"id": str(i), "question": q, "outcomes": '["Yes", "No"]', "outcomePrices": f'["{p}", "{round(1 - p, 4)}"]',
            "volumeNum": vol, "endDate": end + "T00:00:00Z", "closed": closed, "active": True,
            "oneWeekPriceChange": 0.03, "slug": f"m{i}", "events": [{"slug": f"ev{i}"}]}


def test_betting_odds_are_sealed_and_scored_when_questions_settle(tmp_path):
    from psychohistory import bets
    markets = [_poly(1, "Will the Fed cut rates in December?", 0.62), _poly(2, "Lakers vs. Celtics", 0.5),
               _poly(3, "Will Starship reach orbit in 2026?", 0.4, vol=2e6), _poly(4, "A thin market?", 0.3, vol=10),
               _poly(5, "Will the incumbent win the election?", 0.8, end="2026-11-20"),
               _poly(6, "Who wins?", 0.5) | {"outcomes": '["Alice", "Bob"]'}, _poly(7, "Settles tomorrow?", 0.5, end="2026-11-10")]

    def get(path, params=None):
        if path == "/markets":
            return markets if params["offset"] == 0 else []
        m = next(x for x in markets if x["id"] == path.split("/")[-1])
        return m | {"closed": True, "outcomePrices": '["1", "0"]', "closedTime": "2026-11-21 10:00:00+00"} if m["id"] == "5" else m

    # Only open yes/no questions with money behind them, settling in days not hours, no sports; most traded first.
    picked = bets.pick(markets, date(2026, 11, 9))
    assert [m["market_id"] for m in picked] == ["3", "1", "5"]
    assert [m["area"] for m in picked] == ["tech", "markets", "politics"]
    assert picked[0]["url"] == "https://polymarket.com/event/ev3" and picked[1]["p_yes"] == 0.62
    assert bets.yes_price({"outcomes": "not json", "outcomePrices": "[]"}) is None
    assert bets.outcome_of({"closed": True, "outcomePrices": '["0.5", "0.5"]', "outcomes": '["Yes", "No"]'}) is None  # void

    files = [tmp_path / n for n in ("bet_ledger.csv", "bet_scored.csv", "bet_seals.csv")]
    assert bets.run(*files, today=date(2026, 11, 9), get=get) == {"sealed": 3, "settled": 0, "days": 1}
    bets.run(*files, today=date(2026, 11, 9), get=get)                       # a same-day re-run replaces the day
    assert len(bets.read(files[0])) == 3
    markets[4]["outcomePrices"] = '["0.9", "0.1"]'
    bets.run(*files, today=date(2026, 11, 13), get=get)
    done = bets.run(*files, today=date(2026, 11, 22), get=get)
    assert done == {"sealed": 2, "settled": 1, "days": 3}

    scored = bets.read(files[1])
    assert sorted(scored["p_yes"]) == [0.8, 0.9] and set(scored["outcome"]) == {1.0}
    record = bets.record(scored)
    first, week = record["calls"]
    assert first["call"] == "first seen" and first["brier"] == pytest.approx(0.04)
    # 13 Nov (90%) is the last price sealed at least a week before it settled on 21 Nov
    assert week["call"] == "a week out" and week["brier"] == pytest.approx(0.01)
    assert bets.calls(scored).query("call == 'a week out'")["made_on"].item() == "2026-11-13"
    assert (bets.verify(bets.read(files[0]), files[2])["status"] == "ok").all()

    entries = bets.read(files[0])
    entries.loc[0, "p_yes"] = 0.99                                            # an edit after sealing is caught
    assert "changed" in set(bets.verify(entries, files[2])["status"])

    app = bets.payload(bets.read(files[0]), scored)
    assert app["made_on"] == "2026-11-22" and app["days"] == 3 and len(app["items"]) == 2
    fed = next(i for i in app["items"] if i["id"] == "1")
    assert fed["since"] == "2026-11-09" and fed["p0"] == 0.62
    assert "Betting odds from Polymarket" in bets.describe(bets.read(files[0]), scored)
    assert bets.payload(None, None) is None


def test_following_the_forecasts_is_judged_against_holding_with_costs():
    from psychohistory import follow
    rng = np.random.default_rng(3)
    rows = []
    origins = pd.bdate_range("2025-01-01", periods=24, freq="25B")  # windows never end on another origin
    for sid in ("sp500", "gold"):
        level = 100.0
        for o in origins:
            ret = rng.normal(0.01, 0.03)                       # the market drifts up whatever is said
            for model, mid in (("timesfm-2.5", -0.02), ("radiant", 0.02)):
                q50 = level * (1 + mid)
                rows.append({"series_id": sid, "model": model, "origin": o.date().isoformat(), "date": (o + pd.offsets.BDay(20)).date().isoformat(),
                             "step": 20, "q10": q50 * 0.95, "q50": q50, "q90": q50 * 1.05, "actual": level * (1 + ret)})
            rows.append({"series_id": sid, "model": "timesfm-2.5", "origin": "2024-12-01", "date": o.date().isoformat(), "step": 1,
                         "q10": level, "q50": level, "q90": level, "actual": level})   # the close on each origin day
            level *= 1 + rng.normal(0, 0.01)
    w = follow.windows(pd.DataFrame(rows))
    assert set(w["model"]) == {"timesfm-2.5", "radiant"} and len(w) == 2 * 2 * 24
    r = follow.replay(w, cost=0.001)
    by = {x["model"]: x for x in r["rows"]}
    # Always out (says lower) earns nothing; always in pays the cost on top of the market's own return.
    assert by["timesfm-2.5"]["follow"] == 0 and by["timesfm-2.5"]["inside"] == 0
    assert by["radiant"]["follow"] == pytest.approx(by["radiant"]["hold"] - 0.002)
    assert by["radiant"]["t"] < -2 or by["radiant"]["t"] is None   # a steady cost is a real (if small) loss
    assert r["curves"]["20"]["hold"][-1] == pytest.approx(100 * w[w.model == "radiant"]["ret"].sum(), abs=0.1)
    assert {o["model"] for o in r["oos"]} == {"timesfm-2.5", "radiant"} and all(o["origins"] == 12 for o in r["oos"])
    assert "did not beat simply holding" in r["verdict"]
    assert "Research, not investment advice." in follow.describe(r)
    assert follow.payload(None) is None and follow.windows(pd.DataFrame(rows).assign(series_id="news_war")).empty


def test_seal_buttons_and_sort_headers_meet_the_accessibility_floor():
    import re
    css = (Path(__file__).resolve().parents[1] / "site" / "app" / "css" / "app.css").read_text()

    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    fills = re.findall(r"--seal-fill: (#[0-9a-f]{6})", css)
    inks = re.findall(r"--on-seal: (#[0-9a-f]{6})", css)
    assert len(fills) == 2 and len(inks) == 2                      # dusk and light themes
    for fill, ink in zip(fills, inks):
        a, b = sorted((lum(fill), lum(ink)))
        assert (b + 0.05) / (a + 0.05) >= 4.5, (fill, ink)      # WCAG AA for the seal buttons' text
    assert "th button { all: unset; cursor: pointer; display: inline-flex; align-items: center; min-height: 24px" in css


def test_coming_up_calendar_lists_settle_days_and_exports_ics():
    import json
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    root = Path(__file__).resolve().parents[1] / "site"
    for js in ("calendar.js", "share.js"):
        assert f"app/js/{js}" in (root / "sw.js").read_text() and f'src="js/{js}"' in (root / "app" / "index.html").read_text()
    data = {"meta": {"model": "radiant", "generated": "2026-11-09"}, "outlook": [{"made_on": "2026-11-09"}],
            "frames": {"items": [{"id": "gold", "title": "Gold", "area": "markets", "frames": {
                "day": {"radiant": {"p": 0.5, "mid": 0, "low": -0.01, "high": 0.01, "date": "2026-11-10"}},
                "week": {"radiant": {"p": 0.62, "mid": 0.01, "low": -0.02, "high": 0.03, "date": "2026-11-16", "sure": False}},
                "month": {"radiant": {"p": 0.41, "mid": -0.01, "low": -0.05, "high": 0.04, "date": "2026-12-07"}}}}]},
            "worldevents": {"items": [{"title": "War", "area": "news", "week_target": "2026-11-16", "month_target": "2026-12-07",
                                       "week": {"spike": 0.31}, "month": {"spike": 0.05}}]},
            "bets": {"items": [{"q": "Will it rain, settle; day?", "area": "weather", "url": "https://polymarket.com/event/x", "end": "2026-11-20", "p": 0.7}]}}
    script = """
global.window = {}; global.localStorage = { getItem: () => JSON.stringify([{ title: 'Silver', date: '2026-11-18', value: 30, lo: 29, hi: 31 }]) };
global.location = { href: 'https://example.org/app/#calendar', host: 'example.org' };
require(process.argv[1] + '/app/js/calendar.js');
const C = window.WPCalendar; C.teaser(JSON.parse(process.argv[2]));
const list = C.entries();
console.log(JSON.stringify({ list: list.map((e) => [e.date, e.kind]), ics: C.ics(list) }));
"""
    out = json.loads(subprocess.run(["node", "-e", script, str(root), json.dumps(data)], capture_output=True, text=True, check=True).stdout)
    # The next-day call is left out, the 5% flare-up is too small to note, and everything is in date order.
    assert out["list"] == [["2026-11-16", "event"], ["2026-11-16", "forecast"], ["2026-11-18", "yours"], ["2026-11-20", "bet"], ["2026-12-07", "forecast"]]
    ics = out["ics"]
    assert ics.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0") and ics.endswith("END:VCALENDAR\r\n") and ics.count("BEGIN:VEVENT") == 5
    assert "DTSTART;VALUE=DATE:20261120" in ics and "DTEND;VALUE=DATE:20261121" in ics
    assert r"Will it rain\, settle\; day?" in ics.replace("\r\n ", "")              # text escaped, then unfolded
    assert all(len(line) <= 75 for line in ics.split("\r\n"))                     # folded lines (RFC 5545)
    assert "https://example.org/app/#series/gold" in ics.replace("\r\n ", "")


def test_feed_and_api_follow_the_app_data(tmp_path):
    import json
    import subprocess
    import sys
    import xml.etree.ElementTree as ET

    from psychohistory import feeds, web

    site = web.build_site(tmp_path / "site", payload=web.demo_payload())
    D = feeds.read_data(site)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    feed = ET.parse(site / "feed.xml").getroot()
    entries = feed.findall("a:entry", ns)
    ids = [e.findtext("a:id", namespaces=ns) for e in entries]
    assert entries and len(ids) == len(set(ids)) and all(i.startswith(feeds.TAG) for i in ids)
    for e in entries:  # RFC 4287 needs id, title, updated and a link or content in each entry
        assert e.findtext("a:title", namespaces=ns) and e.find("a:content", ns).get("type") == "html"
        assert len(e.findtext("a:updated", namespaces=ns)) == 20
    updated = [e.findtext("a:updated", namespaces=ns) for e in entries]
    assert updated == sorted(updated, reverse=True) and feed.findtext("a:updated", namespaces=ns) >= updated[0]
    assert "demo data" in feed.findtext("a:title", namespaces=ns)  # a demo never passes for real forecasts
    # The API says what the app says.
    index = json.loads((site / "api" / "index.json").read_text())
    assert [s["id"] for s in index["series"]] == [o["id"] for o in D["outlook"]]
    first, o = index["series"][0], D["outlook"][0]
    assert (first["chance_higher"], first["range80"], first["sealed_on"]) == (o["p_up"], [o["low"], o["high"]], o["made_on"])
    doc = json.loads((site / "api" / "series" / f"{o['id']}.json").read_text())
    assert len(doc["fan"]) == len(o["fan"]) and doc["fan"][0]["q50"] == o["fan"][0][2] and doc["history"][-1]["value"] == o["history"][-1][1]
    assert index["record"]["forecasts_judged"] == D["vault"][-1]["opened"]
    # Pages runs it as a plain script, without the package installed.
    (site / "feed.xml").unlink()
    run = subprocess.run([sys.executable, "-I", str(Path(feeds.__file__)), str(site)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert (site / "feed.xml").exists()
    root = Path(__file__).resolve().parents[1]
    assert "python3 src/psychohistory/feeds.py _site" in (root / ".github" / "workflows" / "pages.yml").read_text()


def test_embed_card_is_listed_and_offered_on_series_pages():
    root = Path(__file__).resolve().parents[1] / "site"
    html = (root / "app" / "embed.html").read_text()
    assert 'src="data/data.js"' in html and 'target="_top"' in html and "fonts.googleapis" not in html
    assert "app/embed.html" in (root / "sw.js").read_text()
    assert 'id="sp-embed"' in (root / "app" / "js" / "series.js").read_text()
    for page, href in ((root / "index.html", 'href="feed.xml"'), (root / "app" / "index.html", 'href="../feed.xml"')):
        assert 'type="application/atom+xml"' in page.read_text() and href in page.read_text()


def test_champions_rank_models_per_series_and_test_the_pick_honestly():
    import numpy as np

    from psychohistory import champions

    rng = np.random.default_rng(3)
    rows = []
    for s in range(6):
        for o in range(8):
            for model, noise in (("radiant", 1.0), ("seldon", 1.0 + 0.1 * (s % 2)), ("timesfm-2.5", 1.2)):
                for step in (1, 2, 3):
                    a = 100 + rng.normal()
                    m = a + rng.normal(0, noise)
                    rows.append((f"s{s}", model, f"2026-{o + 1:02d}-01", f"2026-{o + 1:02d}-0{step + 1}", step, m - 2, m, m + 2, a))
    paths = pd.DataFrame(rows, columns=["series_id", "model", "origin", "date", "step", "q10", "q50", "q90", "actual"])
    P = champions.payload(paths, "timesfm-2.5")
    first = P["series"]["s0"]
    assert [r[1] for r in first] == sorted(r[1] for r in first) and all(r[3] == 8 for r in first)  # best first, 8 windows
    H = P["holdout"]
    assert H["default"] == "radiant" and H["series"] == 6 and H["better"] + H["worse"] <= 6 and 0 <= H["kept"] <= 6
    assert champions.payload(None) is None and champions.holdout(paths.iloc[:0]) is None


def test_compare_view_is_wired_and_lines_up_series_from_their_sealing_day():
    import json
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    root = Path(__file__).resolve().parents[1] / "site"
    assert "app/js/compare.js" in (root / "sw.js").read_text() and 'src="js/compare.js"' in (root / "app" / "index.html").read_text()
    assert 'href="#compare"' in (root / "app" / "index.html").read_text() and '"compare"' in (root / "app" / "js" / "app.js").read_text()
    o = {"id": "gold", "history": [["2026-11-06", 100.0], ["2026-11-09", 110.0]], "fan": [["2026-11-10", 99.0, 110.0, 121.0]]}
    js = f"global.window={{}};require({json.dumps(str(root / 'app' / 'js' / 'compare.js'))});console.log(JSON.stringify(window.WPCompare.relative({json.dumps(o)})))"
    out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    assert out["hist"][-1] == ["2026-11-09", 0] and abs(out["hist"][0][1] + 1 / 11) < 1e-9
    assert out["band"][1][0] == "2026-11-10" and abs(out["band"][1][1] + 0.1) < 1e-9 and abs(out["band"][1][2] - 0.1) < 1e-9
    assert out["mid"][0] == ["2026-11-09", 0]


def test_vault_track_record_grid_is_wired():
    root = Path(__file__).resolve().parents[1] / "site"
    html = (root / "app" / "index.html").read_text()
    js = (root / "app" / "js" / "app.js").read_text()
    for hook in ('id="vault-grid"', 'id="vault-grid-meta"', 'id="vault-grid-filter"'):
        assert hook in html
    vault = js[js.index("    vault() {"):js.index("    crowd() {")]
    assert "grid();" in vault                                   # drawn whenever the vault opens
    assert "(s.hit + 1) / (s.n + 2)" in js                       # one lucky forecast cannot top the ranking
    css = (root / "app" / "css" / "app.css").read_text()
    assert all(c in css for c in (".tg-all", ".tg-some", ".tg-none", ".tg-gap"))


def _node(script, *args):
    import json
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    return json.loads(subprocess.run(["node", "-e", script, *args], capture_output=True, text=True, check=True).stdout)


def test_compare_draws_a_sealed_week_against_what_really_happened():
    import json
    root = Path(__file__).resolve().parents[1] / "site"
    data = {"meta": {"model": "timesfm-2.5"},
            "outlook": [{"id": "gold", "history": [["2026-10-15", 100.0], ["2026-10-16", 100.0], ["2026-10-19", 104.0], ["2026-10-20", 96.0]]}],
            # [id, model, made_on, target, step, q10, q50, q90, actual, p_up, up, lag]
            "opened": [["gold", "timesfm-2.5", "2026-10-18", "2026-10-19", 1, 98, 101, 103, 104, 0.6, 1, 0],
                       ["gold", "timesfm-2.5", "2026-10-18", "2026-10-20", 2, 97, 102, 105, 96, 0.6, 0, 0],
                       ["gold", "timesfm-2.5", "2026-10-18", "2026-10-21", 3, 96, 103, 106, 99, 0.6, 0, 0],
                       ["gold", "seldon", "2026-10-18", "2026-10-19", 1, 98, 101, 103, 104, 0.6, 1, 0]]}
    script = f"global.window={{}};require({json.dumps(str(root / 'app' / 'js' / 'compare.js'))});const C=window.WPCompare,D=JSON.parse(process.argv[1]);" \
             "console.log(JSON.stringify({b:C.sealedBatch(D,'gold','timesfm-2.5','2026-10-18'),none:C.sealedBatch(D,'gold','timesfm-2.5','2026-10-25'),weeks:C.batchesOf(D,'seldon',['gold']),models:C.modelsOpened(D)}))"
    out = _node(script, json.dumps(data))
    b = out["b"]
    assert b["start"] == ["2026-10-16", 100.0]                    # the last value before the first due day
    assert [d["inside"] for d in b["days"]] == [False, False, True] and b["hits"] == 1
    assert b["real"][-1] == ["2026-10-21", 99]                     # a due-day value past the history's end joins the real line
    assert abs(b["said"] - 0.03) < 1e-9 and abs(b["did"] + 0.01) < 1e-9 and b["called"] is False
    assert out["none"] is None and out["weeks"] == ["2026-10-18"] and out["models"] == ["timesfm-2.5", "seldon"]


def test_odds_advice_is_held_back_unless_the_record_beats_a_coin_flip():
    import json
    root = Path(__file__).resolve().parents[1] / "site"
    def market(id, windows):
        # each window: (p_up, move); actual path from 100 to 100 * (1 + move)
        actual, wins, ev = [100.0], [], []
        for k, (p, move) in enumerate(windows):
            at = len(actual)
            actual += [100.0, 100.0 * (1 + move)]
            actual.append(100.0)  # back to the base before the next window
            wins.append([f"2025-{k // 28 + 1:02d}-{k % 28 + 1:02d}", at, [1, 1], [1, 1], [1, 1]])
            ev.append([wins[-1][0], 1.0, 0, p, int(move > 0)])
        return {"start": "2025-01-01", "days": list(range(len(actual))), "actual": actual, "windows": wins}, ev
    good, ev_good = market("a", [(0.7, 0.02)] * 22 + [(0.7, -0.01)] * 3 + [(0.3, 0.01)] * 5 + [(0.5, 0.01)] * 4)
    data = {"series": [{"id": "a", "domain": "markets"}, {"id": "n", "domain": "news"}], "track": {"a": good, "n": good}, "evidence": {"a": ev_good, "n": ev_good}}
    script = f"global.window={{}};require({json.dumps(str(root / 'app' / 'js' / 'advice.js'))});const A=window.WPAdvice,D=JSON.parse(process.argv[1]);" \
             "console.log(JSON.stringify({buy:A.advise(D,0.75),sell:A.advise(D,0.2),mid:A.advise(D,0.5),R:A.record(D),tail:A.binomTail(15,20)}))"
    out = _node(script, json.dumps(data))
    assert out["R"]["n"] == 34                                       # markets only: the news copy is ignored
    assert out["R"]["buy"]["n"] == 25 and out["R"]["buy"]["right"] == 22 and out["R"]["buy"]["works"]
    assert out["buy"]["action"] == "Buy or keep holding" and out["buy"]["backed"]
    assert out["sell"]["action"] == "Hold" and not out["sell"]["backed"]   # 0 of 5 fell, and too few anyway
    assert out["mid"]["tier"] == "hold" and out["mid"]["action"] == "Hold"
    assert abs(out["tail"] - 0.020694732666015625) < 1e-12           # P(X >= 15), X ~ Bin(20, 1/2)
    html = (root / "app" / "index.html").read_text()
    assert html.index('src="js/advice.js"') < html.index('src="js/series.js"') and "app/js/advice.js" in (root / "sw.js").read_text()


def test_year_ledger_shows_the_no_change_yardstick():
    js = (Path(__file__).resolve().parents[1] / "site" / "app" / "js" / "year.js").read_text()
    assert "function yardstick(" in js and 'title="the value each forecast started from' in js
    assert "never the real value" in js                              # the note says a forecast is not reality
