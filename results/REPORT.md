# World Predictor: Seldon scorecard

_Generated 2026-11-03 with model `timesfm-2.5`. Skill = 1 - MAE(model) / MAE(naive random walk); positive is better than naive. Coverage80 should be close to 0.80 for an honest forecaster. Brier scores the probability of going up (0.25 = coin flip, lower is better). See docs/METHODOLOGY.md._

## In plain English

- timesfm-2.5 beat the simple guess "tomorrow looks like today" in 2 of 3 areas: world news (21% less error), technology (42% less error).
- Seldon, our own forecaster (crowd laws with timesfm-2.5 as one voter), won 1 of 3 areas (markets) against timesfm-2.5, with lower error on 10 of 32 series and higher on 7.
- Hari Seldon's bet did not hold here: aggregates were not easier to predict than individual series (18% vs 25% skill).
- In world news, its edge lasts up to about 28 days ahead.
- In markets, it had no edge at any distance ahead.
- In technology, its edge lasts up to about 28 days ahead.
- When it gave 70% or more odds of a rise, the rise really happened 72% of the time (61 forecasts).

![Replay of past forecasts against what really happened](plots/replay.gif)

_Each frame is a forecast made in the past: the orange band is what the model expected, the dark dots are what really happened._

## Seldon vs timesfm-2.5: the duel

Seldon is this project's own forecaster (`src/psychohistory/seldon.py`): four laws of crowd behaviour (inertia, drift, momentum, reversion, on top of the weekly rhythm) with TimesFM as one more voter, the laws' share learned per area from finished windows only. It forecasts the same windows as TimesFM and is scored by the same code. A series is won by whichever had the lower average error there; a series where the full Seldon gave TimesFM the whole vote is a tie. Skill is against "no change" (positive is better); range skill scores the whole 80% range (pinball loss).

**The full Seldon** (crowd laws and TimesFM in one council)

| Area | Series | Seldon won | TimesFM won | Seldon's error vs TimesFM | Skill: TimesFM / Seldon | Range skill: TimesFM / Seldon | In 80% range: TimesFM / Seldon | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 15 | 10 | 5 | -1% | -1% / -2% | +1% / -1% | 75% / 74% | Seldon |
| World events in the news | 6 | 0 | 0 | +0% | +21% / +21% | +21% / +21% | 76% / 76% | tie |
| New technologies | 11 | 0 | 2 | +3% | +42% / +42% | +40% / +34% | 74% / 72% | timesfm-2.5 |
| **All areas** | 32 | 10 | 7 | +1% | +12% / +12% | +14% / +13% | 75% / 74% | Seldon |

**The crowd laws alone** (`seldon-laws`, no TimesFM vote)

| Area | Series | Laws won | TimesFM won | Laws' error vs TimesFM | Skill: TimesFM / Laws | Range skill: TimesFM / Laws | In 80% range: TimesFM / Laws | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 15 | 12 | 3 | -3% | -1% / +1% | +1% / +2% | 75% / 75% | Laws |
| World events in the news | 6 | 0 | 6 | +10% | +21% / +15% | +21% / +16% | 76% / 79% | timesfm-2.5 |
| New technologies | 11 | 1 | 10 | +29% | +42% / +22% | +40% / +23% | 74% / 67% | timesfm-2.5 |
| **All areas** | 32 | 13 | 19 | +11% | +12% / +5% | +14% / +11% | 75% / 73% | timesfm-2.5 |

## 1. Can the future be predicted?

![Skill by domain](plots/skill_by_domain.png)

- **World events in the news**: timesfm-2.5 beats the naive baseline (21% less error).
- **Stock and value markets**: timesfm-2.5 about the same as the naive baseline.
- **New technologies**: timesfm-2.5 beats the naive baseline (42% less error).

