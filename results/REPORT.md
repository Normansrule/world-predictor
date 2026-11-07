# World Predictor: Seldon scorecard

_Generated 2026-11-07 with model `timesfm-2.5`. Skill = 1 - MAE(model) / MAE(naive random walk); positive is better than naive. Coverage80 should be close to 0.80 for an honest forecaster. Brier scores the probability of going up (0.25 = coin flip, lower is better). See docs/METHODOLOGY.md._

## In plain English

- timesfm-2.5 beat the simple guess "tomorrow looks like today" in 4 of 5 areas: world news (18% less error), politics (22% less error), technology (40% less error), the weather (27% less error).
- Seldon, our own forecaster (crowd laws with timesfm-2.5 as one voter), won 1 of 5 areas (world news) against timesfm-2.5, with lower error on 14 of 53 series and higher on 19. Its crowd laws alone, without timesfm-2.5, won markets: lower error on 10 of 15 series.
- Hari Seldon's bet did not hold here: aggregates were not easier to predict than individual series (16% vs 22% skill).
- In world news, its edge lasts up to about 28 days ahead.
- In politics, its edge lasts up to about 28 days ahead.
- In markets, it had no edge at any distance ahead.
- In technology, its edge lasts up to about 28 days ahead.
- In the weather, its edge lasts up to about 14 days ahead.
- When it gave 70% or more odds of a rise, the rise really happened 83% of the time (124 forecasts).

![Replay of past forecasts against what really happened](plots/replay.gif)

_Each frame is a forecast made in the past: the orange band is what the model expected, the dark dots are what really happened._

## Seldon vs timesfm-2.5: the duel

Seldon is this project's own forecaster (`src/psychohistory/seldon.py`): four laws of crowd behaviour (inertia, drift, momentum, reversion, on top of the weekly rhythm) with TimesFM as one more voter, the laws' share learned per area from finished windows only. It forecasts the same windows as TimesFM and is scored by the same code. A series is won by whichever had the lower average error there; a series where the full Seldon gave TimesFM the whole vote is a tie. Skill is against "no change" (positive is better); range skill scores the whole 80% range (pinball loss).

**The full Seldon** (crowd laws and TimesFM in one council)

| Area | Series | Seldon won | TimesFM won | Seldon's error vs TimesFM | Skill: TimesFM / Seldon | Range skill: TimesFM / Seldon | In 80% range: TimesFM / Seldon | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 15 | 5 | 10 | +1% | -2% / -4% | -0% / -1% | 79% / 79% | timesfm-2.5 |
| World events in the news | 6 | 4 | 2 | -0% | +18% / +17% | +17% / +17% | 75% / 75% | Seldon |
| Political events | 7 | 0 | 0 | +0% | +22% / +22% | +23% / +23% | 79% / 79% | tie |
| New technologies | 16 | 1 | 2 | +4% | +40% / +39% | +34% / +30% | 73% / 71% | timesfm-2.5 |
| Weather and the planet | 9 | 4 | 5 | +2% | +27% / +24% | +27% / +27% | 79% / 79% | timesfm-2.5 |
| **All areas** | 53 | 14 | 19 | +2% | +20% / +18% | +20% / +19% | 76% / 76% | timesfm-2.5 |

**The crowd laws alone** (`seldon-laws`, no TimesFM vote)

| Area | Series | Laws won | TimesFM won | Laws' error vs TimesFM | Skill: TimesFM / Laws | Range skill: TimesFM / Laws | In 80% range: TimesFM / Laws | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 15 | 10 | 5 | -1% | -2% / -1% | -0% / -0% | 79% / 78% | Laws |
| World events in the news | 6 | 1 | 5 | +11% | +18% / +12% | +17% / +11% | 75% / 77% | timesfm-2.5 |
| Political events | 7 | 0 | 7 | +13% | +22% / +15% | +23% / +17% | 79% / 80% | timesfm-2.5 |
| New technologies | 16 | 2 | 14 | +23% | +40% / +23% | +34% / +20% | 73% / 71% | timesfm-2.5 |
| Weather and the planet | 9 | 0 | 9 | +46% | +27% / +8% | +27% / +5% | 79% / 76% | timesfm-2.5 |
| **All areas** | 53 | 13 | 40 | +18% | +20% / +8% | +20% / +10% | 76% / 76% | timesfm-2.5 |

## 1. Can the future be predicted?

![Skill by domain](plots/skill_by_domain.png)

- **World events in the news**: timesfm-2.5 beats the naive baseline (18% less error).
- **Political events**: timesfm-2.5 beats the naive baseline (22% less error).
- **Stock and value markets**: timesfm-2.5 about the same as the naive baseline.
- **New technologies**: timesfm-2.5 beats the naive baseline (40% less error).
- **Weather and the planet**: timesfm-2.5 beats the naive baseline (27% less error).

