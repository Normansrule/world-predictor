# References

Open-source projects and modelling ideas this project learns from. Three of the repositories are
used directly in the code (marked **used**); the rest shaped its design, metrics and
presentation, or are natural next models to compare against TimesFM. Licences and terms for
everything that ships or downloads with this project are in [CREDITS.md](CREDITS.md).

## 20 reference repositories

### Time-series foundation models (rivals to TimesFM)

| # | Repository | What it contributes here |
|---|---|---|
| 1 | [amazon-science/chronos-forecasting](https://github.com/amazon-science/chronos-forecasting) | **Used**: `chronos-bolt` and `chronos-2`, run with `--compare`. Amazon's Chronos models, the most common head-to-head rival for TimesFM. |
| 2 | [SalesforceAIResearch/uni2ts](https://github.com/SalesforceAIResearch/uni2ts) | Salesforce's Moirai, a universal any-frequency forecaster. Another candidate for the model table. |
| 3 | [time-series-foundation-models/lag-llama](https://github.com/time-series-foundation-models/lag-llama) | An open probabilistic foundation model built on lagged features. Shows how to report full forecast distributions. |
| 4 | [moment-timeseries-foundation-model/moment](https://github.com/moment-timeseries-foundation-model/moment) | MOMENT, a family of open time-series models for forecasting, anomaly detection and classification. Its anomaly detection points toward spotting "Seldon crises". |
| 5 | [Nixtla/nixtla](https://github.com/Nixtla/nixtla) | The SDK for Nixtla's TimeGPT, a hosted foundation model. A useful commercial comparison point. |

### Forecasting frameworks

| # | Repository | What it contributes here |
|---|---|---|
| 6 | [Nixtla/statsforecast](https://github.com/Nixtla/statsforecast) | **Used**: the `auto-ets` and `auto-arima` baselines. Fast AutoETS and AutoARIMA with prediction intervals, from the tradition of the M-competitions. |
| 7 | [Nixtla/neuralforecast](https://github.com/Nixtla/neuralforecast) | Deep-learning forecasters such as N-BEATS, NHITS and PatchTST. The next tier of baselines between classical models and foundation models. |
| 8 | [facebook/prophet](https://github.com/facebook/prophet) | Meta's decomposable trend-plus-seasonality model. Its plots of forecasts with uncertainty inspired the fan charts. |
| 9 | [unit8co/darts](https://github.com/unit8co/darts) | A single forecasting API over dozens of models with built-in backtesting. A reference for the rolling-origin backtest design. |
| 10 | [sktime/sktime](https://github.com/sktime/sktime) | A scikit-learn-style unified interface for time-series learning. A reference for the small `Forecaster` protocol in `models.py`. |
| 11 | [awslabs/gluonts](https://github.com/awslabs/gluonts) | Amazon's probabilistic forecasting toolkit. Its quantile-based evaluation shaped the decile scoring, and its quantile-averaging ensembles are the model for `--ensemble`. |
| 12 | [statsmodels/statsmodels](https://github.com/statsmodels/statsmodels) | The classical econometrics toolbox (ARIMA, state-space models, unit-root tests) behind the random-walk view of markets. |
| 13 | [bashtage/arch](https://github.com/bashtage/arch) | GARCH and other volatility models. Market *volatility* is far more predictable than direction, which suits a future extension. |

### Benchmarks and scoring

| # | Repository | What it contributes here |
|---|---|---|
| 14 | [SalesforceAIResearch/gift-eval](https://github.com/SalesforceAIResearch/gift-eval) | GIFT-Eval, one of the three benchmarks TimesFM 3.0 reports on. Its use of MASE and CRPS shaped the metric choices. |
| 15 | [autogluon/fev](https://github.com/autogluon/fev) | fev-bench, a lightweight forecasting benchmark library and another of TimesFM 3.0's benchmarks. Its skill-versus-baseline reporting inspired the "skill" score. |
| 16 | [properscoring/properscoring](https://github.com/properscoring/properscoring) | Reference implementations of proper scoring rules (CRPS, Brier). The background for the pinball and Brier metrics. |

### Simulation and theory

| # | Repository | What it contributes here |
|---|---|---|
| 17 | [projectmesa/mesa](https://github.com/projectmesa/mesa) | Agent-based modelling in Python, the closest open-source cousin of psychohistory: simulate many individuals and watch aggregate behaviour emerge. |

### Visuals and presentation

| # | Repository | What it contributes here |
|---|---|---|
| 18 | [plotly/plotly.py](https://github.com/plotly/plotly.py) | **Used**: the interactive `results/dashboard.html`, with hover tooltips and a series picker on the fan chart. |
| 19 | [owid/owid-grapher](https://github.com/owid/owid-grapher) | Our World in Data's chart engine. Its one-question-per-chart layout, plain captions and source lines are the model for the dashboard. |
| 20 | [streamlit/streamlit](https://github.com/streamlit/streamlit) | Python apps for data exploration. The natural next step if the dashboard becomes an interactive app with live re-forecasting. |

## Modelling theories behind the tests

| Theory | Source | Where it shows up |
|---|---|---|
| Psychohistory | Isaac Asimov, *Foundation* (1951) | The whole project: forecast populations, not individuals. |
| Cliodynamics | Peter Turchin, *Historical Dynamics* (2003); the Seshat Global History Databank | The real-world attempt at mathematical history, and the scientific framing for the news domain. |
| Law of large numbers | Jacob Bernoulli, *Ars Conjectandi* (1713) | Test 2: aggregates should be more predictable than individuals. |
| Efficient-market hypothesis | Eugene Fama, "Efficient Capital Markets" (1970) | Why the naive random walk is the right market baseline, and why beating it is hard. |
| Fat tails and black swans | Benoit Mandelbrot (1963); Nassim Taleb, *The Black Swan* (2007) | Test 5, Seldon crises: shocks that fall outside forecast bands. |
| Chaos and limits to predictability | Edward Lorenz, "Deterministic Nonperiodic Flow" (1963) | Test 3, the Seldon horizon: skill should decay as the forecast reaches further ahead. |
| Bass diffusion model | Frank Bass, "A New Product Growth Model" (1969) | **Built in** as the `bass` model: an S-curve fitted to each technology-adoption series and run against TimesFM. |
| Gartner hype cycle | Gartner (1995) | Why attention to a technology (Wikipedia views) spikes and fades even while adoption keeps rising. |
| Proper scoring rules | Glenn Brier (1950); Gneiting and Raftery (2007) | Brier and pinball scores; honest odds (test 4). |
| Superforecasting | Philip Tetlock and Dan Gardner, *Superforecasting* (2015) | Keeping a dated prediction ledger and scoring calibration over time. |
| Forecast accuracy measures | Hyndman and Koehler (2006) | MASE, which makes gold prices and news shares comparable. |