| domain   | model        |   series |   median_skill |   median_mase |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|---------------:|--------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       15 |         -0.000 |         4.382 |       0.483 |        0.788 |   0.253 |
| markets  | chronos-bolt |       15 |         -0.048 |         4.191 |       0.528 |        0.737 |   0.265 |
| markets  | drift        |       15 |          0.008 |         4.320 |       0.556 |        0.660 |   0.256 |
| markets  | ensemble     |       15 |         -0.001 |         4.290 |       0.500 |        0.777 |   0.254 |
| markets  | mean         |       15 |         -0.911 |         7.922 |       0.517 |        0.520 |   0.359 |
| markets  | naive        |       15 |          0.000 |         4.407 |     nan     |        0.663 |   0.250 |
| markets  | radiant      |       15 |         -0.014 |         4.560 |       0.439 |        0.750 |   0.258 |
| markets  | radiant-core |       15 |         -0.002 |         4.446 |       0.461 |        0.800 |   0.252 |
| markets  | seldon       |       15 |         -0.016 |         4.644 |       0.461 |        0.737 |   0.264 |
| markets  | seldon-laws  |       15 |          0.007 |         4.422 |       0.500 |        0.754 |   0.252 |
| markets  | timesfm-2.5  |       15 |         -0.014 |         4.721 |       0.467 |        0.755 |   0.268 |
| news     | auto-ets     |        6 |         -0.060 |         1.584 |       0.625 |        0.883 |   0.240 |
| news     | chronos-bolt |        6 |          0.197 |         1.199 |       0.708 |        0.732 |   0.208 |
| news     | drift        |        6 |         -0.000 |         1.550 |       0.417 |        0.805 |   0.260 |
| news     | ensemble     |        6 |          0.175 |         1.280 |       0.639 |        0.844 |   0.215 |
| news     | mean         |        6 |          0.178 |         1.289 |       0.694 |        0.677 |   0.212 |
| news     | naive        |        6 |          0.000 |         1.548 |     nan     |        0.808 |   0.250 |
| news     | radiant      |        6 |          0.178 |         1.276 |       0.681 |        0.757 |   0.205 |
| news     | radiant-core |        6 |          0.040 |         1.488 |       0.639 |        0.772 |   0.226 |
| news     | seldon       |        6 |          0.213 |         1.224 |       0.681 |        0.762 |   0.205 |
| news     | seldon-laws  |        6 |          0.149 |         1.314 |       0.625 |        0.788 |   0.216 |
| news     | timesfm-2.5  |        6 |          0.213 |         1.224 |       0.681 |        0.762 |   0.205 |
| tech     | auto-ets     |       11 |          0.130 |         1.724 |       0.621 |        0.808 |   0.211 |
| tech     | bass         |        3 |         -1.365 |       108.159 |       0.333 |        0.000 |   0.603 |
| tech     | chronos-bolt |       11 |          0.404 |         0.822 |       0.773 |        0.755 |   0.156 |
| tech     | drift        |       11 |         -0.013 |         1.367 |       0.682 |        0.649 |   0.179 |
| tech     | ensemble     |       11 |          0.373 |         0.989 |       0.682 |        0.850 |   0.188 |
| tech     | mean         |       11 |          0.102 |         1.184 |       0.333 |        0.522 |   0.492 |
| tech     | naive        |       11 |          0.000 |         1.407 |     nan     |        0.652 |   0.297 |
| tech     | radiant      |       11 |          0.391 |         0.805 |       0.758 |        0.717 |   0.180 |
| tech     | radiant-core |       11 |          0.030 |         1.313 |       0.435 |        0.516 |   0.252 |
| tech     | seldon       |       11 |          0.420 |         0.807 |       0.758 |        0.721 |   0.181 |
| tech     | seldon-laws  |       11 |          0.219 |         0.964 |       0.773 |        0.669 |   0.184 |
| tech     | timesfm-2.5  |       11 |          0.420 |         0.807 |       0.758 |        0.741 |   0.179 |

## 2. Seldon's law of large numbers: aggregates vs individuals

Psychohistory only claims to work for very large populations. If that holds here, aggregate series (indices, composites, world totals) should show higher skill and lower MASE than individual ones.

| domain   | scale      | model       |   series |   median_skill |   median_mase |
|:---------|:-----------|:------------|---------:|---------------:|--------------:|
| markets  | aggregate  | timesfm-2.5 |        5 |         -0.079 |         3.696 |
| markets  | individual | timesfm-2.5 |       10 |         -0.003 |         5.198 |
| news     | aggregate  | timesfm-2.5 |        1 |          0.180 |         1.295 |
| news     | individual | timesfm-2.5 |        5 |          0.247 |         1.152 |
| tech     | aggregate  | timesfm-2.5 |        4 |          0.487 |        15.981 |
| tech     | individual | timesfm-2.5 |        7 |          0.375 |         0.807 |

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
| oil_wti        | markets  | 2026-03-04 |        0.000 |  15.624 |
| nasdaq100      | markets  | 2026-05-04 |        0.000 |   9.132 |
| sp500          | markets  | 2026-05-04 |        0.000 |   6.419 |
| wiki_ai        | tech     | 2026-09-06 |        0.036 |   5.266 |
| nasdaq100      | markets  | 2026-04-02 |        0.095 |  12.391 |
| sp500          | markets  | 2026-04-02 |        0.095 |  10.801 |
| copper         | markets  | 2026-05-04 |        0.095 |  10.247 |
| news_inflation | news     | 2026-02-25 |        0.107 |   2.119 |
| bitcoin        | markets  | 2026-01-26 |        0.143 |  13.484 |