| domain   | model        |   series |   median_skill |   median_mase |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|---------------:|--------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       15 |         -0.000 |         4.073 |       0.572 |        0.812 |   0.253 |
| markets  | chronos-bolt |       15 |         -0.046 |         4.036 |       0.550 |        0.778 |   0.257 |
| markets  | drift        |       15 |         -0.010 |         3.991 |       0.567 |        0.677 |   0.253 |
| markets  | ensemble     |       15 |         -0.009 |         3.911 |       0.500 |        0.807 |   0.247 |
| markets  | mean         |       15 |         -0.941 |         7.785 |       0.483 |        0.514 |   0.375 |
| markets  | naive        |       15 |          0.000 |         4.032 |     nan     |        0.676 |   0.250 |
| markets  | radiant      |       15 |         -0.022 |         3.994 |       0.517 |        0.779 |   0.250 |
| markets  | radiant-core |       15 |         -0.004 |         4.025 |       0.439 |        0.822 |   0.250 |
| markets  | seldon       |       15 |         -0.035 |         4.029 |       0.506 |        0.790 |   0.249 |
| markets  | seldon-laws  |       15 |         -0.009 |         4.092 |       0.544 |        0.781 |   0.249 |
| markets  | timesfm-2.5  |       15 |         -0.021 |         3.971 |       0.506 |        0.785 |   0.249 |
| news     | auto-ets     |        6 |         -0.021 |         1.653 |       0.639 |        0.880 |   0.233 |
| news     | chronos-bolt |        6 |          0.152 |         1.305 |       0.625 |        0.702 |   0.231 |
| news     | drift        |        6 |         -0.016 |         1.565 |       0.375 |        0.784 |   0.261 |
| news     | ensemble     |        6 |          0.139 |         1.363 |       0.597 |        0.832 |   0.216 |
| news     | mean         |        6 |          0.142 |         1.396 |       0.694 |        0.674 |   0.233 |
| news     | naive        |        6 |          0.000 |         1.555 |     nan     |        0.793 |   0.250 |
| news     | radiant      |        6 |          0.174 |         1.333 |       0.639 |        0.743 |   0.234 |
| news     | radiant-core |        6 |          0.030 |         1.515 |       0.597 |        0.754 |   0.236 |
| news     | seldon       |        6 |          0.174 |         1.337 |       0.639 |        0.747 |   0.226 |
| news     | seldon-laws  |        6 |          0.120 |         1.475 |       0.667 |        0.769 |   0.229 |
| news     | timesfm-2.5  |        6 |          0.179 |         1.330 |       0.639 |        0.745 |   0.233 |
| politics | auto-ets     |        7 |         -0.253 |         2.261 |       0.500 |        0.960 |   0.250 |
| politics | chronos-bolt |        7 |          0.208 |         1.526 |       0.631 |        0.764 |   0.233 |
| politics | drift        |        7 |         -0.007 |         1.798 |       0.393 |        0.778 |   0.259 |
| politics | ensemble     |        7 |          0.096 |         1.489 |       0.619 |        0.923 |   0.231 |
| politics | mean         |        7 |          0.020 |         1.613 |       0.643 |        0.693 |   0.255 |
| politics | naive        |        7 |          0.000 |         1.801 |     nan     |        0.781 |   0.250 |
| politics | radiant      |        7 |          0.220 |         1.504 |       0.619 |        0.793 |   0.227 |
| politics | radiant-core |        7 |          0.024 |         1.705 |       0.631 |        0.821 |   0.237 |
| politics | seldon       |        7 |          0.220 |         1.513 |       0.607 |        0.793 |   0.227 |
| politics | seldon-laws  |        7 |          0.153 |         1.583 |       0.643 |        0.797 |   0.229 |
| politics | timesfm-2.5  |        7 |          0.220 |         1.513 |       0.607 |        0.793 |   0.227 |
| tech     | auto-ets     |       16 |         -0.411 |         2.271 |       0.552 |        0.845 |   0.237 |
| tech     | bass         |        4 |         -1.038 |        60.712 |       0.333 |        0.104 |   0.566 |
| tech     | chronos-bolt |       16 |          0.403 |         0.851 |       0.740 |        0.750 |   0.167 |
| tech     | drift        |       16 |          0.013 |         1.164 |       0.688 |        0.707 |   0.202 |
| tech     | ensemble     |       16 |          0.148 |         1.230 |       0.630 |        0.868 |   0.207 |
| tech     | mean         |       16 |         -0.012 |         1.230 |       0.583 |        0.567 |   0.330 |
| tech     | naive        |       16 |          0.000 |         1.194 |     nan     |        0.707 |   0.282 |
| tech     | radiant      |       16 |          0.394 |         0.849 |       0.802 |        0.741 |   0.145 |
| tech     | radiant-core |       16 |          0.023 |         1.147 |       0.604 |        0.618 |   0.235 |
| tech     | seldon       |       16 |          0.391 |         0.845 |       0.776 |        0.710 |   0.160 |
| tech     | seldon-laws  |       16 |          0.228 |         0.906 |       0.672 |        0.710 |   0.200 |
| tech     | timesfm-2.5  |       16 |          0.404 |         0.845 |       0.776 |        0.728 |   0.160 |
| weather  | auto-ets     |        9 |          0.022 |         2.230 |       0.630 |        0.851 |   0.213 |
| weather  | chronos-bolt |        9 |          0.267 |         1.727 |       0.731 |        0.772 |   0.176 |
| weather  | drift        |        9 |         -0.006 |         2.197 |       0.352 |        0.768 |   0.257 |
| weather  | ensemble     |        9 |          0.233 |         1.784 |       0.750 |        0.870 |   0.161 |
| weather  | mean         |        9 |         -0.338 |         2.791 |       0.537 |        0.531 |   0.374 |
| weather  | naive        |        9 |          0.000 |         2.173 |     nan     |        0.782 |   0.250 |
| weather  | radiant      |        9 |          0.271 |         1.687 |       0.759 |        0.790 |   0.161 |
| weather  | radiant-core |        9 |          0.043 |         2.125 |       0.713 |        0.839 |   0.219 |
| weather  | seldon       |        9 |          0.242 |         1.680 |       0.769 |        0.789 |   0.158 |
| weather  | seldon-laws  |        9 |          0.083 |         2.023 |       0.648 |        0.761 |   0.227 |
| weather  | timesfm-2.5  |        9 |          0.270 |         1.673 |       0.759 |        0.788 |   0.159 |

## 2. Seldon's law of large numbers: aggregates vs individuals

Psychohistory only claims to work for very large populations. If that holds here, aggregate series (indices, composites, world totals) should show higher skill and lower MASE than individual ones.

| domain   | scale      | model       |   series |   median_skill |   median_mase |
|:---------|:-----------|:------------|---------:|---------------:|--------------:|
| markets  | aggregate  | timesfm-2.5 |        5 |         -0.018 |         2.859 |
| markets  | individual | timesfm-2.5 |       10 |         -0.024 |         4.419 |
| news     | aggregate  | timesfm-2.5 |        1 |          0.162 |         1.384 |
| news     | individual | timesfm-2.5 |        5 |          0.196 |         1.276 |
| politics | aggregate  | timesfm-2.5 |        1 |          0.064 |         1.778 |
| politics | individual | timesfm-2.5 |        6 |          0.221 |         1.453 |
| tech     | aggregate  | timesfm-2.5 |        5 |          0.453 |         8.692 |
| tech     | individual | timesfm-2.5 |       11 |          0.331 |         0.793 |
| weather  | aggregate  | timesfm-2.5 |        4 |          0.344 |         1.903 |
| weather  | individual | timesfm-2.5 |        5 |          0.232 |         1.669 |

## 3. Seldon crises: what the model did not see coming

Backtest windows where most actual values fell outside the model's 80% band.

