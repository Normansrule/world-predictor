# World Predictor: Seldon scorecard

_Generated 2026-11-05 with model `timesfm-2.5`. Skill = 1 - MAE(model) / MAE(naive random walk); positive is better than naive. Coverage80 should be close to 0.80 for an honest forecaster. Brier scores the probability of going up (0.25 = coin flip, lower is better). See docs/METHODOLOGY.md._

## In plain English

- timesfm-2.5 beat the simple guess "tomorrow looks like today" in 2 of 3 areas: world news (15% less error), technology (46% less error).
- Seldon, our own forecaster (crowd laws with timesfm-2.5 as one voter), won 1 of 3 areas (markets) against timesfm-2.5, with lower error on 9 of 32 series and higher on 8.
- Hari Seldon's bet did not hold here: aggregates were not easier to predict than individual series (14% vs 16% skill).
- In world news, its edge lasts up to about 28 days ahead.
- In markets, it had no edge at any distance ahead.
- In technology, its edge lasts up to about 28 days ahead.
- When it gave 70% or more odds of a rise, the rise really happened 80% of the time (56 forecasts).

![Replay of past forecasts against what really happened](plots/replay.gif)

_Each frame is a forecast made in the past: the orange band is what the model expected, the dark dots are what really happened._

## Seldon vs timesfm-2.5: the duel

Seldon is this project's own forecaster (`src/psychohistory/seldon.py`): four laws of crowd behaviour (inertia, drift, momentum, reversion, on top of the weekly rhythm) with TimesFM as one more voter, the laws' share learned per area from finished windows only. It forecasts the same windows as TimesFM and is scored by the same code. A series is won by whichever had the lower average error there; a series where the full Seldon gave TimesFM the whole vote is a tie. Skill is against "no change" (positive is better); range skill scores the whole 80% range (pinball loss).

**The full Seldon** (crowd laws and TimesFM in one council)

| Area | Series | Seldon won | TimesFM won | Seldon's error vs TimesFM | Skill: TimesFM / Seldon | Range skill: TimesFM / Seldon | In 80% range: TimesFM / Seldon | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 15 | 9 | 6 | +1% | -2% / -4% | -2% / -2% | 77% / 78% | Seldon |
| World events in the news | 6 | 0 | 0 | +0% | +15% / +15% | +16% / +16% | 77% / 77% | tie |
| New technologies | 11 | 0 | 2 | +3% | +46% / +46% | +45% / +45% | 74% / 72% | timesfm-2.5 |
| **All areas** | 32 | 9 | 8 | +1% | +8% / +8% | +11% / +12% | 76% / 76% | Seldon |

**The crowd laws alone** (`seldon-laws`, no TimesFM vote)

| Area | Series | Laws won | TimesFM won | Laws' error vs TimesFM | Skill: TimesFM / Laws | Range skill: TimesFM / Laws | In 80% range: TimesFM / Laws | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 15 | 11 | 4 | -2% | -2% / -1% | -2% / +1% | 77% / 77% | Laws |
| World events in the news | 6 | 0 | 6 | +8% | +15% / +10% | +16% / +9% | 77% / 78% | timesfm-2.5 |
| New technologies | 11 | 1 | 10 | +33% | +46% / +25% | +45% / +29% | 74% / 68% | timesfm-2.5 |
| **All areas** | 32 | 12 | 20 | +12% | +8% / +4% | +11% / +8% | 76% / 74% | timesfm-2.5 |

## 1. Can the future be predicted?

![Skill by domain](plots/skill_by_domain.png)

- **World events in the news**: timesfm-2.5 beats the naive baseline (15% less error).
- **Stock and value markets**: timesfm-2.5 about the same as the naive baseline.
- **New technologies**: timesfm-2.5 beats the naive baseline (46% less error).