## 4. Prediction ledger (true out-of-sample test)

![Time Vault track record](plots/track_record.png)

_Predictions are sealed with a date before the future happens and opened when it arrives. The left line should settle near 80%; the right line should sit below the coin-flip line._

| domain   | model        |   series |   predictions |   median_skill |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|--------------:|---------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       12 |           419 |         -0.001 |       0.482 |        0.879 |   0.253 |
| markets  | chronos-bolt |       12 |           419 |         -0.067 |       0.474 |        0.821 |   0.269 |
| markets  | ensemble     |       12 |           419 |         -0.017 |       0.482 |        0.852 |   0.255 |
| markets  | seldon-laws  |       12 |           162 |         -0.019 |       0.334 |        0.750 |   0.260 |
| markets  | timesfm-2.5  |       12 |           419 |          0.014 |       0.508 |        0.842 |   0.252 |
| news     | auto-ets     |        6 |           111 |          0.019 |       0.568 |        0.793 |   0.240 |
| news     | chronos-bolt |        6 |           111 |          0.072 |       0.606 |        0.681 |   0.244 |
| news     | ensemble     |        6 |           111 |          0.036 |       0.608 |        0.762 |   0.240 |
| news     | seldon-laws  |        6 |            36 |          0.002 |       0.606 |        0.500 |   0.269 |
| news     | timesfm-2.5  |        6 |           111 |          0.046 |       0.551 |        0.688 |   0.279 |
| tech     | auto-ets     |        8 |           400 |         -0.231 |       0.520 |        0.960 |   0.253 |
| tech     | chronos-bolt |        8 |           400 |          0.480 |       0.768 |        0.713 |   0.150 |
| tech     | ensemble     |        8 |           400 |          0.243 |       0.715 |        0.945 |   0.156 |
| tech     | seldon-laws  |        8 |           152 |          0.305 |       0.724 |        0.737 |   0.157 |
| tech     | timesfm-2.5  |        8 |           400 |          0.535 |       0.792 |        0.677 |   0.133 |

## 5. How far ahead can it see?

Median skill versus the naive baseline by how many steps ahead the forecast is (days for news and tech attention, trading days for markets; yearly adoption series are too short for this and are left out). Where skill drops to zero is the limit of the model's foresight in that domain.

![Skill by step](plots/skill_by_step.png)

| domain   |   1 step |    2-5 |   6-10 |   11-20 |    21+ |
|:---------|---------:|-------:|-------:|--------:|-------:|
| markets  |    0.033 | -0.026 | -0.040 |  -0.013 | -0.088 |
| news     |    0.183 |  0.273 |  0.246 |   0.171 |  0.192 |
| tech     |    0.619 |  0.479 |  0.370 |   0.381 |  0.361 |

## 6. Are its odds honest?

Backtest forecasts grouped by the chance they gave of the series ending higher. `said` is the average probability given, `happened` is how often it really went up. When the two match, the odds can be taken at face value.

| domain   | odds given   |   forecasts |   said |   happened |
|:---------|:-------------|------------:|-------:|-----------:|
| markets  | 0%-20%       |           1 |  0.132 |      0.000 |
| markets  | 20%-40%      |          14 |  0.373 |      0.643 |
| markets  | 40%-60%      |         127 |  0.484 |      0.567 |
| markets  | 60%-80%      |          38 |  0.657 |      0.421 |
| news     | 0%-20%       |          14 |  0.098 |      0.143 |
| news     | 20%-40%      |          23 |  0.301 |      0.478 |
| news     | 40%-60%      |          17 |  0.472 |      0.529 |
| news     | 60%-80%      |          14 |  0.690 |      0.929 |
| news     | 80%-100%     |           4 |  0.853 |      0.750 |
| tech     | 0%-20%       |          16 |  0.128 |      0.312 |
| tech     | 20%-40%      |          31 |  0.311 |      0.194 |
| tech     | 40%-60%      |          18 |  0.516 |      0.667 |
| tech     | 60%-80%      |          29 |  0.701 |      0.655 |
| tech     | 80%-100%     |          27 |  0.909 |      0.852 |