| series_id         | domain   | origin     |   coverage80 |    mase |
|:------------------|:---------|:-----------|-------------:|--------:|
| adoption_solar    | tech     | 2010-01-01 |        0.000 | 155.972 |
| adoption_solar    | tech     | 2007-01-01 |        0.000 | 150.231 |
| adoption_solar    | tech     | 1989-01-01 |        0.000 | 108.537 |
| adoption_wind     | tech     | 1989-01-01 |        0.000 |  87.285 |
| adoption_solar    | tech     | 2013-01-01 |        0.000 |  82.032 |
| adoption_solar    | tech     | 2004-01-01 |        0.000 |  70.178 |
| space_launches    | tech     | 2019-01-01 |        0.000 |  56.721 |
| space_launches    | tech     | 2016-01-01 |        0.000 |  16.455 |
| weather_world_air | weather  | 2026-09-04 |        0.000 |   4.982 |
| space_launches    | tech     | 2013-01-01 |        0.000 |   3.874 |
| tlt               | markets  | 2026-03-09 |        0.000 |   3.775 |
| bitcoin           | markets  | 2026-01-29 |        0.036 |  12.359 |
| wiki_ai           | tech     | 2026-09-09 |        0.036 |   4.728 |
| xom               | markets  | 2026-07-09 |        0.048 |  11.375 |
| us10y             | markets  | 2026-09-08 |        0.048 |   6.485 |

## 4. Prediction ledger (true out-of-sample test)

![Time Vault track record](plots/track_record.png)

_Predictions are sealed with a date before the future happens and opened when it arrives. The left line should settle near 80%; the right line should sit below the coin-flip line._

| domain   | model        |   series |   predictions |   median_skill |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|--------------:|---------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       15 |           851 |         -0.008 |       0.493 |        0.755 |   0.258 |
| markets  | chronos-bolt |       15 |           851 |         -0.093 |       0.404 |        0.718 |   0.287 |
| markets  | ensemble     |       15 |           851 |         -0.032 |       0.392 |        0.735 |   0.265 |
| markets  | radiant      |       15 |           120 |         -0.027 |       0.426 |        0.516 |   0.262 |
| markets  | radiant-core |       15 |           120 |         -0.000 |       0.537 |        0.577 |   0.250 |
| markets  | seldon       |       15 |           120 |         -0.036 |       0.435 |        0.567 |   0.270 |
| markets  | seldon-laws  |       15 |           488 |         -0.040 |       0.375 |        0.651 |   0.266 |
| markets  | timesfm-2.5  |       15 |           851 |         -0.032 |       0.483 |        0.728 |   0.263 |
| news     | auto-ets     |        6 |           336 |          0.023 |       0.539 |        0.737 |   0.251 |
| news     | chronos-bolt |        6 |           336 |          0.044 |       0.611 |        0.562 |   0.258 |
| news     | ensemble     |        6 |           336 |          0.047 |       0.620 |        0.672 |   0.243 |
| news     | radiant      |        6 |            60 |         -0.110 |       0.583 |        0.467 |   0.297 |
| news     | radiant-core |        6 |            60 |          0.005 |       0.550 |        0.533 |   0.247 |
| news     | seldon       |        6 |            60 |         -0.109 |       0.583 |        0.467 |   0.298 |
| news     | seldon-laws  |        6 |           216 |          0.055 |       0.618 |        0.500 |   0.248 |
| news     | timesfm-2.5  |        6 |           336 |          0.007 |       0.584 |        0.543 |   0.284 |
| politics | auto-ets     |        6 |             6 |         -0.026 |       0.333 |        0.333 |   0.324 |
| politics | chronos-bolt |        6 |             6 |         -0.209 |       0.167 |        0.333 |   0.452 |
| politics | ensemble     |        6 |             6 |         -0.096 |       0.167 |        0.333 |   0.390 |
| politics | radiant      |        6 |             6 |         -0.141 |       0.333 |        0.333 |   0.397 |
| politics | radiant-core |        6 |             6 |         -0.000 |       0.400 |        0.333 |   0.250 |
| politics | seldon       |        6 |             6 |         -0.172 |       0.333 |        0.333 |   0.435 |
| politics | seldon-laws  |        6 |             6 |         -0.042 |       0.333 |        0.333 |   0.354 |
| politics | timesfm-2.5  |        6 |             6 |         -0.172 |       0.333 |        0.333 |   0.435 |
| tech     | auto-ets     |       12 |           652 |          0.085 |       0.638 |        0.968 |   0.226 |
| tech     | chronos-bolt |       12 |           652 |          0.398 |       0.848 |        0.765 |   0.111 |
| tech     | ensemble     |       12 |           652 |          0.313 |       0.821 |        0.959 |   0.132 |
| tech     | radiant      |       12 |            60 |          0.458 |       0.857 |        0.857 |   0.106 |
| tech     | radiant-core |       12 |            60 |          0.017 |       0.845 |        0.560 |   0.242 |
| tech     | seldon       |       12 |            60 |          0.457 |       0.857 |        0.857 |   0.105 |
| tech     | seldon-laws  |       12 |           340 |          0.132 |       0.764 |        0.718 |   0.169 |
| tech     | timesfm-2.5  |       12 |           652 |          0.375 |       0.862 |        0.740 |   0.113 |
| weather  | auto-ets     |        9 |             9 |          0.062 |       0.714 |        0.778 |   0.229 |
| weather  | chronos-bolt |        9 |             9 |         -0.570 |       0.714 |        0.667 |   0.252 |
| weather  | ensemble     |        9 |             9 |         -0.164 |       0.714 |        0.889 |   0.231 |
| weather  | radiant      |        9 |             9 |         -0.080 |       0.714 |        0.889 |   0.221 |
| weather  | radiant-core |        9 |             9 |          0.037 |       0.857 |        0.889 |   0.234 |
| weather  | seldon       |        9 |             9 |          0.079 |       0.571 |        0.889 |   0.235 |
| weather  | seldon-laws  |        9 |             9 |          0.207 |       1.000 |        0.889 |   0.221 |
| weather  | timesfm-2.5  |        9 |             9 |          0.079 |       0.571 |        0.889 |   0.235 |

## 5. How far ahead can it see?

Median skill versus the naive baseline by how many steps ahead the forecast is (days for news and tech attention, trading days for markets; yearly adoption series are too short for this and are left out). Where skill drops to zero is the limit of the model's foresight in that domain.

![Skill by step](plots/skill_by_step.png)

| domain   |   1 step |    2-5 |   6-10 |   11-20 |     21+ |
|:---------|---------:|-------:|-------:|--------:|--------:|
| markets  |   -0.043 | -0.032 | -0.018 |  -0.018 |  -0.046 |
| news     |    0.254 |  0.304 |  0.109 |   0.188 |   0.132 |
| politics |    0.219 |  0.240 |  0.200 |   0.201 |   0.155 |
| tech     |   -0.085 |  0.478 |  0.205 |   0.240 |   0.335 |
| weather  |    0.200 |  0.214 |  0.184 |   0.282 | nan     |