| domain   | model        |   series |   median_skill |   median_mase |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|---------------:|--------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       15 |         -0.010 |         4.228 |       0.472 |        0.789 |   0.255 |
| markets  | chronos-bolt |       15 |         -0.049 |         4.416 |       0.522 |        0.763 |   0.270 |
| markets  | drift        |       15 |         -0.008 |         4.195 |       0.567 |        0.667 |   0.256 |
| markets  | ensemble     |       15 |         -0.019 |         4.124 |       0.489 |        0.792 |   0.257 |
| markets  | mean         |       15 |         -0.920 |         7.853 |       0.517 |        0.518 |   0.375 |
| markets  | naive        |       15 |          0.000 |         4.228 |     nan     |        0.672 |   0.250 |
| markets  | radiant      |       15 |         -0.018 |         4.254 |       0.450 |        0.759 |   0.260 |
| markets  | radiant-core |       15 |         -0.001 |         4.240 |       0.461 |        0.813 |   0.253 |
| markets  | seldon       |       15 |         -0.040 |         4.264 |       0.439 |        0.783 |   0.267 |
| markets  | seldon-laws  |       15 |         -0.008 |         4.516 |       0.483 |        0.772 |   0.253 |
| markets  | timesfm-2.5  |       15 |         -0.023 |         4.301 |       0.461 |        0.770 |   0.267 |
| news     | auto-ets     |        6 |         -0.108 |         1.613 |       0.542 |        0.887 |   0.245 |
| news     | chronos-bolt |        6 |          0.136 |         1.232 |       0.750 |        0.724 |   0.210 |
| news     | drift        |        6 |         -0.001 |         1.493 |       0.472 |        0.825 |   0.256 |
| news     | ensemble     |        6 |          0.140 |         1.239 |       0.667 |        0.849 |   0.220 |
| news     | mean         |        6 |          0.099 |         1.294 |       0.639 |        0.675 |   0.209 |
| news     | naive        |        6 |          0.000 |         1.498 |     nan     |        0.823 |   0.250 |
| news     | radiant      |        6 |          0.140 |         1.244 |       0.764 |        0.766 |   0.195 |
| news     | radiant-core |        6 |          0.034 |         1.430 |       0.708 |        0.765 |   0.232 |
| news     | seldon       |        6 |          0.149 |         1.235 |       0.764 |        0.766 |   0.193 |
| news     | seldon-laws  |        6 |          0.103 |         1.296 |       0.625 |        0.782 |   0.232 |
| news     | timesfm-2.5  |        6 |          0.149 |         1.235 |       0.764 |        0.766 |   0.193 |
| tech     | auto-ets     |       11 |         -0.098 |         2.556 |       0.605 |        0.815 |   0.207 |
| tech     | bass         |        3 |         -1.365 |       108.159 |       0.333 |        0.000 |   0.602 |
| tech     | chronos-bolt |       11 |          0.481 |         0.798 |       0.756 |        0.758 |   0.154 |
| tech     | drift        |       11 |          0.015 |         1.120 |       0.663 |        0.645 |   0.184 |
| tech     | ensemble     |       11 |          0.359 |         1.259 |       0.689 |        0.850 |   0.174 |
| tech     | mean         |       11 |          0.148 |         1.185 |       0.484 |        0.517 |   0.396 |
| tech     | naive        |       11 |          0.000 |         1.345 |     nan     |        0.646 |   0.297 |
| tech     | radiant      |       11 |          0.469 |         0.785 |       0.771 |        0.735 |   0.150 |
| tech     | radiant-core |       11 |          0.016 |         1.322 |       0.545 |        0.558 |   0.238 |
| tech     | seldon       |       11 |          0.460 |         0.784 |       0.749 |        0.721 |   0.162 |
| tech     | seldon-laws  |       11 |          0.246 |         0.905 |       0.718 |        0.685 |   0.192 |
| tech     | timesfm-2.5  |       11 |          0.460 |         0.784 |       0.749 |        0.741 |   0.160 |

## 2. Seldon's law of large numbers: aggregates vs individuals

Psychohistory only claims to work for very large populations. If that holds here, aggregate series (indices, composites, world totals) should show higher skill and lower MASE than individual ones.

| domain   | scale      | model       |   series |   median_skill |   median_mase |
|:---------|:-----------|:------------|---------:|---------------:|--------------:|
| markets  | aggregate  | timesfm-2.5 |        5 |         -0.086 |         3.735 |
| markets  | individual | timesfm-2.5 |       10 |         -0.018 |         4.766 |
| news     | aggregate  | timesfm-2.5 |        1 |          0.140 |         1.334 |
| news     | individual | timesfm-2.5 |        5 |          0.158 |         1.137 |
| tech     | aggregate  | timesfm-2.5 |        4 |          0.483 |        15.981 |
| tech     | individual | timesfm-2.5 |        7 |          0.429 |         0.784 |

## 3. Seldon crises: what the model did not see coming

Backtest windows where most actual values fell outside the model's 80% band.