## 7. Every series

| series_id         | domain   | scale      | model       |      mae |   mase |   smape |   direction |   coverage80 |   pinball |   brier |   skill |   prob_skill |
|:------------------|:---------|:-----------|:------------|---------:|-------:|--------:|------------:|-------------:|----------:|--------:|--------:|-------------:|
| aapl              | markets  | individual | timesfm-2.5 |   11.277 |  4.775 |   0.039 |       0.500 |        0.734 |     1.849 |   0.241 |  -0.007 |       -0.008 |
| adoption_internet | tech     | aggregate  | timesfm-2.5 |    2.341 |  0.774 |   0.032 |       1.000 |        1.000 |     0.260 |   0.003 |   0.460 |        0.526 |
| adoption_solar    | tech     | aggregate  | timesfm-2.5 |    0.254 | 64.139 |   0.421 |       0.750 |        0.417 |    27.337 |   0.197 |   0.441 |        0.282 |
| adoption_wind     | tech     | aggregate  | timesfm-2.5 |    0.165 | 31.187 |   0.249 |       0.833 |        0.694 |    12.482 |   0.124 |   0.646 |        0.416 |
| bitcoin           | markets  | individual | timesfm-2.5 | 5910.618 |  4.721 |   0.079 |       0.250 |        0.815 |     1.834 |   0.285 |  -0.068 |       -0.041 |
| copper            | markets  | individual | timesfm-2.5 |    0.201 |  3.760 |   0.034 |       0.500 |        0.813 |     1.548 |   0.258 |   0.000 |       -0.025 |
| gold              | markets  | individual | timesfm-2.5 |  198.294 |  8.754 |   0.044 |       0.750 |        0.786 |     3.469 |   0.236 |   0.002 |        0.104 |
| msci_world        | markets  | aggregate  | timesfm-2.5 |    3.606 |  3.696 |   0.019 |       0.500 |        0.679 |     1.460 |   0.338 |  -0.089 |       -0.055 |
| nasdaq100         | markets  | aggregate  | timesfm-2.5 |  968.020 |  5.411 |   0.035 |       0.500 |        0.583 |     2.180 |   0.287 |  -0.056 |       -0.051 |
| news_climate      | news     | individual | timesfm-2.5 |    0.131 |  0.994 |   0.159 |       0.667 |        0.771 |     0.383 |   0.225 |   0.097 |        0.118 |
| news_composite    | news     | aggregate  | timesfm-2.5 |    0.072 |  1.295 |   0.088 |       0.667 |        0.777 |     0.515 |   0.220 |   0.180 |        0.151 |
| news_election     | news     | individual | timesfm-2.5 |    0.568 |  1.152 |   0.128 |       0.667 |        0.807 |     0.474 |   0.186 |   0.247 |        0.290 |
| news_inflation    | news     | individual | timesfm-2.5 |    0.302 |  0.988 |   0.156 |       0.667 |        0.771 |     0.388 |   0.232 |   0.278 |        0.265 |
| news_pandemic     | news     | individual | timesfm-2.5 |    0.247 |  1.331 |   0.123 |       0.500 |        0.702 |     0.553 |   0.225 |   0.346 |        0.338 |
| news_protest      | news     | individual | timesfm-2.5 |    0.506 |  1.723 |   0.212 |       0.917 |        0.747 |     0.731 |   0.141 |   0.137 |        0.130 |
| nvda              | markets  | individual | timesfm-2.5 |   11.417 |  5.819 |   0.057 |       0.417 |        0.786 |     2.226 |   0.273 |  -0.014 |        0.074 |
| oil_wti           | markets  | individual | timesfm-2.5 |    8.385 |  5.880 |   0.101 |       0.417 |        0.694 |     2.325 |   0.256 |   0.023 |        0.101 |
| silver            | markets  | individual | timesfm-2.5 |    6.230 | 11.342 |   0.088 |       0.417 |        0.869 |     4.299 |   0.257 |   0.003 |        0.166 |
| sp500             | markets  | aggregate  | timesfm-2.5 |  145.670 |  3.841 |   0.021 |       0.583 |        0.671 |     1.557 |   0.272 |  -0.087 |       -0.067 |
| tech_composite    | tech     | aggregate  | timesfm-2.5 |    0.071 |  0.699 |   0.087 |       0.833 |        0.711 |     0.282 |   0.171 |   0.514 |        0.480 |
| tlt               | markets  | individual | timesfm-2.5 |    1.283 |  1.846 |   0.015 |       0.333 |        0.738 |     0.716 |   0.285 |  -0.037 |        0.036 |
| tsla              | markets  | individual | timesfm-2.5 |   22.525 |  2.994 |   0.057 |       0.667 |        0.881 |     1.181 |   0.247 |   0.037 |        0.018 |
| us10y             | markets  | aggregate  | timesfm-2.5 |    0.115 |  2.298 |   0.025 |       0.250 |        0.730 |     0.909 |   0.297 |  -0.079 |       -0.035 |
| vix               | markets  | aggregate  | timesfm-2.5 |    2.210 |  2.107 |   0.116 |       0.583 |        0.833 |     0.808 |   0.220 |   0.055 |        0.121 |
| wiki_ai           | tech     | individual | timesfm-2.5 | 1739.261 |  1.292 |   0.131 |       0.583 |        0.726 |     0.547 |   0.280 |   0.375 |        0.341 |
| wiki_crispr       | tech     | individual | timesfm-2.5 |   88.868 |  0.584 |   0.111 |       0.750 |        0.759 |     0.236 |   0.218 |   0.402 |        0.401 |
| wiki_ev           | tech     | individual | timesfm-2.5 |   40.841 |  0.447 |   0.093 |       0.667 |        0.854 |     0.176 |   0.203 |   0.420 |        0.453 |
| wiki_fusion       | tech     | individual | timesfm-2.5 |   94.502 |  0.807 |   0.123 |       0.750 |        0.726 |     0.336 |   0.192 |   0.305 |        0.270 |
| wiki_humanoid     | tech     | individual | timesfm-2.5 |   61.231 |  1.035 |   0.169 |       0.833 |        0.685 |     0.430 |   0.152 |   0.234 |        0.212 |
| wiki_llm          | tech     | individual | timesfm-2.5 |  295.715 |  0.544 |   0.089 |       0.833 |        0.801 |     0.216 |   0.154 |   0.613 |        0.583 |
| wiki_quantum      | tech     | individual | timesfm-2.5 |  355.985 |  0.910 |   0.128 |       0.500 |        0.783 |     0.403 |   0.280 |   0.319 |        0.262 |
| xom               | markets  | individual | timesfm-2.5 |    7.031 |  5.621 |   0.048 |       0.333 |        0.706 |     2.166 |   0.275 |  -0.046 |        0.013 |

