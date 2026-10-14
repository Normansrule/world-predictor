# Methodology

## What "predicting the future" means here

Each series is a daily (news, tech attention, crypto), business-day (markets) or annual (tech
adoption) time series. TimesFM is used **zero-shot**: no fine-tuning, the model only sees the
most recent 1,024 points of a series and returns a median forecast and nine deciles.

| Domain | Frequency | Horizon |
|---|---|---|
| News (GDELT coverage share) | daily | 28 days |
| Markets | business days | 21 trading days (about a month) |
| Bitcoin | daily | 28 days |
| Tech attention (Wikipedia) | daily | 28 days |
| Tech adoption (OWID) | yearly | 3 years |

## Backtest

For each series, 12 forecast origins (configurable with `--windows`) are placed one horizon
apart, ending one horizon before the latest data. At each origin the model sees only data up
to that day (`tests/test_pipeline.py::test_backtest_never_sees_the_future` checks this).

Every model is run on the same windows: TimesFM plus three baselines.

- `naive`: last value carried forward (a random walk). For prices this is famously hard to
  beat; the efficient-market hypothesis says it should be unbeatable.
- `drift`: last value plus the historical average slope.
- `mean`: average of the last 90 points.

Two more comparison models come from the reference list (REFERENCES.md):

- `bass` (adoption series only): the Bass diffusion curve, fitted by grid search over
  innovation p, imitation q and the start of diffusion, with market size solved by least
  squares. Uncertainty is the fit's residual spread, widening with the square root of the
  steps ahead.
- `ensemble` (with `--ensemble`): the average of the model under test, its `--compare` rivals
  and AutoETS, averaging each decile separately (quantile averaging, as in GluonTS).

Baseline uncertainty bands come from each series' own history of k-step changes, so the
calibration comparison is fair.

## Metrics

- **Skill** = 1 - MAE(model) / MAE(naive), computed per series, then the median across series.
- **MASE**: MAE scaled by the in-sample one-step naive error. Comparable across series.
- **Direction**: share of windows where the sign of the change over the horizon was right. A
  forecast of exactly no change is not counted.
- **Coverage80**: share of actual values inside the 10%-90% forecast band. Target 0.80.
- **Brier**: the forecast's deciles are turned into a probability that the series ends the
  horizon above today's value (interpolated between deciles, tails capped at 5% and 95%).
  Brier = (probability - outcome)^2, averaged. 0.25 is a coin flip; lower is better.
- **Pinball**: average quantile loss over the nine deciles, scaled like MASE. Lower is better.

## The Seldon hypotheses

1. *Predictability*: median skill above 0 in a domain.
2. *Law of large numbers*: aggregates (indices, composites, world totals) show higher skill
   and lower MASE than individual series in the same domain.
3. *Horizon*: skill at each step ahead (`results/skill_by_step.csv`), computed per series as
   1 - mean scaled error(model) / mean scaled error(naive) at that step, then the median per
   domain. Yearly adoption series have too few steps and are excluded.
4. *Honest odds*: backtest forecasts are grouped by the probability they gave of ending higher
   (0-20%, 20-40%, ...), and each group's stated probability is compared with how often the
   series really ended higher. Matching numbers mean the odds can be taken at face value.
5. *Crises*: windows with coverage80 at or below 0.5 are listed as events the model missed.

## Known limitations

- **Leakage through pretraining.** TimesFM was pretrained on large public corpora that may
  include some of these very series up to its release date. Backtest windows before that date
  can look better than true foresight. The prediction ledger exists to remove this doubt:
  only ledger scores are fully out of sample.
- **Attention is not events.** GDELT and Wikipedia measure how much the world talks about
  something, not whether it happens.
- **Prices and returns.** Forecasting price levels makes MAE comparable to the naive baseline
  but says nothing about tradable returns after costs. This is not a trading system.
- **Data revisions and gaps.** Sources change history occasionally; the CSV cache in `data/`
  pins what was used for a run.