## 6. Are its odds honest?

Backtest forecasts grouped by the chance they gave of the series ending higher. `said` is the average probability given, `happened` is how often it really went up. When the two match, the odds can be taken at face value.

| domain   | odds given   |   forecasts |   said |   happened |
|:---------|:-------------|------------:|-------:|-----------:|
| markets  | 20%-40%      |          15 |  0.369 |      0.533 |
| markets  | 40%-60%      |         136 |  0.488 |      0.522 |
| markets  | 60%-80%      |          29 |  0.661 |      0.724 |
| news     | 0%-20%       |           8 |  0.128 |      0.375 |
| news     | 20%-40%      |          25 |  0.312 |      0.520 |
| news     | 40%-60%      |          16 |  0.501 |      0.562 |
| news     | 60%-80%      |          16 |  0.684 |      0.750 |
| news     | 80%-100%     |           7 |  0.866 |      1.000 |
| politics | 0%-20%       |          14 |  0.139 |      0.214 |
| politics | 20%-40%      |          23 |  0.295 |      0.435 |
| politics | 40%-60%      |          13 |  0.480 |      0.462 |
| politics | 60%-80%      |          27 |  0.696 |      0.593 |
| politics | 80%-100%     |           7 |  0.839 |      0.857 |
| tech     | 0%-20%       |          30 |  0.121 |      0.200 |
| tech     | 20%-40%      |          38 |  0.298 |      0.184 |
| tech     | 40%-60%      |          42 |  0.489 |      0.381 |
| tech     | 60%-80%      |          39 |  0.689 |      0.718 |
| tech     | 80%-100%     |          32 |  0.915 |      0.938 |
| weather  | 0%-20%       |          41 |  0.095 |      0.122 |
| weather  | 20%-40%      |          16 |  0.301 |      0.438 |
| weather  | 40%-60%      |          16 |  0.481 |      0.562 |
| weather  | 60%-80%      |          11 |  0.708 |      0.545 |
| weather  | 80%-100%     |          24 |  0.905 |      0.917 |

## 7. Every series