## 8. What the model expects next

![What the model expects next](plots/outlook.png)

Latest forecasts recorded in the ledger (made with data up to each series' last date). Changes are relative to the last observed value; the range is the 10%-90% band; "chance higher" is the model's probability that the value on the target date is above today's (scored later with the Brier score: 0 is perfect, 0.25 is a coin flip).

### World events in the news

| series         |   last | target date   | median   | chance higher   | range (10%-90%)   |
|:---------------|-------:|:--------------|:---------|:----------------|:------------------|
| news_climate   |  0.857 | 2026-11-24    | +7.2%    | 62%             | -18.9% to +49.4%  |
| news_composite |  1.323 | 2026-11-24    | -27.4%   | 5%              | -38.9% to -7.0%   |
| news_election  | 11.407 | 2026-11-24    | -51.0%   | 5%              | -63.0% to -23.4%  |
| news_inflation |  2.976 | 2026-11-24    | -33.0%   | 5%              | -48.2% to -10.1%  |
| news_pandemic  |  1.713 | 2026-11-24    | -6.7%    | 29%             | -20.9% to +13.0%  |
| news_protest   |  3.156 | 2026-11-24    | -31.5%   | 14%             | -48.8% to +7.8%   |

![news_climate](plots/news_climate.png)
![news_composite](plots/news_composite.png)
![news_election](plots/news_election.png)
![news_inflation](plots/news_inflation.png)
![news_pandemic](plots/news_pandemic.png)
![news_protest](plots/news_protest.png)

### Stock and value markets

| series     |      last | target date   | median   | chance higher   | range (10%-90%)   |
|:-----------|----------:|:--------------|:---------|:----------------|:------------------|
| aapl       |   344.63  | 2026-11-30    | +0.9%    | 56%             | -6.7% to +6.2%    |
| bitcoin    | 77028.7   | 2026-12-01    | -1.9%    | 44%             | -18.2% to +15.7%  |
| copper     |     6.527 | 2026-12-01    | -0.2%    | 46%             | -7.4% to +4.0%    |
| gold       |  3964.2   | 2026-12-01    | -0.6%    | 45%             | -8.0% to +8.1%    |
| msci_world |   204.64  | 2026-11-30    | +2.4%    | 82%             | -0.9% to +4.8%    |
| nasdaq100  | 27989.8   | 2026-12-01    | +3.0%    | 67%             | -5.8% to +10.1%   |
| nvda       |   204.64  | 2026-11-30    | +0.9%    | 54%             | -10.7% to +12.3%  |
| oil_wti    |    96.73  | 2026-12-01    | -2.7%    | 40%             | -18.2% to +11.7%  |
| silver     |    50.44  | 2026-12-01    | -0.8%    | 47%             | -13.1% to +15.3%  |
| sp500      |  7541.4   | 2026-12-01    | +2.2%    | 76%             | -2.2% to +5.2%    |
| tlt        |    81.84  | 2026-11-30    | +1.0%    | 67%             | -1.9% to +3.6%    |
| tsla       |   399.81  | 2026-11-30    | +0.2%    | 51%             | -15.3% to +15.7%  |
| us10y      |     4.894 | 2026-12-01    | -0.6%    | 44%             | -5.7% to +4.7%    |
| vix        |    21.15  | 2026-12-01    | -15.7%   | 20%             | -31.2% to +12.9%  |
| xom        |   187.25  | 2026-11-30    | +0.5%    | 52%             | -9.7% to +11.3%   |

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
| tech_composite    |     0.523 | 2026-11-29    | +17.0%   | 95%             | +4.4% to +35.9%   |
| wiki_ai           | 12385     | 2026-11-29    | -6.5%    | 33%             | -21.9% to +20.1%  |
| wiki_crispr       |   492     | 2026-11-29    | +19.6%   | 88%             | -1.6% to +48.2%   |
| wiki_ev           |   284     | 2026-11-29    | +25.5%   | 95%             | +5.6% to +53.7%   |
| wiki_fusion       |   378     | 2026-11-29    | +31.0%   | 95%             | +2.9% to +76.3%   |
| wiki_humanoid     |   185     | 2026-11-29    | +35.6%   | 95%             | +9.1% to +82.3%   |
| wiki_llm          |  2418     | 2026-11-29    | +5.5%    | 75%             | -4.8% to +21.7%   |
| wiki_quantum      |  1151     | 2026-11-29    | +12.6%   | 79%             | -5.7% to +47.8%   |

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
| auto-ets | 930 | 6 | -0.1% | 90% | 51% | 0.251 |
| chronos-bolt | 930 | 6 | +7.2% | 76% | 61% | 0.216 |
| ensemble | 930 | 6 | +0.7% | 88% | 59% | 0.211 |
| seldon-laws | 350 | 4 | +0.4% | 71% | 52% | 0.216 |
| timesfm-2.5 | 930 | 6 | +6.0% | 76% | 64% | 0.204 |

**Is timesfm-2.5 really better than "no change"?** A Diebold-Mariano test on the weekly batches (Newey-West variance, as the batches' horizons overlap, with the Harvey-Leybourne-Newbold small-sample correction and Student's t):

- All areas: not distinguishable from no change (p = 0.36)
- Stock and value markets: not distinguishable from no change (p = 0.70)
- World events in the news: not distinguishable from no change
- New technologies: not distinguishable from no change (p = 0.47)

**Drift alarms** (forecasts due in the last 13 weeks): 25 raised. Every forecaster is tested on every series at once, so alarms must pass a Benjamini-Hochberg false-discovery cut of 5%.
- auto-ets on aapl: range too wide
- auto-ets on bitcoin: range too wide
- auto-ets on copper: range too wide
- auto-ets on news_pandemic: edge lost
- auto-ets on wiki_quantum: range too wide
- chronos-bolt on aapl: range too wide
- chronos-bolt on aapl: edge lost
- chronos-bolt on msci_world: range too wide
- chronos-bolt on news_election: edge lost
- chronos-bolt on xom: range too wide
- ensemble on aapl: range too wide
- ensemble on news_election: edge lost
- ensemble on wiki_humanoid: edge lost
- ensemble on wiki_quantum: range too wide
- ensemble on xom: range too wide
- timesfm-2.5 on aapl: range too wide
- timesfm-2.5 on bitcoin: range too wide
- timesfm-2.5 on news_election: edge lost
- timesfm-2.5 on oil_wti: edge lost
- timesfm-2.5 on tsla: edge lost
- timesfm-2.5 on xom: range too wide
- auto-ets on wiki_crispr: range too wide
- auto-ets on wiki_llm: range too wide
- chronos-bolt on copper: range too wide
- ensemble on copper: range too wide

## 10. Volatility forecasts

Each market's volatility over the next week and month, forecast at every weekly origin from 2025-11-28 to 2026-10-22 and scored with QLIKE against the volatility that followed. Skill is against last month's volatility carried forward, on the same windows; p is a Diebold-Mariano test.

| Forecaster | Ahead | Windows | Skill | Beat it in | Typical miss | p |
|---|---|---|---|---|---|---|
| garch | 1 week | 378 | +12.7% | 10 of 12 markets | 32% | 0.282 |
| ewma | 1 week | 378 | +10.5% | 12 of 12 markets | 28% | 0.036 |
| last-month | 1 week | 437 | baseline |  | 30% |  |
| timesfm-2.5 | 1 week | 132 | -12.5% | 5 of 12 markets | 25% | 0.928 |
| seldon | 1 week | 132 | -16.9% | 4 of 12 markets | 29% | 0.689 |
| seldon-laws | 1 week | 132 | -82.4% | 1 of 12 markets | 33% | 0.004 |
| ewma | 1 month | 341 | +12.0% | 10 of 12 markets | 19% | 0.302 |
| garch | 1 month | 341 | +10.7% | 8 of 12 markets | 22% | 0.389 |
| last-month | 1 month | 400 | baseline |  | 22% |  |
| seldon | 1 month | 132 | -19.6% | 5 of 12 markets | 23% | 0.558 |
| timesfm-2.5 | 1 month | 132 | -20.9% | 5 of 12 markets | 20% | 0.606 |
| seldon-laws | 1 month | 132 | -123.0% | 3 of 12 markets | 30% | 0.412 |

Sealed volatility forecasts are in `predictions/vol_ledger.csv`, fingerprinted in `predictions/vol_seals.csv` and scored in `predictions/vol_scored.csv`.

## 11. Event odds

The chance that a news or technology series reaches, four weeks ahead, a level it reaches only one day in ten (a spike: above the 90th percentile of its last two years) or falls to a low it sees one day in ten (a lull). Odds are scored with the Brier score; skill is against climatology (10%) and against persistence (what followed days like the origin), on the same forecasts. p is a Diebold-Mariano test of the edge over climatology.

| Event | Forecaster | Forecasts | Happened | Said | Brier | vs climatology | vs persistence | p |
|---|---|---|---|---|---|---|---|---|
| lull | seldon | 70 | 40% | 35% | 0.1666 | +49.4% | +40.9% | 0.052 |
| lull | timesfm-2.5 | 70 | 40% | 35% | 0.1696 | +48.5% | +39.9% | 0.060 |
| lull | seldon-laws | 70 | 40% | 33% | 0.1936 | +41.2% | +31.4% | 0.095 |
| lull | persistence | 70 | 40% | 15% | 0.2821 | +14.3% | baseline | 0.054 |
| lull | climatology | 70 | 40% | 10% | 0.3293 | baseline | -16.7% |  |
| spike | timesfm-2.5 | 70 | 10% | 8% | 0.0803 | +10.9% | +12.6% | 0.418 |
| spike | seldon | 70 | 10% | 9% | 0.0831 | +7.8% | +9.6% | 0.612 |
| spike | climatology | 70 | 10% | 10% | 0.0902 | baseline | +1.9% |  |
| spike | persistence | 70 | 10% | 10% | 0.0919 | -2.0% | baseline | 0.543 |
| spike | seldon-laws | 70 | 10% | 11% | 0.0920 | -2.0% | -0.0% | 0.880 |

Sealed event odds are in `predictions/event_ledger.csv`, fingerprinted in `predictions/event_seals.csv` and scored in `predictions/event_scored.csv`.