| series_id      | domain   | origin     |   coverage80 |    mase |
|:---------------|:---------|:-----------|-------------:|--------:|
| adoption_solar | tech     | 2010-01-01 |        0.000 | 155.972 |
| adoption_solar | tech     | 2007-01-01 |        0.000 | 150.231 |
| adoption_solar | tech     | 1989-01-01 |        0.000 | 108.537 |
| adoption_wind  | tech     | 1989-01-01 |        0.000 |  87.285 |
| adoption_solar | tech     | 2013-01-01 |        0.000 |  82.032 |
| adoption_solar | tech     | 2004-01-01 |        0.000 |  70.178 |
| wiki_ai        | tech     | 2026-09-08 |        0.000 |   5.117 |
| bitcoin        | markets  | 2026-01-27 |        0.036 |  14.993 |
| nasdaq100      | markets  | 2026-04-06 |        0.048 |  12.584 |
| sp500          | markets  | 2026-04-06 |        0.048 |  10.862 |
| msci_world     | markets  | 2026-04-06 |        0.048 |   9.060 |
| sp500          | markets  | 2026-05-05 |        0.095 |   5.177 |
| nvda           | markets  | 2026-05-05 |        0.143 |  11.942 |
| nvda           | markets  | 2026-04-06 |        0.143 |  11.732 |
| copper         | markets  | 2026-04-07 |        0.143 |   8.143 |

## 4. Prediction ledger (true out-of-sample test)

![Time Vault track record](plots/track_record.png)

_Predictions are sealed with a date before the future happens and opened when it arrives. The left line should settle near 80%; the right line should sit below the coin-flip line._

| domain   | model        |   series |   predictions |   median_skill |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|--------------:|---------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       15 |           633 |         -0.000 |       0.517 |        0.831 |   0.255 |
| markets  | chronos-bolt |       15 |           633 |         -0.096 |       0.461 |        0.787 |   0.270 |
| markets  | ensemble     |       15 |           633 |         -0.054 |       0.456 |        0.809 |   0.254 |
| markets  | radiant      |       15 |            46 |         -0.000 |       0.550 |        0.561 |   0.242 |
| markets  | radiant-core |       15 |            46 |         -0.000 |       0.450 |        0.594 |   0.249 |
| markets  | seldon       |       15 |            46 |          0.010 |       0.517 |        0.583 |   0.238 |
| markets  | seldon-laws  |       15 |           318 |         -0.030 |       0.440 |        0.723 |   0.254 |
| markets  | timesfm-2.5  |       15 |           633 |         -0.009 |       0.537 |        0.801 |   0.248 |
| news     | auto-ets     |        6 |           150 |          0.022 |       0.551 |        0.739 |   0.246 |
| news     | chronos-bolt |        6 |           150 |          0.103 |       0.651 |        0.625 |   0.211 |
| news     | ensemble     |        6 |           150 |          0.112 |       0.677 |        0.725 |   0.216 |
| news     | radiant      |        6 |             6 |          0.225 |       0.833 |        0.500 |   0.146 |
| news     | radiant-core |        6 |             6 |          0.060 |       0.833 |        0.833 |   0.222 |
| news     | seldon       |        6 |             6 |          0.225 |       0.833 |        0.500 |   0.146 |
| news     | seldon-laws  |        6 |            66 |          0.068 |       0.676 |        0.515 |   0.225 |
| news     | timesfm-2.5  |        6 |           150 |          0.037 |       0.625 |        0.633 |   0.241 |
| tech     | auto-ets     |        8 |           528 |         -0.222 |       0.566 |        0.940 |   0.236 |
| tech     | chronos-bolt |        8 |           528 |          0.398 |       0.790 |        0.676 |   0.138 |
| tech     | ensemble     |        8 |           528 |          0.237 |       0.738 |        0.940 |   0.145 |
| tech     | radiant      |        8 |            20 |          0.601 |       0.969 |        0.812 |   0.022 |
| tech     | radiant-core |        8 |            20 |          0.013 |       0.969 |        0.062 |   0.237 |
| tech     | seldon       |        8 |            20 |          0.603 |       0.969 |        0.812 |   0.022 |
| tech     | seldon-laws  |        8 |           244 |          0.339 |       0.800 |        0.725 |   0.121 |
| tech     | timesfm-2.5  |        8 |           528 |          0.459 |       0.809 |        0.634 |   0.124 |

## 5. How far ahead can it see?

