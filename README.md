# World Predictions

**Can a machine do Hari Seldon's psychohistory?**

In Isaac Asimov's *Foundation*, the mathematician Hari Seldon forecasts the fall of the Galactic
Empire with *psychohistory*: statistics that cannot predict any one person, but can predict the
behaviour of enormous populations. This project tests a small, measurable version of that idea
with [**TimesFM**](https://github.com/google-research/timesfm), Google Research's open-source
time-series foundation model, across three kinds of "future":

| Domain | What is forecast | Data |
|---|---|---|
| **World events in the news** | Share of all world news coverage about war, elections, inflation, climate, outbreaks, protests | [GDELT Project](https://www.gdeltproject.org/) |
| **Stock and value markets** | S&P 500, Nasdaq-100, MSCI World, Apple, NVIDIA, Tesla, Exxon, **gold**, **silver**, oil, copper, Bitcoin | Yahoo Finance via [yfinance](https://github.com/ranaroussi/yfinance) |
| **New technologies** | Public attention to LLMs, AI, quantum computing, CRISPR, EVs, fusion, humanoid robots; adoption of solar, wind, internet | [Wikimedia Pageviews](https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews), [Our World in Data](https://ourworldindata.org/) |

Nothing here is financial advice. Most of the interesting results are about *where prediction
fails*.

## The three Seldon tests

1. **Can the future be predicted at all?** Every forecast is scored against a naive
   "tomorrow looks like today" baseline. *Skill* is the share of error TimesFM removes
   compared with that baseline; zero means no better than naive.
2. **Seldon's law of large numbers.** Psychohistory only works on huge populations. Each series
   is tagged *aggregate* (an index, a composite, a world total) or *individual* (one company,
   one topic). If Seldon is right, aggregates should be more predictable.
3. **Seldon crises.** Windows where reality leaves the model's 80% band are the shocks the
   model did not foresee. They are listed in every report.

And one honesty rule: backtests can flatter a model that was pretrained on the same history,
so the repo keeps a **prediction ledger**. Forecasts are written to `predictions/ledger.csv`
with a date *before* the future happens and scored once it arrives, like Seldon's recordings
in the Time Vault.

Results land in [`results/REPORT.md`](results/REPORT.md). Methodology details are in
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Quick start

```bash
git clone https://github.com/Normansrule/world-predictions.git
cd world-predictions
python -m venv .venv && source .venv/bin/activate
pip install -e ".[timesfm,dev]"      # installs TimesFM with PyTorch

psychohistory fetch                  # download all series into data/ (cached)
psychohistory backtest               # rolling backtest vs baselines, writes results/REPORT.md
psychohistory predict                # record forecasts in predictions/ledger.csv, plus fan charts
psychohistory score                  # score ledger forecasts whose dates have arrived
```

Useful options: `--domain markets` (repeatable), `--series gold --series silver`,
`--model timesfm-3`, `--windows 24`, `-v` for progress logs.

Without a GPU everything still runs on CPU; TimesFM 2.5 has 200M parameters. To try the
pipeline without downloading the model, use a baseline: `psychohistory backtest --model drift`.

## Models

| Name | Model | Weights licence |
|---|---|---|
| `timesfm-2.5` (default) | [google/timesfm-2.5-200m-pytorch](https://huggingface.co/google/timesfm-2.5-200m-pytorch) | Apache-2.0 |
| `timesfm-3` | [google/timesfm-3.0-pytorch](https://huggingface.co/google/timesfm-3.0-pytorch) | **Non-commercial only** ([licence](https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE)) |
| `naive`, `drift`, `mean` | Baselines in `src/psychohistory/models.py` | Apache-2.0 (this repo) |

TimesFM 2.5 is the default so the whole project stays usable under Apache-2.0. TimesFM 3.0 is
stronger but its downloaded weights may not be used commercially or in production.

## Automation

`.github/workflows/predict.yml` runs every Monday: it fetches fresh data, records new TimesFM
forecasts in the ledger, scores old ones, and commits the results. On the first of each month it
also reruns the full backtest. Raw data is not committed (see Credits for each source's terms).

## Adding your own predictions

Add a `SeriesSpec` to [`src/psychohistory/catalog.py`](src/psychohistory/catalog.py), for example:

```python
_stock("platinum", "PL=F", "Platinum futures")
_news("news_ai_regulation", '"AI regulation"', "Coverage of AI regulation")
_wiki("wiki_solid_state_battery", "Solid-state_battery", "Wikipedia views: Solid-state battery")
```

## Project layout

```
src/psychohistory/
  catalog.py     the series to forecast, by domain, tagged aggregate / individual
  data/          loaders: gdelt.py, markets.py, wikipedia.py, owid.py (+ CSV cache)
  models.py      TimesFM 2.5 / 3.0 wrappers and baseline forecasters
  metrics.py     MAE, MASE, sMAPE, direction, 80% coverage, pinball loss
  backtest.py    rolling-origin backtest and the Seldon summary tables
  ledger.py      record forecasts now, score them later
  report.py      results/REPORT.md and charts
  cli.py         the `psychohistory` command
tests/           offline tests (synthetic data, no downloads)
```

## Credits

This project stands on other people's work. Full attribution, licences and terms of use are in
[**CREDITS.md**](CREDITS.md). In short:

- **TimesFM** by Google Research: [github.com/google-research/timesfm](https://github.com/google-research/timesfm),
  paper: Das, Kong, Sen, Zhou, *A decoder-only foundation model for time-series forecasting*, ICML 2024
  ([arXiv:2310.10688](https://arxiv.org/abs/2310.10688)).
- **GDELT Project** for world news coverage data.
- **Yahoo Finance** data via the **yfinance** library by Ran Aroussi.
- **Wikimedia Foundation** Pageviews API.
- **Our World in Data** (CC BY 4.0).
- **Isaac Asimov**'s *Foundation* for the idea of psychohistory.

## Licence

Code: [Apache License 2.0](LICENSE). Data and model weights keep their own licences; see
[CREDITS.md](CREDITS.md).