| series_id            | domain   | scale      | model       |      mae |   mase |   smape |   direction |   coverage80 |   pinball |   brier |   skill |   prob_skill |
|:---------------------|:---------|:-----------|:------------|---------:|-------:|--------:|------------:|-------------:|----------:|--------:|--------:|-------------:|
| aapl                 | markets  | individual | timesfm-2.5 |    9.414 |  3.971 |   0.032 |       0.667 |        0.841 |     1.500 |   0.244 |   0.025 |        0.030 |
| adoption_internet    | tech     | aggregate  | timesfm-2.5 |    2.341 |  0.774 |   0.032 |       1.000 |        1.000 |     0.260 |   0.002 |   0.460 |        0.526 |
| adoption_solar       | tech     | aggregate  | timesfm-2.5 |    0.254 | 64.139 |   0.421 |       0.750 |        0.417 |    27.337 |   0.197 |   0.441 |        0.282 |
| adoption_wind        | tech     | aggregate  | timesfm-2.5 |    0.165 | 31.187 |   0.249 |       0.833 |        0.694 |    12.482 |   0.124 |   0.646 |        0.416 |
| bitcoin              | markets  | individual | timesfm-2.5 | 5179.797 |  4.105 |   0.070 |       0.500 |        0.801 |     1.734 |   0.264 |  -0.021 |       -0.019 |
| copper               | markets  | individual | timesfm-2.5 |    0.166 |  3.101 |   0.028 |       0.500 |        0.901 |     1.275 |   0.249 |  -0.021 |       -0.084 |
| gold                 | markets  | individual | timesfm-2.5 |  171.694 |  7.599 |   0.038 |       0.750 |        0.889 |     2.905 |   0.245 |   0.016 |        0.123 |
| msci_world           | markets  | aggregate  | timesfm-2.5 |    2.810 |  2.876 |   0.015 |       0.667 |        0.786 |     1.148 |   0.204 |  -0.032 |       -0.014 |
| nasdaq100            | markets  | aggregate  | timesfm-2.5 |  798.449 |  4.426 |   0.029 |       0.500 |        0.722 |     1.810 |   0.226 |  -0.018 |       -0.001 |
| news_climate         | news     | individual | timesfm-2.5 |    0.134 |  1.019 |   0.161 |       0.583 |        0.807 |     0.399 |   0.245 |   0.100 |        0.110 |
| news_composite       | news     | aggregate  | timesfm-2.5 |    0.077 |  1.384 |   0.093 |       0.667 |        0.756 |     0.553 |   0.201 |   0.162 |        0.144 |
| news_election        | news     | individual | timesfm-2.5 |    0.630 |  1.276 |   0.131 |       0.667 |        0.818 |     0.538 |   0.215 |   0.129 |        0.117 |
| news_inflation       | news     | individual | timesfm-2.5 |    0.316 |  1.036 |   0.161 |       0.667 |        0.723 |     0.412 |   0.232 |   0.196 |        0.206 |
| news_pandemic        | news     | individual | timesfm-2.5 |    0.267 |  1.447 |   0.133 |       0.583 |        0.673 |     0.599 |   0.214 |   0.197 |        0.190 |
| news_protest         | news     | individual | timesfm-2.5 |    0.556 |  1.890 |   0.231 |       0.667 |        0.693 |     0.776 |   0.289 |   0.393 |        0.415 |
| nvda                 | markets  | individual | timesfm-2.5 |   10.208 |  5.188 |   0.051 |       0.500 |        0.782 |     2.043 |   0.270 |  -0.034 |        0.018 |
| oil_wti              | markets  | individual | timesfm-2.5 |    6.753 |  4.734 |   0.082 |       0.500 |        0.710 |     1.878 |   0.248 |  -0.061 |       -0.012 |
| politics_ceasefire   | politics | individual | timesfm-2.5 |    0.393 |  1.987 |   0.382 |       0.583 |        0.807 |     0.847 |   0.272 |   0.133 |        0.130 |
| politics_composite   | politics | aggregate  | timesfm-2.5 |    0.243 |  1.778 |   0.191 |       0.500 |        0.801 |     0.733 |   0.287 |   0.064 |        0.086 |
| politics_coup        | politics | individual | timesfm-2.5 |    0.091 |  0.868 |   0.231 |       0.667 |        0.723 |     0.351 |   0.152 |   0.465 |        0.473 |
| politics_impeachment | politics | individual | timesfm-2.5 |    0.060 |  0.745 |   0.250 |       0.583 |        0.839 |     0.304 |   0.257 |   0.220 |        0.227 |
| politics_referendum  | politics | individual | timesfm-2.5 |    0.118 |  1.513 |   0.293 |       0.583 |        0.771 |     0.622 |   0.216 |   0.081 |        0.074 |
| politics_sanctions   | politics | individual | timesfm-2.5 |    0.262 |  1.583 |   0.208 |       0.833 |        0.812 |     0.613 |   0.148 |   0.260 |        0.286 |
| politics_tariffs     | politics | individual | timesfm-2.5 |    0.321 |  1.392 |   0.228 |       0.500 |        0.795 |     0.564 |   0.258 |   0.222 |        0.254 |
| quakes_m45           | weather  | aggregate  | timesfm-2.5 |    7.725 |  0.955 |   0.319 |       0.667 |        0.732 |     0.386 |   0.207 |   0.279 |        0.273 |
| silver               | markets  | individual | timesfm-2.5 |    6.045 | 11.221 |   0.087 |       0.333 |        0.833 |     4.297 |   0.260 |  -0.028 |        0.122 |
| sp500                | markets  | aggregate  | timesfm-2.5 |  108.360 |  2.859 |   0.015 |       0.500 |        0.798 |     1.178 |   0.229 |   0.008 |       -0.000 |
| space_launches       | tech     | aggregate  | timesfm-2.5 |  218.395 |  8.692 |   0.333 |       0.250 |        0.556 |     3.938 |   0.353 |   0.026 |        0.045 |
| tech_composite       | tech     | aggregate  | timesfm-2.5 |    0.067 |  0.656 |   0.082 |       0.833 |        0.732 |     0.264 |   0.131 |   0.453 |        0.442 |
| tlt                  | markets  | individual | timesfm-2.5 |    1.376 |  2.039 |   0.016 |       0.333 |        0.690 |     0.804 |   0.292 |  -0.041 |        0.032 |
| tsla                 | markets  | individual | timesfm-2.5 |   21.573 |  2.874 |   0.056 |       0.667 |        0.865 |     1.213 |   0.249 |  -0.011 |       -0.058 |
| us10y                | markets  | aggregate  | timesfm-2.5 |    0.122 |  2.471 |   0.027 |       0.167 |        0.722 |     0.966 |   0.306 |  -0.086 |       -0.038 |
| vix                  | markets  | aggregate  | timesfm-2.5 |    1.972 |  1.884 |   0.106 |       0.667 |        0.853 |     0.737 |   0.180 |   0.027 |        0.046 |
| weather_arctic_ice   | weather  | aggregate  | timesfm-2.5 |    0.126 |  1.788 |   0.019 |       1.000 |        0.815 |     0.691 |   0.005 |   0.735 |        0.710 |
| weather_london       | weather  | individual | timesfm-2.5 |    3.434 |  1.805 |   0.149 |       0.667 |        0.768 |     0.698 |   0.233 |   0.077 |        0.119 |
| weather_los_angeles  | weather  | individual | timesfm-2.5 |    2.907 |  1.673 |   0.097 |       0.750 |        0.774 |     0.653 |   0.169 |   0.329 |        0.329 |
| weather_new_delhi    | weather  | individual | timesfm-2.5 |    2.033 |  1.669 |   0.060 |       0.750 |        0.810 |     0.659 |   0.124 |   0.232 |        0.251 |
| weather_sydney       | weather  | individual | timesfm-2.5 |    2.333 |  1.016 |   0.112 |       0.417 |        0.815 |     0.388 |   0.342 |   0.270 |        0.297 |
| weather_tokyo        | weather  | individual | timesfm-2.5 |    3.394 |  1.505 |   0.125 |       0.750 |        0.685 |     0.576 |   0.193 |   0.158 |        0.160 |
| weather_world_air    | weather  | aggregate  | timesfm-2.5 |    0.081 |  2.019 |   0.005 |       1.000 |        0.810 |     0.795 |   0.027 |   0.409 |        0.415 |
| weather_world_sea    | weather  | aggregate  | timesfm-2.5 |    0.018 |  2.708 |   0.001 |       0.833 |        0.887 |     1.073 |   0.134 |   0.184 |        0.221 |
| wiki_ai              | tech     | individual | timesfm-2.5 | 1589.349 |  1.176 |   0.118 |       0.833 |        0.768 |     0.488 |   0.177 |   0.328 |        0.281 |
| wiki_battery         | tech     | individual | timesfm-2.5 |  181.862 |  1.261 |   0.228 |       0.583 |        0.759 |     0.542 |   0.276 |   0.296 |        0.298 |
| wiki_crispr          | tech     | individual | timesfm-2.5 |   90.381 |  0.598 |   0.115 |       0.917 |        0.717 |     0.242 |   0.079 |   0.488 |        0.479 |
| wiki_ev              | tech     | individual | timesfm-2.5 |   40.800 |  0.449 |   0.094 |       0.833 |        0.824 |     0.181 |   0.130 |   0.562 |        0.530 |
| wiki_fusion          | tech     | individual | timesfm-2.5 |   92.887 |  0.793 |   0.121 |       0.750 |        0.732 |     0.333 |   0.197 |   0.253 |        0.212 |
| wiki_gene_therapy    | tech     | individual | timesfm-2.5 |   27.576 |  0.481 |   0.148 |       0.750 |        0.759 |     0.191 |   0.165 |   0.367 |        0.373 |
| wiki_humanoid        | tech     | individual | timesfm-2.5 |   59.980 |  1.014 |   0.165 |       1.000 |        0.690 |     0.419 |   0.076 |   0.331 |        0.300 |
| wiki_llm             | tech     | individual | timesfm-2.5 |  317.133 |  0.581 |   0.094 |       1.000 |        0.771 |     0.228 |   0.074 |   0.513 |        0.520 |
| wiki_quantum         | tech     | individual | timesfm-2.5 |  352.078 |  0.897 |   0.127 |       0.833 |        0.753 |     0.397 |   0.154 |   0.220 |        0.198 |
| wiki_self_driving    | tech     | individual | timesfm-2.5 |   56.490 |  0.533 |   0.114 |       0.667 |        0.735 |     0.213 |   0.174 |   0.479 |        0.478 |
| wiki_starship        | tech     | individual | timesfm-2.5 |  858.681 |  0.917 |   0.274 |       0.583 |        0.735 |     0.411 |   0.249 |   0.075 |        0.059 |
| xom                  | markets  | individual | timesfm-2.5 |    8.218 |  6.550 |   0.056 |       0.333 |        0.583 |     2.578 |   0.266 |  -0.031 |        0.022 |

