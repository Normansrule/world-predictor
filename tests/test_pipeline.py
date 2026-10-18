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
    assert len(pd.read_csv(tmp_path / "ledger.csv")) == sum(s.horizon for s in specs)


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
    assert set(pd.read_csv(tmp_path / "ledger.csv")["model"]) == {"drift", "mean"}


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
    cli.main(["site", *common, "--site-dir", str(tmp_path / "site")])
    built = tmp_path / "site"
    for rel in ("index.html", "sw.js", "manifest.webmanifest", "app/index.html", "app/js/app.js", "app/js/charts.js", "app/css/app.css"):
        assert (built / rel).exists(), rel
    assert (built / "app" / "data" / "data.js").read_text() == text


def test_demo_payload_is_marked_and_complete():
    from psychohistory import web

    payload = web.demo_payload()
    assert payload["meta"]["demo"] is True
    for key in ("headlines", "domains", "horizon", "calibration", "series", "outlook", "vault"):
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
    files = [str(p.relative_to(root)) for d in ("src", "site", "scripts", "docs")
             for p in (root / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    ignored = subprocess.run(["git", "check-ignore", "--no-index", *files], cwd=root,
                             capture_output=True, text=True).stdout.split()
    assert not ignored, f"these files would never be committed: {ignored}"
