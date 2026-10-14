"""Offline tests: synthetic data, baseline models only (no network, no TimesFM download)."""

from __future__ import annotations

from datetime import date

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
    assert "## 6. What the model expects next" in report and "plots/sp500.png" in report
    assert (tmp_path / "results" / "plots" / "skill_by_domain.png").exists()
    assert (tmp_path / "results" / "plots" / "sp500.png").exists()
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