Median skill versus the naive baseline by how many steps ahead the forecast is (days for news and tech attention, trading days for markets; yearly adoption series are too short for this and are left out). Where skill drops to zero is the limit of the model's foresight in that domain.

![Skill by step](plots/skill_by_step.png)

| domain   |   1 step |    2-5 |   6-10 |   11-20 |    21+ |
|:---------|---------:|-------:|-------:|--------:|-------:|
| markets  |   -0.016 | -0.029 | -0.044 |  -0.033 | -0.016 |
| news     |    0.193 |  0.182 |  0.188 |   0.161 |  0.179 |
| tech     |    0.041 |  0.424 |  0.250 |   0.321 |  0.385 |

## 6. Are its odds honest?

Backtest forecasts grouped by the chance they gave of the series ending higher. `said` is the average probability given, `happened` is how often it really went up. When the two match, the odds can be taken at face value.

| domain   | odds given   |   forecasts |   said |   happened |
|:---------|:-------------|------------:|-------:|-----------:|
| markets  | 0%-20%       |           2 |  0.191 |      0.500 |
| markets  | 20%-40%      |          12 |  0.359 |      0.667 |
| markets  | 40%-60%      |         134 |  0.488 |      0.530 |
| markets  | 60%-80%      |          32 |  0.658 |      0.469 |
| news     | 0%-20%       |          11 |  0.147 |      0.273 |
| news     | 20%-40%      |          19 |  0.308 |      0.263 |
| news     | 40%-60%      |          21 |  0.500 |      0.429 |
| news     | 60%-80%      |          19 |  0.686 |      0.842 |
| news     | 80%-100%     |           2 |  0.845 |      1.000 |
| tech     | 0%-20%       |          22 |  0.121 |      0.182 |
| tech     | 20%-40%      |          21 |  0.308 |      0.286 |
| tech     | 40%-60%      |          24 |  0.512 |      0.583 |
| tech     | 60%-80%      |          24 |  0.692 |      0.625 |
| tech     | 80%-100%     |          30 |  0.908 |      0.933 |

## 7. Every series