## 8. What the model expects next

![What the model expects next](plots/outlook.png)

Latest forecasts recorded in the ledger (made with data up to each series' last date). Changes are relative to the last observed value; the range is the 10%-90% band; "chance higher" is the model's probability that the value on the target date is above today's (scored later with the Brier score: 0 is perfect, 0.25 is a coin flip).

### World events in the news

| series         |   last | target date   | median   | chance higher   | range (10%-90%)   |
|:---------------|-------:|:--------------|:---------|:----------------|:------------------|
| news_climate   |  0.569 | 2026-12-04    | +32.6%   | 85%             | -6.0% to +93.0%   |
| news_composite |  1.054 | 2026-12-04    | -12.8%   | 20%             | -25.6% to +9.4%   |
| news_election  |  9.571 | 2026-12-04    | -39.9%   | 5%              | -56.1% to -4.6%   |
| news_inflation |  2.326 | 2026-12-04    | -13.2%   | 26%             | -32.9% to +17.2%  |
| news_pandemic  |  1.871 | 2026-12-04    | -10.5%   | 22%             | -24.6% to +9.5%   |
| news_protest   |  2.39  | 2026-12-04    | -21.7%   | 20%             | -39.4% to +19.1%  |

![news_climate](plots/news_climate.png)
![news_composite](plots/news_composite.png)
![news_election](plots/news_election.png)
![news_inflation](plots/news_inflation.png)
![news_pandemic](plots/news_pandemic.png)
![news_protest](plots/news_protest.png)

### Political events

| series               |   last | target date   | median   | chance higher   | range (10%-90%)   |
|:---------------------|-------:|:--------------|:---------|:----------------|:------------------|
| politics_ceasefire   |  1.138 | 2026-12-04    | -55.0%   | 5%              | -77.3% to -1.4%   |
| politics_composite   |  1.864 | 2026-12-04    | -44.6%   | 5%              | -58.6% to -12.2%  |
| politics_coup        |  0.379 | 2026-12-04    | -26.8%   | 19%             | -44.9% to +21.4%  |
| politics_impeachment |  1.142 | 2026-12-04    | -78.1%   | 5%              | -86.2% to -55.3%  |
| politics_sanctions   |  1.087 | 2026-12-04    | +5.1%    | 57%             | -24.2% to +56.4%  |
| politics_tariffs     |  1.618 | 2026-12-04    | -31.3%   | 19%             | -54.2% to +23.1%  |

![politics_ceasefire](plots/politics_ceasefire.png)
![politics_composite](plots/politics_composite.png)
![politics_coup](plots/politics_coup.png)
![politics_impeachment](plots/politics_impeachment.png)
![politics_sanctions](plots/politics_sanctions.png)
![politics_tariffs](plots/politics_tariffs.png)

### Stock and value markets

| series     |      last | target date   | median   | chance higher   | range (10%-90%)   |
|:-----------|----------:|:--------------|:---------|:----------------|:------------------|
| aapl       |   344.17  | 2026-12-04    | +0.7%    | 55%             | -7.1% to +6.4%    |
| bitcoin    | 76014.2   | 2026-12-04    | -0.8%    | 47%             | -17.0% to +16.5%  |
| copper     |     6.287 | 2026-12-04    | -0.1%    | 50%             | -9.1% to +6.1%    |
| gold       |  4080.6   | 2026-12-04    | +0.4%    | 53%             | -6.7% to +9.7%    |
| msci_world |   199.63  | 2026-12-04    | +4.5%    | 95%             | +0.4% to +7.4%    |
| nasdaq100  | 26629.8   | 2026-12-04    | +5.0%    | 71%             | -7.4% to +14.4%   |
| nvda       |   181.6   | 2026-12-04    | +3.6%    | 60%             | -16.1% to +20.7%  |
| oil_wti    |    91.66  | 2026-12-04    | -1.1%    | 46%             | -16.9% to +14.7%  |
| silver     |    52.1   | 2026-12-04    | -0.7%    | 47%             | -12.9% to +15.7%  |
| sp500      |  7353.73  | 2026-12-04    | +4.3%    | 84%             | -1.4% to +7.9%    |
| tlt        |    81.93  | 2026-12-04    | +1.2%    | 71%             | -1.7% to +3.8%    |
| tsla       |   343.69  | 2026-12-04    | +1.2%    | 53%             | -21.9% to +21.6%  |
| us10y      |     4.837 | 2026-12-04    | -0.7%    | 43%             | -5.7% to +4.4%    |
| vix        |    28.18  | 2026-12-04    | -36.0%   | 5%              | -48.5% to -9.6%   |
| xom        |   165.3   | 2026-12-04    | -0.8%    | 46%             | -13.2% to +11.2%  |

![aapl](plots/aapl.png)
![bitcoin](plots/bitcoin.png)
![copper](plots/copper.png)
![gold](plots/gold.png)
![msci_world](plots/msci_world.png)
![nasdaq100](plots/nasdaq100.png)
![nvda](plots/nvda.png)
![oil_wti](plots/oil_wti.png)
![silver](plots/silver.png)
![sp500](plots/sp500.png)
![tlt](plots/tlt.png)
![tsla](plots/tsla.png)
![us10y](plots/us10y.png)
![vix](plots/vix.png)
![xom](plots/xom.png)

### New technologies

| series            |      last | target date   | median   | chance higher   | range (10%-90%)   |
|:------------------|----------:|:--------------|:---------|:----------------|:------------------|
| adoption_ev       |    25     | 2028-01-01    | +11.9%   | 71%             | -20.4% to +38.9%  |
| adoption_internet |    73.6   | 2028-01-01    | +5.8%    | 79%             | -2.9% to +19.5%   |
| adoption_solar    |     8.745 | 2028-01-01    | +49.5%   | 95%             | +15.3% to +94.2%  |
| adoption_wind     |     8.539 | 2028-01-01    | +6.9%    | 73%             | -9.3% to +22.4%   |
| space_launches    |  4510     | 2028-01-01    | -37.8%   | 11%             | -68.1% to +1.7%   |
| tech_composite    |     0.679 | 2026-12-02    | +8.7%    | 79%             | -5.4% to +28.4%   |
| wiki_ai           | 16372     | 2026-12-02    | -8.7%    | 29%             | -27.1% to +16.6%  |
| wiki_battery      |   268     | 2026-12-02    | +28.8%   | 84%             | -7.6% to +94.5%   |
| wiki_crispr       |   624     | 2026-12-02    | +17.8%   | 87%             | -2.4% to +44.0%   |
| wiki_ev           |   333     | 2026-12-02    | +19.6%   | 89%             | -0.9% to +48.6%   |
| wiki_fusion       |   495     | 2026-12-02    | +19.9%   | 86%             | -2.8% to +56.9%   |
| wiki_gene_therapy |   166     | 2026-12-02    | -2.6%    | 43%             | -23.5% to +28.2%  |
| wiki_humanoid     |   275     | 2026-12-02    | +3.3%    | 57%             | -16.8% to +38.6%  |
| wiki_llm          |  3022     | 2026-12-02    | +5.8%    | 69%             | -8.8% to +24.3%   |
| wiki_quantum      |  1443     | 2026-12-02    | +13.8%   | 79%             | -7.7% to +48.5%   |
| wiki_self_driving |   342     | 2026-12-02    | +15.6%   | 80%             | -8.4% to +46.0%   |
| wiki_starship     |  1168     | 2026-12-02    | +22.1%   | 85%             | -5.0% to +123.0%  |

![adoption_ev](plots/adoption_ev.png)
![adoption_internet](plots/adoption_internet.png)
![adoption_solar](plots/adoption_solar.png)
![adoption_wind](plots/adoption_wind.png)
![space_launches](plots/space_launches.png)
![tech_composite](plots/tech_composite.png)
![wiki_ai](plots/wiki_ai.png)
![wiki_battery](plots/wiki_battery.png)
![wiki_crispr](plots/wiki_crispr.png)
![wiki_ev](plots/wiki_ev.png)
![wiki_fusion](plots/wiki_fusion.png)
![wiki_gene_therapy](plots/wiki_gene_therapy.png)
![wiki_humanoid](plots/wiki_humanoid.png)
![wiki_llm](plots/wiki_llm.png)
![wiki_quantum](plots/wiki_quantum.png)
![wiki_self_driving](plots/wiki_self_driving.png)
![wiki_starship](plots/wiki_starship.png)

### Weather and the planet

| series              |   last | target date   | median   | chance higher   | range (10%-90%)   |
|:--------------------|-------:|:--------------|:---------|:----------------|:------------------|
| quakes_m45          |  8     | 2026-11-19    | +86.0%   | 95%             | +2.7% to +236.4%  |
| weather_arctic_ice  |  8.241 | 2026-11-18    | +13.6%   | 95%             | +9.8% to +17.2%   |
| weather_london      | 10     | 2026-11-19    | +10.7%   | 64%             | -24.4% to +53.0%  |
| weather_los_angeles | 26.5   | 2026-11-19    | -13.1%   | 20%             | -30.6% to +7.0%   |
| weather_new_delhi   | 28.6   | 2026-11-19    | -10.8%   | 5%              | -22.2% to -1.9%   |
| weather_sydney      | 21     | 2026-11-19    | +19.9%   | 84%             | -4.5% to +55.5%   |
| weather_tokyo       | 19.5   | 2026-11-19    | -19.9%   | 14%             | -44.1% to +3.3%   |
| weather_world_air   | 14.995 | 2026-11-13    | -4.0%    | 5%              | -5.8% to -2.5%    |
| weather_world_sea   | 21.033 | 2026-11-03    | -0.2%    | 5%              | -0.5% to -0.0%    |

![quakes_m45](plots/quakes_m45.png)
![weather_arctic_ice](plots/weather_arctic_ice.png)
![weather_london](plots/weather_london.png)
![weather_los_angeles](plots/weather_los_angeles.png)
![weather_new_delhi](plots/weather_new_delhi.png)
![weather_sydney](plots/weather_sydney.png)
![weather_tokyo](plots/weather_tokyo.png)
![weather_world_air](plots/weather_world_air.png)
![weather_world_sea](plots/weather_world_sea.png)

## 9. The long-term monitor

Every sealed forecast that has come due, scored against what really happened. Unlike the backtest, none of these could have been fitted to the outcome. Run `psychohistory monitor` for the same in the terminal; the app's Monitor view draws it month by month.

| Model | Forecasts | Weekly batches | Skill vs "no change" | In 80% range | Right direction | Brier |
|---|---|---|---|---|---|---|
| auto-ets | 1854 | 9 | -0.0% | 83% | 51% | 0.248 |
| chronos-bolt | 1854 | 9 | -5.2% | 67% | 57% | 0.233 |
| ensemble | 1854 | 9 | -2.2% | 80% | 55% | 0.223 |
| radiant | 255 | 3 | -0.3% | 58% | 56% | 0.239 |
| radiant-core | 255 | 3 | +0.5% | 55% | 61% | 0.246 |
| seldon | 255 | 3 | +1.1% | 60% | 56% | 0.244 |
| seldon-laws | 1059 | 7 | +2.3% | 63% | 55% | 0.221 |
| timesfm-2.5 | 1854 | 9 | +1.7% | 66% | 59% | 0.226 |

**Is timesfm-2.5 really better than "no change"?** A Diebold-Mariano test on the weekly batches (Newey-West variance, as the batches' horizons overlap, with the Harvey-Leybourne-Newbold small-sample correction and Student's t):

- All areas: not distinguishable from no change (p = 0.06)
- Stock and value markets: worse than no change (p = 0.05)
- World events in the news: not distinguishable from no change (p = 0.33)
- Political events: too early: 1 of 4 weekly batches
- New technologies: not distinguishable from no change (p = 0.06)
- Weather and the planet: too early: 1 of 4 weekly batches

**Drift alarms** (forecasts due in the last 13 weeks): 48 raised. Every forecaster is tested on every series at once, so alarms must pass a Benjamini-Hochberg false-discovery cut of 5%.
- auto-ets on silver: edge lost
- chronos-bolt on news_election: edge lost
- chronos-bolt on news_inflation: edge lost
- chronos-bolt on xom: edge lost
- ensemble on aapl: edge lost
- ensemble on news_election: edge lost
- ensemble on wiki_humanoid: edge lost
- seldon-laws on news_climate: edge lost
- seldon-laws on news_inflation: edge lost
- timesfm-2.5 on aapl: edge lost
- timesfm-2.5 on news_climate: edge lost
- timesfm-2.5 on news_election: edge lost
- timesfm-2.5 on news_inflation: edge lost
- timesfm-2.5 on wiki_ev: edge lost
- auto-ets on bitcoin: range too wide
- auto-ets on msci_world: worse than no change
- auto-ets on wiki_ai: range too wide
- auto-ets on wiki_ev: range too wide
- auto-ets on wiki_fusion: range too wide
- auto-ets on wiki_humanoid: range too wide
- auto-ets on wiki_llm: range too wide
- chronos-bolt on gold: worse than no change
- chronos-bolt on news_climate: range too narrow
- chronos-bolt on news_composite: range too narrow
- chronos-bolt on news_election: range too narrow
- chronos-bolt on news_election: worse than no change
- chronos-bolt on news_pandemic: range too narrow
- chronos-bolt on wiki_ai: range too wide
- chronos-bolt on wiki_llm: range too narrow
- ensemble on msci_world: worse than no change
- ensemble on news_election: range too narrow
- ensemble on tech_composite: range too wide
- ensemble on wiki_ai: range too wide
- ensemble on wiki_crispr: range too wide
- ensemble on wiki_fusion: range too wide
- ensemble on wiki_humanoid: range too wide
- ensemble on wiki_llm: range too wide
- seldon-laws on msci_world: worse than no change
- seldon-laws on news_composite: range too narrow
- seldon-laws on news_election: range too narrow
- seldon-laws on news_protest: range too narrow
- timesfm-2.5 on bitcoin: range too wide
- timesfm-2.5 on msci_world: worse than no change
- timesfm-2.5 on news_composite: range too narrow
- timesfm-2.5 on news_election: range too narrow
- timesfm-2.5 on news_election: worse than no change
- timesfm-2.5 on news_inflation: range too narrow
- timesfm-2.5 on wiki_llm: range too narrow

## 10. Volatility forecasts

Each market's volatility over the next week and month, forecast at every weekly origin from 2005-12-29 to 2026-10-29 and scored with QLIKE against the volatility that followed. Skill is against last month's volatility carried forward, on the same windows; p is a Diebold-Mariano test.

| Forecaster | Ahead | Windows | Skill | Beat it in | Typical miss | p |
|---|---|---|---|---|---|---|
| timesfm-2.5 | 1 week | 168 | +22.3% | 9 of 14 markets | 25% | 0.206 |
| seldon | 1 week | 168 | +19.7% | 9 of 14 markets | 26% | 0.253 |
| garch | 1 week | 13952 | +17.4% | 14 of 14 markets | 32% | 0.000 |
| radiant | 1 week | 168 | +14.3% | 6 of 14 markets | 27% | 0.293 |
| chronos-bolt | 1 week | 168 | +12.8% | 8 of 14 markets | 29% | 0.407 |
| ewma | 1 week | 13952 | +11.4% | 14 of 14 markets | 31% | 0.000 |
| last-month | 1 week | 13952 | baseline |  | 31% |  |
| seldon-laws | 1 week | 168 | -5.4% | 5 of 14 markets | 35% | 0.631 |
| radiant-core | 1 week | 168 | -19.3% | 5 of 14 markets | 39% | 0.425 |
| garch | 1 month | 13901 | +29.9% | 13 of 14 markets | 24% | 0.000 |
| ewma | 1 month | 13901 | +17.4% | 14 of 14 markets | 22% | 0.000 |
| last-month | 1 month | 13901 | baseline |  | 23% |  |
| seldon | 1 month | 168 | -58.3% | 7 of 14 markets | 25% | 0.292 |
| radiant | 1 month | 168 | -60.8% | 5 of 14 markets | 24% | 0.401 |
| timesfm-2.5 | 1 month | 168 | -61.0% | 7 of 14 markets | 25% | 0.132 |
| chronos-bolt | 1 month | 168 | -75.0% | 7 of 14 markets | 21% | 0.040 |
| radiant-core | 1 month | 168 | -90.9% | 7 of 14 markets | 29% | 0.676 |
| seldon-laws | 1 month | 168 | -93.2% | 3 of 14 markets | 27% | 0.599 |

Sealed volatility forecasts are in `predictions/vol_ledger.csv`, fingerprinted in `predictions/vol_seals.csv` and scored in `predictions/vol_scored.csv`.

## 11. Event odds

The chance that a news or technology series reaches, four weeks ahead, a level it reaches only one day in ten (a spike: above the 90th percentile of its last two years) or falls to a low it sees one day in ten (a lull). Odds are scored with the Brier score; skill is against climatology (10%) and against persistence (what followed days like the origin), on the same forecasts. p is a Diebold-Mariano test of the edge over climatology.

| Event | Forecaster | Forecasts | Happened | Said | Brier | vs climatology | vs persistence | p |
|---|---|---|---|---|---|---|---|---|
| lull | seldon | 300 | 23% | 20% | 0.1404 | +26.6% | +23.5% | 0.004 |
| lull | timesfm-2.5 | 300 | 23% | 20% | 0.1406 | +26.6% | +23.5% | 0.004 |
| lull | radiant | 300 | 23% | 19% | 0.1461 | +23.7% | +20.5% | 0.004 |
| lull | chronos-bolt | 300 | 23% | 17% | 0.1634 | +14.6% | +11.0% | 0.023 |
| lull | seldon-laws | 300 | 23% | 23% | 0.1647 | +13.9% | +10.3% | 0.268 |
| lull | radiant-core | 300 | 23% | 26% | 0.1691 | +11.7% | +7.9% | 0.414 |
| lull | persistence | 300 | 23% | 13% | 0.1836 | +4.1% | baseline | 0.588 |
| lull | climatology | 300 | 23% | 10% | 0.1914 | baseline | -4.2% |  |
| spike | seldon | 300 | 8% | 6% | 0.0553 | +22.4% | +21.0% | 0.001 |
| spike | radiant | 300 | 8% | 6% | 0.0564 | +20.9% | +19.5% | 0.002 |
| spike | timesfm-2.5 | 300 | 8% | 6% | 0.0565 | +20.7% | +19.3% | 0.002 |
| spike | chronos-bolt | 300 | 8% | 5% | 0.0585 | +18.0% | +16.5% | 0.014 |
| spike | seldon-laws | 300 | 8% | 11% | 0.0671 | +5.9% | +4.2% | 0.525 |
| spike | radiant-core | 300 | 8% | 11% | 0.0679 | +4.8% | +3.1% | 0.582 |
| spike | persistence | 300 | 8% | 9% | 0.0700 | +1.8% | baseline | 0.519 |
| spike | climatology | 300 | 8% | 10% | 0.0713 | baseline | -1.8% |  |

Sealed event odds are in `predictions/event_ledger.csv`, fingerprinted in `predictions/event_seals.csv` and scored in `predictions/event_scored.csv`.