| series_id         | domain   | scale      | model       |      mae |   mase |   smape |   direction |   coverage80 |   pinball |   brier |   skill |   prob_skill |
|:------------------|:---------|:-----------|:------------|---------:|-------:|--------:|------------:|-------------:|----------:|--------:|--------:|-------------:|
| aapl              | markets  | individual | timesfm-2.5 |   10.145 |  4.301 |   0.035 |       0.333 |        0.786 |     1.664 |   0.252 |  -0.017 |       -0.019 |
| adoption_internet | tech     | aggregate  | timesfm-2.5 |    2.341 |  0.774 |   0.032 |       1.000 |        1.000 |     0.260 |   0.002 |   0.460 |        0.526 |
| adoption_solar    | tech     | aggregate  | timesfm-2.5 |    0.254 | 64.139 |   0.421 |       0.750 |        0.417 |    27.337 |   0.197 |   0.441 |        0.282 |
| adoption_wind     | tech     | aggregate  | timesfm-2.5 |    0.165 | 31.187 |   0.249 |       0.833 |        0.694 |    12.482 |   0.124 |   0.646 |        0.416 |
| bitcoin           | markets  | individual | timesfm-2.5 | 5629.761 |  4.478 |   0.076 |       0.500 |        0.815 |     1.843 |   0.262 |  -0.010 |       -0.016 |
| copper            | markets  | individual | timesfm-2.5 |    0.180 |  3.337 |   0.030 |       0.500 |        0.861 |     1.374 |   0.258 |  -0.044 |       -0.097 |
| gold              | markets  | individual | timesfm-2.5 |  172.523 |  7.547 |   0.038 |       0.333 |        0.877 |     2.962 |   0.255 |   0.011 |        0.094 |
| msci_world        | markets  | aggregate  | timesfm-2.5 |    3.643 |  3.735 |   0.019 |       0.500 |        0.663 |     1.478 |   0.288 |  -0.093 |       -0.056 |
| nasdaq100         | markets  | aggregate  | timesfm-2.5 |  912.019 |  5.096 |   0.033 |       0.500 |        0.643 |     2.040 |   0.286 |  -0.069 |       -0.044 |
| news_climate      | news     | individual | timesfm-2.5 |    0.130 |  0.988 |   0.157 |       0.750 |        0.780 |     0.384 |   0.196 |   0.102 |        0.134 |
| news_composite    | news     | aggregate  | timesfm-2.5 |    0.074 |  1.334 |   0.091 |       0.750 |        0.759 |     0.529 |   0.223 |   0.140 |        0.105 |
| news_election     | news     | individual | timesfm-2.5 |    0.561 |  1.137 |   0.125 |       0.833 |        0.845 |     0.464 |   0.219 |   0.158 |        0.177 |
| news_inflation    | news     | individual | timesfm-2.5 |    0.316 |  1.033 |   0.163 |       0.750 |        0.741 |     0.407 |   0.178 |   0.288 |        0.284 |
| news_pandemic     | news     | individual | timesfm-2.5 |    0.249 |  1.339 |   0.123 |       0.750 |        0.696 |     0.558 |   0.176 |   0.241 |        0.210 |
| news_protest      | news     | individual | timesfm-2.5 |    0.502 |  1.714 |   0.208 |       0.750 |        0.777 |     0.713 |   0.167 |   0.061 |        0.057 |
| nvda              | markets  | individual | timesfm-2.5 |   11.386 |  5.791 |   0.057 |       0.500 |        0.742 |     2.274 |   0.275 |  -0.009 |        0.060 |
| oil_wti           | markets  | individual | timesfm-2.5 |    7.210 |  5.055 |   0.085 |       0.500 |        0.750 |     1.908 |   0.265 |  -0.044 |        0.064 |
| silver            | markets  | individual | timesfm-2.5 |    5.867 | 10.763 |   0.083 |       0.417 |        0.865 |     4.171 |   0.255 |  -0.018 |        0.125 |
| sp500             | markets  | aggregate  | timesfm-2.5 |  142.066 |  3.752 |   0.020 |       0.500 |        0.675 |     1.502 |   0.273 |  -0.086 |       -0.057 |
| tech_composite    | tech     | aggregate  | timesfm-2.5 |    0.068 |  0.669 |   0.083 |       0.667 |        0.744 |     0.269 |   0.150 |   0.505 |        0.503 |
| tlt               | markets  | individual | timesfm-2.5 |    1.211 |  1.781 |   0.015 |       0.333 |        0.782 |     0.699 |   0.282 |  -0.015 |        0.078 |
| tsla              | markets  | individual | timesfm-2.5 |   24.918 |  3.320 |   0.064 |       0.750 |        0.837 |     1.301 |   0.242 |  -0.023 |       -0.041 |
| us10y             | markets  | aggregate  | timesfm-2.5 |    0.121 |  2.432 |   0.027 |       0.167 |        0.722 |     0.948 |   0.309 |  -0.087 |       -0.028 |
| vix               | markets  | aggregate  | timesfm-2.5 |    1.878 |  1.791 |   0.100 |       0.667 |        0.909 |     0.686 |   0.234 |   0.000 |        0.036 |
| wiki_ai           | tech     | individual | timesfm-2.5 | 1712.361 |  1.270 |   0.128 |       0.750 |        0.732 |     0.538 |   0.172 |   0.673 |        0.689 |
| wiki_crispr       | tech     | individual | timesfm-2.5 |   87.468 |  0.578 |   0.111 |       0.917 |        0.738 |     0.235 |   0.106 |   0.489 |        0.472 |
| wiki_ev           | tech     | individual | timesfm-2.5 |   39.667 |  0.437 |   0.091 |       0.818 |        0.845 |     0.175 |   0.124 |   0.429 |        0.451 |
| wiki_fusion       | tech     | individual | timesfm-2.5 |   91.877 |  0.784 |   0.119 |       0.500 |        0.762 |     0.327 |   0.293 |   0.213 |        0.194 |
| wiki_humanoid     | tech     | individual | timesfm-2.5 |   60.390 |  1.021 |   0.166 |       0.667 |        0.705 |     0.422 |   0.185 |   0.312 |        0.291 |
| wiki_llm          | tech     | individual | timesfm-2.5 |  313.341 |  0.576 |   0.093 |       0.667 |        0.762 |     0.229 |   0.183 |   0.489 |        0.491 |
| wiki_quantum      | tech     | individual | timesfm-2.5 |  352.003 |  0.899 |   0.126 |       0.667 |        0.753 |     0.400 |   0.226 |   0.175 |        0.165 |
| xom               | markets  | individual | timesfm-2.5 |    7.902 |  6.313 |   0.054 |       0.417 |        0.623 |     2.420 |   0.272 |  -0.037 |        0.029 |

## 8. What the model expects next

![What the model expects next](plots/outlook.png)

Latest forecasts recorded in the ledger (made with data up to each series' last date). Changes are relative to the last observed value; the range is the 10%-90% band; "chance higher" is the model's probability that the value on the target date is above today's (scored later with the Brier score: 0 is perfect, 0.25 is a coin flip).

### World events in the news

| series         |   last | target date   | median   | chance higher   | range (10%-90%)   |
|:---------------|-------:|:--------------|:---------|:----------------|:------------------|
| news_climate   |  0.67  | 2026-12-01    | +33.9%   | 90%             | -0.2% to +87.1%   |
| news_composite |  1.072 | 2026-12-01    | -15.7%   | 15%             | -27.5% to +3.8%   |
| news_election  |  8.145 | 2026-12-01    | -34.5%   | 10%             | -50.7% to +0.7%   |
| news_inflation |  2.874 | 2026-12-01    | -25.0%   | 5%              | -42.2% to -0.9%   |
| news_pandemic  |  2.01  | 2026-12-01    | -16.3%   | 11%             | -28.7% to +0.9%   |
| news_protest   |  2.204 | 2026-12-01    | -15.9%   | 28%             | -36.8% to +32.6%  |

![news_climate](plots/news_climate.png)
![news_composite](plots/news_composite.png)
![news_election](plots/news_election.png)
![news_inflation](plots/news_inflation.png)
![news_pandemic](plots/news_pandemic.png)
![news_protest](plots/news_protest.png)

### Stock and value markets

| series     |      last | target date   | median   | chance higher   | range (10%-90%)   |
|:-----------|----------:|:--------------|:---------|:----------------|:------------------|
| aapl       |   331.9   | 2026-12-02    | +1.4%    | 58%             | -8.2% to +8.2%    |
| bitcoin    | 77637     | 2026-12-02    | -1.0%    | 46%             | -16.9% to +15.9%  |
| copper     |     6.384 | 2026-12-03    | +0.2%    | 52%             | -7.7% to +5.2%    |
| gold       |  4006.6   | 2026-12-03    | +0.1%    | 51%             | -7.0% to +9.0%    |
| msci_world |   204.28  | 2026-12-02    | +2.1%    | 79%             | -1.3% to +4.7%    |
| nasdaq100  | 28180.3   | 2026-12-02    | +2.6%    | 67%             | -5.1% to +9.4%    |
| nvda       |   206.69  | 2026-12-02    | -0.2%    | 49%             | -11.0% to +10.3%  |
| oil_wti    |    95.94  | 2026-12-03    | -2.4%    | 40%             | -17.7% to +11.1%  |
| silver     |    51.105 | 2026-12-03    | -1.2%    | 45%             | -13.6% to +14.6%  |
| sp500      |  7568.92  | 2026-12-02    | +1.9%    | 74%             | -2.1% to +5.0%    |
| tlt        |    81.11  | 2026-12-02    | +1.5%    | 74%             | -1.5% to +4.2%    |
| tsla       |   398.5   | 2026-12-02    | +0.3%    | 51%             | -15.0% to +14.9%  |
| us10y      |     4.952 | 2026-12-02    | -0.8%    | 42%             | -5.7% to +4.5%    |
| vix        |    20.83  | 2026-12-02    | -14.1%   | 23%             | -30.1% to +14.7%  |
| xom        |   177.46  | 2026-12-02    | +0.7%    | 53%             | -9.5% to +11.2%   |

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
| adoption_internet |    73.6   | 2028-01-01    | +5.8%    | 79%             | -2.9% to +19.5%   |
| adoption_solar    |     8.745 | 2028-01-01    | +49.5%   | 95%             | +15.3% to +94.2%  |
| adoption_wind     |     8.539 | 2028-01-01    | +6.9%    | 73%             | -9.3% to +22.4%   |
| tech_composite    |     0.702 | 2026-12-01    | +8.0%    | 80%             | -4.9% to +25.9%   |
| wiki_ai           | 15121     | 2026-12-01    | -1.3%    | 46%             | -19.6% to +23.8%  |
| wiki_crispr       |   669     | 2026-12-01    | +11.8%   | 81%             | -5.9% to +34.9%   |
| wiki_ev           |   364     | 2026-12-01    | +12.6%   | 81%             | -5.3% to +37.8%   |
| wiki_fusion       |   502     | 2026-12-01    | +22.4%   | 89%             | -1.1% to +59.3%   |
| wiki_humanoid     |   241     | 2026-12-01    | +17.3%   | 83%             | -5.4% to +57.5%   |
| wiki_llm          |  3166     | 2026-12-01    | +3.8%    | 66%             | -8.6% to +19.7%   |
| wiki_quantum      |  2005     | 2026-12-01    | -11.5%   | 25%             | -26.2% to +14.9%  |

![adoption_internet](plots/adoption_internet.png)
![adoption_solar](plots/adoption_solar.png)
![adoption_wind](plots/adoption_wind.png)
![tech_composite](plots/tech_composite.png)
![wiki_ai](plots/wiki_ai.png)
![wiki_crispr](plots/wiki_crispr.png)
![wiki_ev](plots/wiki_ev.png)
![wiki_fusion](plots/wiki_fusion.png)
![wiki_humanoid](plots/wiki_humanoid.png)
![wiki_llm](plots/wiki_llm.png)
![wiki_quantum](plots/wiki_quantum.png)

## 9. The long-term monitor

Every sealed forecast that has come due, scored against what really happened. Unlike the backtest, none of these could have been fitted to the outcome. Run `psychohistory monitor` for the same in the terminal; the app's Monitor view draws it month by month.

| Model | Forecasts | Weekly batches | Skill vs "no change" | In 80% range | Right direction | Brier |
|---|---|---|---|---|---|---|
| auto-ets | 1311 | 8 | -0.0% | 87% | 52% | 0.247 |
| chronos-bolt | 1311 | 8 | +2.7% | 72% | 60% | 0.214 |
| ensemble | 1311 | 8 | +0.2% | 86% | 58% | 0.209 |
| radiant | 72 | 2 | +4.2% | 61% | 70% | 0.177 |
| radiant-core | 72 | 2 | +0.9% | 50% | 66% | 0.244 |
| seldon | 72 | 2 | +12.3% | 62% | 68% | 0.174 |
| seldon-laws | 628 | 6 | +3.3% | 69% | 57% | 0.202 |
| timesfm-2.5 | 1311 | 8 | +2.3% | 72% | 62% | 0.203 |

**Is timesfm-2.5 really better than "no change"?** A Diebold-Mariano test on the weekly batches (Newey-West variance, as the batches' horizons overlap, with the Harvey-Leybourne-Newbold small-sample correction and Student's t):

- All areas: better than no change (p = 0.01)
- Stock and value markets: not distinguishable from no change (p = 0.81)
- World events in the news: not distinguishable from no change (p = 0.67)
- New technologies: better than no change (p = 0.01)

**Drift alarms** (forecasts due in the last 13 weeks): 19 raised. Every forecaster is tested on every series at once, so alarms must pass a Benjamini-Hochberg false-discovery cut of 5%.
- chronos-bolt on xom: edge lost
- ensemble on aapl: edge lost
- ensemble on wiki_humanoid: edge lost
- seldon-laws on news_inflation: edge lost
- seldon-laws on nvda: edge lost
- timesfm-2.5 on news_election: edge lost
- timesfm-2.5 on news_inflation: edge lost
- timesfm-2.5 on news_pandemic: edge lost
- auto-ets on nvda: range too wide
- auto-ets on wiki_ai: range too wide
- auto-ets on wiki_llm: range too wide
- chronos-bolt on copper: range too wide
- chronos-bolt on wiki_llm: range too narrow
- ensemble on tech_composite: range too wide
- ensemble on wiki_ai: range too wide
- ensemble on wiki_crispr: range too wide
- seldon-laws on nvda: worse than no change
- timesfm-2.5 on silver: range too narrow
- timesfm-2.5 on wiki_llm: range too narrow

## 10. Volatility forecasts

Each market's volatility over the next week and month, forecast at every weekly origin from 2005-12-29 to 2026-10-28 and scored with QLIKE against the volatility that followed. Skill is against last month's volatility carried forward, on the same windows; p is a Diebold-Mariano test.

| Forecaster | Ahead | Windows | Skill | Beat it in | Typical miss | p |
|---|---|---|---|---|---|---|
| garch | 1 week | 13947 | +17.2% | 14 of 14 markets | 32% | 0.000 |
| ewma | 1 week | 13947 | +11.3% | 14 of 14 markets | 31% | 0.000 |
| seldon | 1 week | 168 | +9.4% | 9 of 14 markets | 29% | 0.423 |
| chronos-bolt | 1 week | 168 | +8.3% | 7 of 14 markets | 28% | 0.168 |
| last-month | 1 week | 13947 | baseline |  | 31% |  |
| timesfm-2.5 | 1 week | 168 | -4.5% | 9 of 14 markets | 32% | 0.688 |
| radiant | 1 week | 168 | -5.1% | 4 of 14 markets | 29% | 0.972 |
| seldon-laws | 1 week | 168 | -8.9% | 6 of 14 markets | 29% | 0.143 |
| radiant-core | 1 week | 168 | -9.9% | 9 of 14 markets | 40% | 0.546 |
| garch | 1 month | 13901 | +29.9% | 13 of 14 markets | 24% | 0.000 |
| ewma | 1 month | 13901 | +17.4% | 14 of 14 markets | 22% | 0.000 |
| last-month | 1 month | 13901 | baseline |  | 23% |  |
| seldon | 1 month | 168 | -36.4% | 4 of 14 markets | 26% | 0.253 |
| radiant | 1 month | 168 | -49.3% | 3 of 14 markets | 26% | 0.192 |
| timesfm-2.5 | 1 month | 168 | -50.0% | 6 of 14 markets | 26% | 0.051 |
| chronos-bolt | 1 month | 168 | -59.0% | 5 of 14 markets | 22% | 0.035 |
| seldon-laws | 1 month | 168 | -94.6% | 2 of 14 markets | 26% | 0.160 |
| radiant-core | 1 month | 168 | -109.6% | 6 of 14 markets | 32% | 0.190 |

Sealed volatility forecasts are in `predictions/vol_ledger.csv`, fingerprinted in `predictions/vol_seals.csv` and scored in `predictions/vol_scored.csv`.

## 11. Event odds

The chance that a news or technology series reaches, four weeks ahead, a level it reaches only one day in ten (a spike: above the 90th percentile of its last two years) or falls to a low it sees one day in ten (a lull). Odds are scored with the Brier score; skill is against climatology (10%) and against persistence (what followed days like the origin), on the same forecasts. p is a Diebold-Mariano test of the edge over climatology.

| Event | Forecaster | Forecasts | Happened | Said | Brier | vs climatology | vs persistence | p |
|---|---|---|---|---|---|---|---|---|
| lull | seldon | 168 | 19% | 20% | 0.1206 | +25.8% | +24.2% | 0.110 |
| lull | timesfm-2.5 | 168 | 19% | 20% | 0.1206 | +25.8% | +24.2% | 0.110 |
| lull | radiant | 168 | 19% | 19% | 0.1225 | +24.6% | +23.0% | 0.119 |
| lull | chronos-bolt | 168 | 19% | 16% | 0.1410 | +13.2% | +11.4% | 0.258 |
| lull | seldon-laws | 168 | 19% | 22% | 0.1461 | +10.1% | +8.2% | 0.596 |
| lull | radiant-core | 168 | 19% | 25% | 0.1545 | +4.9% | +2.9% | 0.860 |
| lull | persistence | 168 | 19% | 12% | 0.1591 | +2.1% | baseline | 0.742 |
| lull | climatology | 168 | 19% | 10% | 0.1625 | baseline | -2.1% |  |
| spike | seldon | 168 | 8% | 5% | 0.0549 | +23.6% | +16.8% | 0.050 |
| spike | timesfm-2.5 | 168 | 8% | 5% | 0.0549 | +23.6% | +16.8% | 0.050 |
| spike | radiant | 168 | 8% | 5% | 0.0549 | +23.6% | +16.8% | 0.050 |
| spike | chronos-bolt | 168 | 8% | 6% | 0.0560 | +22.0% | +15.1% | 0.126 |
| spike | radiant-core | 168 | 8% | 10% | 0.0643 | +10.6% | +2.7% | 0.533 |
| spike | persistence | 168 | 8% | 9% | 0.0660 | +8.1% | baseline | 0.162 |
| spike | seldon-laws | 168 | 8% | 10% | 0.0680 | +5.4% | -3.0% | 0.733 |
| spike | climatology | 168 | 8% | 10% | 0.0719 | baseline | -8.9% |  |

Sealed event odds are in `predictions/event_ledger.csv`, fingerprinted in `predictions/event_seals.csv` and scored in `predictions/event_scored.csv`.
