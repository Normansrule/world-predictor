# World Predictor: Seldon scorecard

_Generated 2026-11-28 with model `timesfm-2.5`. Skill = 1 - MAE(model) / MAE(naive random walk); positive is better than naive. Coverage80 should be close to 0.80 for an honest forecaster. Brier scores the probability of going up (0.25 = coin flip, lower is better). See docs/METHODOLOGY.md._

## In plain English

- timesfm-2.5 beat the simple guess "tomorrow looks like today" in 4 of 5 areas: world news (13% less error), politics (11% less error), technology (41% less error), the weather (18% less error).
- Seldon, our own forecaster (crowd laws with timesfm-2.5 as one voter), won 1 of 5 areas (markets) against timesfm-2.5, with lower error on 18 of 53 series and higher on 35.
- Hari Seldon's bet held here: big aggregates such as indices and averages were easier to predict than single stocks or topics (12% vs 12% skill).
- In world news, its edge lasts up to about 28 days ahead.
- In politics, its edge lasts up to about 28 days ahead.
- In markets, it had no edge at any distance ahead.
- In technology, its edge lasts up to about 28 days ahead.
- In the weather, its edge lasts up to about 14 days ahead.
- When it gave 70% or more odds of a rise, the rise really happened 83% of the time (122 forecasts).

![Replay of past forecasts against what really happened](plots/replay.gif)

_Each frame is a forecast made in the past: the orange band is what the model expected, the dark dots are what really happened._

## Seldon vs timesfm-2.5: the duel

Seldon is this project's own forecaster (`src/psychohistory/seldon.py`): four laws of crowd behaviour (inertia, drift, momentum, reversion, on top of the weekly rhythm), a behavioural core, "no change" and Chronos-Bolt, each voter's weight learned per area from finished windows only. Since November 2026 TimesFM is not one of its voters, so Seldon is a second opinion, not a copy. It forecasts the same windows as TimesFM and is scored by the same code. A series is won by whichever had the lower average error there; an exact tie is a tie. Skill is against "no change" (positive is better); range skill scores the whole 80% range (pinball loss).

**The full Seldon** (crowd laws and TimesFM in one council)

| Area | Series | Seldon won | TimesFM won | Seldon's error vs TimesFM | Skill: TimesFM / Seldon | Range skill: TimesFM / Seldon | In 80% range: TimesFM / Seldon | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 15 | 8 | 7 | -1% | -2% / -0% | +2% / +1% | 83% / 76% | Seldon |
| World events in the news | 6 | 1 | 5 | +3% | +13% / +8% | +13% / +10% | 78% / 78% | timesfm-2.5 |
| Political events | 7 | 2 | 5 | +3% | +11% / +11% | +15% / +12% | 80% / 80% | timesfm-2.5 |
| New technologies | 16 | 5 | 11 | +1% | +41% / +35% | +40% / +38% | 72% / 75% | timesfm-2.5 |
| Weather and the planet | 9 | 2 | 7 | +20% | +18% / +17% | +18% / +17% | 80% / 78% | timesfm-2.5 |
| **All areas** | 53 | 18 | 35 | +4% | +12% / +9% | +15% / +11% | 78% / 77% | timesfm-2.5 |

**The crowd laws alone** (`seldon-laws`, no TimesFM vote)

| Area | Series | Laws won | TimesFM won | Laws' error vs TimesFM | Skill: TimesFM / Laws | Range skill: TimesFM / Laws | In 80% range: TimesFM / Laws | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 15 | 5 | 10 | +1% | -2% / -2% | +2% / -1% | 83% / 82% | timesfm-2.5 |
| World events in the news | 6 | 2 | 4 | +4% | +13% / +7% | +13% / +7% | 78% / 78% | timesfm-2.5 |
| Political events | 7 | 0 | 7 | +7% | +11% / +8% | +15% / +11% | 80% / 81% | timesfm-2.5 |
| New technologies | 16 | 2 | 14 | +24% | +41% / +23% | +40% / +25% | 72% / 70% | timesfm-2.5 |
| Weather and the planet | 9 | 1 | 8 | +59% | +18% / +8% | +18% / +6% | 80% / 74% | timesfm-2.5 |
| **All areas** | 53 | 10 | 43 | +19% | +12% / +7% | +15% / +9% | 78% / 76% | timesfm-2.5 |

## 1. Can the future be predicted?

![Skill by domain](plots/skill_by_domain.png)

- **World events in the news**: timesfm-2.5 beats the naive baseline (13% less error).
- **Political events**: timesfm-2.5 beats the naive baseline (11% less error).
- **Stock and value markets**: timesfm-2.5 about the same as the naive baseline.
- **New technologies**: timesfm-2.5 beats the naive baseline (41% less error).
- **Weather and the planet**: timesfm-2.5 beats the naive baseline (18% less error).

| domain   | model        |   series |   median_skill |   median_mase |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|---------------:|--------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       15 |         -0.007 |         3.813 |       0.465 |        0.835 |   0.256 |
| markets  | chronos-bolt |       15 |         -0.062 |         3.904 |       0.526 |        0.811 |   0.261 |
| markets  | drift        |       15 |         -0.014 |         3.643 |       0.526 |        0.697 |   0.265 |
| markets  | ensemble     |       15 |         -0.013 |         3.553 |       0.537 |        0.844 |   0.247 |
| markets  | mean         |       15 |         -1.017 |         7.704 |       0.508 |        0.511 |   0.360 |
| markets  | naive        |       15 |          0.000 |         3.786 |     nan     |        0.702 |   0.250 |
| markets  | radiant      |       15 |         -0.008 |         3.801 |       0.446 |        0.782 |   0.251 |
| markets  | radiant-core |       15 |         -0.003 |         3.791 |       0.474 |        0.846 |   0.251 |
| markets  | seldon       |       15 |         -0.003 |         3.798 |       0.407 |        0.763 |   0.251 |
| markets  | seldon-laws  |       15 |         -0.016 |         3.795 |       0.537 |        0.820 |   0.250 |
| markets  | timesfm-2.5  |       15 |         -0.016 |         3.692 |       0.518 |        0.830 |   0.245 |
| news     | auto-ets     |        6 |         -0.059 |         1.444 |       0.472 |        0.911 |   0.272 |
| news     | chronos-bolt |        6 |          0.082 |         1.269 |       0.653 |        0.739 |   0.224 |
| news     | drift        |        6 |         -0.007 |         1.382 |       0.528 |        0.860 |   0.255 |
| news     | ensemble     |        6 |          0.117 |         1.262 |       0.583 |        0.855 |   0.245 |
| news     | mean         |        6 |         -0.103 |         1.546 |       0.597 |        0.655 |   0.243 |
| news     | naive        |        6 |          0.000 |         1.371 |     nan     |        0.865 |   0.250 |
| news     | radiant      |        6 |          0.142 |         1.291 |       0.667 |        0.792 |   0.218 |
| news     | radiant-core |        6 |          0.029 |         1.346 |       0.611 |        0.792 |   0.245 |
| news     | seldon       |        6 |          0.084 |         1.302 |       0.611 |        0.782 |   0.231 |
| news     | seldon-laws  |        6 |          0.067 |         1.321 |       0.597 |        0.777 |   0.231 |
| news     | timesfm-2.5  |        6 |          0.130 |         1.286 |       0.653 |        0.778 |   0.217 |
| politics | auto-ets     |        7 |         -0.220 |         1.758 |       0.476 |        0.961 |   0.257 |
| politics | chronos-bolt |        7 |          0.096 |         1.390 |       0.619 |        0.780 |   0.220 |
| politics | drift        |        7 |         -0.009 |         1.691 |       0.405 |        0.818 |   0.259 |
| politics | ensemble     |        7 |          0.093 |         1.460 |       0.571 |        0.921 |   0.231 |
| politics | mean         |        7 |          0.043 |         1.567 |       0.619 |        0.700 |   0.244 |
| politics | naive        |        7 |          0.000 |         1.676 |     nan     |        0.820 |   0.250 |
| politics | radiant      |        7 |          0.121 |         1.333 |       0.631 |        0.804 |   0.206 |
| politics | radiant-core |        7 |          0.021 |         1.626 |       0.607 |        0.831 |   0.241 |
| politics | seldon       |        7 |          0.111 |         1.486 |       0.607 |        0.802 |   0.237 |
| politics | seldon-laws  |        7 |          0.082 |         1.540 |       0.655 |        0.810 |   0.231 |
| politics | timesfm-2.5  |        7 |          0.114 |         1.315 |       0.643 |        0.795 |   0.202 |
| tech     | auto-ets     |       16 |         -0.447 |         2.379 |       0.620 |        0.853 |   0.219 |
| tech     | bass         |        4 |         -1.038 |        60.712 |       0.333 |        0.104 |   0.566 |
| tech     | chronos-bolt |       16 |          0.353 |         0.910 |       0.698 |        0.736 |   0.192 |
| tech     | drift        |       16 |          0.022 |         1.184 |       0.609 |        0.709 |   0.204 |
| tech     | ensemble     |       16 |          0.203 |         1.218 |       0.677 |        0.871 |   0.204 |
| tech     | mean         |       16 |          0.033 |         1.256 |       0.583 |        0.564 |   0.339 |
| tech     | naive        |       16 |          0.000 |         1.318 |     nan     |        0.707 |   0.282 |
| tech     | radiant      |       16 |          0.402 |         0.869 |       0.708 |        0.784 |   0.184 |
| tech     | radiant-core |       16 |          0.016 |         1.304 |       0.581 |        0.629 |   0.240 |
| tech     | seldon       |       16 |          0.350 |         0.907 |       0.693 |        0.749 |   0.195 |
| tech     | seldon-laws  |       16 |          0.226 |         1.003 |       0.708 |        0.699 |   0.197 |
| tech     | timesfm-2.5  |       16 |          0.414 |         0.866 |       0.677 |        0.724 |   0.194 |
| weather  | auto-ets     |        9 |          0.026 |         2.287 |       0.676 |        0.866 |   0.209 |
| weather  | chronos-bolt |        9 |          0.180 |         1.594 |       0.741 |        0.774 |   0.152 |
| weather  | drift        |        9 |         -0.008 |         2.365 |       0.315 |        0.772 |   0.258 |
| weather  | ensemble     |        9 |          0.201 |         1.706 |       0.787 |        0.892 |   0.153 |
| weather  | mean         |        9 |         -0.504 |         2.725 |       0.454 |        0.524 |   0.413 |
| weather  | naive        |        9 |          0.000 |         2.346 |     nan     |        0.788 |   0.250 |
| weather  | radiant      |        9 |          0.178 |         1.597 |       0.769 |        0.796 |   0.133 |
| weather  | radiant-core |        9 |          0.052 |         2.312 |       0.731 |        0.842 |   0.225 |
| weather  | seldon       |        9 |          0.174 |         1.747 |       0.741 |        0.784 |   0.154 |
| weather  | seldon-laws  |        9 |          0.078 |         2.143 |       0.630 |        0.737 |   0.228 |
| weather  | timesfm-2.5  |        9 |          0.178 |         1.559 |       0.769 |        0.796 |   0.136 |

## 2. Seldon's law of large numbers: aggregates vs individuals

Psychohistory only claims to work for very large populations. If that holds here, aggregate series (indices, composites, world totals) should show higher skill and lower MASE than individual ones.

| domain   | scale      | model       |   series |   median_skill |   median_mase |
|:---------|:-----------|:------------|---------:|---------------:|--------------:|
| markets  | aggregate  | timesfm-2.5 |        5 |         -0.025 |         2.707 |
| markets  | individual | timesfm-2.5 |       10 |         -0.003 |         4.192 |
| news     | aggregate  | timesfm-2.5 |        1 |          0.121 |         1.447 |
| news     | individual | timesfm-2.5 |        5 |          0.138 |         1.270 |
| politics | aggregate  | timesfm-2.5 |        1 |          0.076 |         1.315 |
| politics | individual | timesfm-2.5 |        6 |          0.121 |         1.420 |
| tech     | aggregate  | timesfm-2.5 |        5 |          0.460 |         8.692 |
| tech     | individual | timesfm-2.5 |       11 |          0.371 |         0.805 |
| weather  | aggregate  | timesfm-2.5 |        4 |          0.379 |         1.781 |
| weather  | individual | timesfm-2.5 |        5 |          0.053 |         1.559 |

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
| space_launches | tech     | 2019-01-01 |        0.000 |  56.721 |
| space_launches | tech     | 2016-01-01 |        0.000 |  16.455 |
| bitcoin        | markets  | 2026-08-18 |        0.000 |   9.848 |
| sp500          | markets  | 2026-04-13 |        0.000 |   7.544 |
| space_launches | tech     | 2013-01-01 |        0.000 |   3.874 |
| nasdaq100      | markets  | 2026-04-13 |        0.048 |  11.327 |
| xom            | markets  | 2026-01-09 |        0.095 |  12.057 |
| news_pandemic  | news     | 2026-05-01 |        0.143 |   4.976 |
| wiki_quantum   | tech     | 2025-12-09 |        0.143 |   0.983 |

## 4. Prediction ledger (true out-of-sample test)

![Time Vault track record](plots/track_record.png)

_Predictions are sealed with a date before the future happens and opened when it arrives. The left line should settle near 80%; the right line should sit below the coin-flip line._

| domain   | model        |   series |   predictions |   median_skill |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|--------------:|---------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       21 |          3088 |         -0.000 |       0.555 |        0.666 |   0.260 |
| markets  | chronos-bolt |       21 |          3088 |         -0.049 |       0.500 |        0.658 |   0.257 |
| markets  | ensemble     |       21 |          3088 |         -0.014 |       0.476 |        0.673 |   0.258 |
| markets  | radiant      |       21 |          1592 |         -0.014 |       0.517 |        0.631 |   0.257 |
| markets  | radiant-core |       21 |          1592 |          0.003 |       0.621 |        0.612 |   0.248 |
| markets  | seldon       |       21 |          1592 |         -0.010 |       0.528 |        0.577 |   0.267 |
| markets  | seldon-laws  |       21 |          2570 |         -0.022 |       0.374 |        0.588 |   0.267 |
| markets  | timesfm-2.5  |       21 |          3088 |         -0.030 |       0.473 |        0.677 |   0.271 |
| news     | auto-ets     |        7 |          1530 |         -0.128 |       0.490 |        0.828 |   0.263 |
| news     | chronos-bolt |        7 |          1530 |          0.352 |       0.753 |        0.649 |   0.170 |
| news     | ensemble     |        7 |          1530 |          0.236 |       0.737 |        0.786 |   0.178 |
| news     | radiant      |        7 |           828 |          0.388 |       0.758 |        0.674 |   0.165 |
| news     | radiant-core |        7 |           828 |          0.039 |       0.620 |        0.550 |   0.235 |
| news     | seldon       |        7 |           828 |          0.392 |       0.760 |        0.675 |   0.165 |
| news     | seldon-laws  |        7 |          1332 |          0.141 |       0.692 |        0.569 |   0.194 |
| news     | timesfm-2.5  |        7 |          1530 |          0.342 |       0.744 |        0.670 |   0.171 |
| politics | auto-ets     |        7 |           548 |         -0.280 |       0.494 |        0.844 |   0.257 |
| politics | chronos-bolt |        7 |           548 |          0.143 |       0.730 |        0.752 |   0.177 |
| politics | ensemble     |        7 |           548 |          0.122 |       0.712 |        0.827 |   0.187 |
| politics | radiant      |        7 |           548 |          0.195 |       0.703 |        0.739 |   0.175 |
| politics | radiant-core |        7 |           548 |          0.021 |       0.692 |        0.716 |   0.241 |
| politics | seldon       |        7 |           548 |          0.175 |       0.721 |        0.748 |   0.173 |
| politics | seldon-laws  |        7 |           548 |          0.120 |       0.703 |        0.675 |   0.196 |
| politics | timesfm-2.5  |        7 |           548 |          0.194 |       0.707 |        0.772 |   0.172 |
| tech     | auto-ets     |       14 |          2884 |          0.006 |       0.670 |        0.954 |   0.214 |
| tech     | chronos-bolt |       14 |          2884 |          0.376 |       0.801 |        0.767 |   0.140 |
| tech     | ensemble     |       14 |          2884 |          0.311 |       0.758 |        0.940 |   0.148 |
| tech     | radiant      |       14 |          1564 |          0.424 |       0.805 |        0.746 |   0.136 |
| tech     | radiant-core |       14 |          1564 |          0.035 |       0.731 |        0.677 |   0.236 |
| tech     | seldon       |       14 |          1564 |          0.398 |       0.809 |        0.787 |   0.137 |
| tech     | seldon-laws  |       14 |          2436 |          0.273 |       0.796 |        0.797 |   0.136 |
| tech     | timesfm-2.5  |       14 |          2884 |          0.408 |       0.801 |        0.685 |   0.139 |
| weather  | auto-ets     |       16 |           779 |         -0.022 |       0.686 |        0.903 |   0.257 |
| weather  | chronos-bolt |       16 |           779 |          0.003 |       0.787 |        0.799 |   0.239 |
| weather  | ensemble     |       16 |           779 |         -0.004 |       0.783 |        0.884 |   0.234 |
| weather  | radiant      |       16 |           779 |          0.251 |       0.748 |        0.827 |   0.244 |
| weather  | radiant-core |       16 |           779 |          0.000 |       0.665 |        0.871 |   0.235 |
| weather  | seldon       |       16 |           779 |          0.003 |       0.786 |        0.812 |   0.240 |
| weather  | seldon-laws  |       16 |           779 |         -0.010 |       0.667 |        0.782 |   0.299 |
| weather  | timesfm-2.5  |       16 |           779 |          0.256 |       0.747 |        0.820 |   0.243 |

## 5. How far ahead can it see?

Median skill versus the naive baseline by how many steps ahead the forecast is (days for news and tech attention, trading days for markets; yearly adoption series are too short for this and are left out). Where skill drops to zero is the limit of the model's foresight in that domain.

![Skill by step](plots/skill_by_step.png)

| domain   |   1 step |    2-5 |   6-10 |   11-20 |     21+ |
|:---------|---------:|-------:|-------:|--------:|--------:|
| markets  |   -0.010 | -0.003 |  0.015 |  -0.015 |  -0.012 |
| news     |    0.179 | -0.024 |  0.132 |   0.075 |   0.135 |
| politics |    0.154 |  0.208 |  0.120 |   0.174 |   0.082 |
| tech     |   -0.005 |  0.361 |  0.210 |   0.343 |   0.287 |
| weather  |    0.164 |  0.142 |  0.192 |   0.296 | nan     |

## 6. Are its odds honest?

Backtest forecasts grouped by the chance they gave of the series ending higher. `said` is the average probability given, `happened` is how often it really went up. When the two match, the odds can be taken at face value.

| domain   | odds given   |   forecasts |   said |   happened |
|:---------|:-------------|------------:|-------:|-----------:|
| markets  | 20%-40%      |          13 |  0.360 |      0.615 |
| markets  | 40%-60%      |         134 |  0.491 |      0.463 |
| markets  | 60%-80%      |          33 |  0.657 |      0.758 |
| news     | 0%-20%       |          11 |  0.129 |      0.364 |
| news     | 20%-40%      |          19 |  0.339 |      0.263 |
| news     | 40%-60%      |          20 |  0.487 |      0.450 |
| news     | 60%-80%      |          17 |  0.699 |      0.765 |
| news     | 80%-100%     |           5 |  0.838 |      0.800 |
| politics | 0%-20%       |          11 |  0.121 |      0.091 |
| politics | 20%-40%      |          21 |  0.325 |      0.381 |
| politics | 40%-60%      |          25 |  0.505 |      0.400 |
| politics | 60%-80%      |          21 |  0.698 |      0.762 |
| politics | 80%-100%     |           6 |  0.860 |      0.833 |
| tech     | 0%-20%       |          22 |  0.124 |      0.318 |
| tech     | 20%-40%      |          36 |  0.308 |      0.194 |
| tech     | 40%-60%      |          41 |  0.498 |      0.463 |
| tech     | 60%-80%      |          50 |  0.697 |      0.640 |
| tech     | 80%-100%     |          32 |  0.888 |      0.875 |
| weather  | 0%-20%       |          38 |  0.096 |      0.053 |
| weather  | 20%-40%      |          15 |  0.288 |      0.267 |
| weather  | 40%-60%      |          19 |  0.503 |      0.632 |
| weather  | 60%-80%      |          17 |  0.689 |      0.706 |
| weather  | 80%-100%     |          19 |  0.908 |      0.895 |

## 7. Every series

| series_id            | domain   | scale      | model       |      mae |   mase |   smape |   direction |   coverage80 |   pinball |   brier |   skill |   prob_skill |
|:---------------------|:---------|:-----------|:------------|---------:|-------:|--------:|------------:|-------------:|----------:|--------:|--------:|-------------:|
| aapl                 | markets  | individual | timesfm-2.5 |    8.705 |  3.692 |   0.030 |       0.500 |        0.849 |     1.449 |   0.250 |   0.025 |        0.022 |
| adoption_internet    | tech     | aggregate  | timesfm-2.5 |    2.341 |  0.774 |   0.032 |       1.000 |        1.000 |     0.260 |   0.002 |   0.460 |        0.526 |
| adoption_solar       | tech     | aggregate  | timesfm-2.5 |    0.254 | 64.139 |   0.421 |       0.750 |        0.417 |    27.337 |   0.197 |   0.441 |        0.282 |
| adoption_wind        | tech     | aggregate  | timesfm-2.5 |    0.165 | 31.187 |   0.249 |       0.833 |        0.694 |    12.482 |   0.124 |   0.646 |        0.416 |
| bitcoin              | markets  | individual | timesfm-2.5 | 5639.103 |  4.417 |   0.076 |       0.417 |        0.815 |     1.696 |   0.251 |  -0.016 |        0.015 |
| copper               | markets  | individual | timesfm-2.5 |    0.179 |  3.317 |   0.030 |       0.583 |        0.889 |     1.351 |   0.246 |   0.048 |       -0.009 |
| gold                 | markets  | individual | timesfm-2.5 |  167.546 |  7.290 |   0.037 |       0.333 |        0.821 |     2.911 |   0.258 |   0.017 |        0.087 |
| msci_world           | markets  | aggregate  | timesfm-2.5 |    2.643 |  2.707 |   0.014 |       0.750 |        0.798 |     1.049 |   0.179 |   0.012 |        0.024 |
| nasdaq100            | markets  | aggregate  | timesfm-2.5 |  765.631 |  4.237 |   0.028 |       0.667 |        0.750 |     1.708 |   0.207 |  -0.025 |        0.014 |
| news_climate         | news     | individual | timesfm-2.5 |    0.128 |  0.972 |   0.156 |       0.750 |        0.780 |     0.383 |   0.152 |   0.184 |        0.174 |
| news_composite       | news     | aggregate  | timesfm-2.5 |    0.117 |  1.447 |   0.139 |       0.750 |        0.786 |     0.577 |   0.174 |   0.121 |        0.118 |
| news_election        | news     | individual | timesfm-2.5 |    0.641 |  1.302 |   0.133 |       0.667 |        0.812 |     0.540 |   0.226 |   0.138 |        0.140 |
| news_inflation       | news     | individual | timesfm-2.5 |    0.308 |  1.009 |   0.156 |       0.500 |        0.783 |     0.390 |   0.324 |   0.182 |        0.199 |
| news_pandemic        | news     | individual | timesfm-2.5 |    0.234 |  1.270 |   0.116 |       0.583 |        0.741 |     0.520 |   0.250 |  -0.084 |       -0.062 |
| news_protest         | news     | individual | timesfm-2.5 |    0.475 |  1.612 |   0.200 |       0.667 |        0.765 |     0.654 |   0.174 |   0.066 |        0.076 |
| nvda                 | markets  | individual | timesfm-2.5 |    8.059 |  3.982 |   0.040 |       0.500 |        0.869 |     1.631 |   0.259 |   0.009 |       -0.006 |
| oil_wti              | markets  | individual | timesfm-2.5 |    6.286 |  4.409 |   0.075 |       0.500 |        0.806 |     1.690 |   0.227 |  -0.025 |        0.050 |
| politics_ceasefire   | politics | individual | timesfm-2.5 |    0.384 |  1.943 |   0.382 |       0.583 |        0.786 |     0.828 |   0.194 |   0.039 |        0.053 |
| politics_composite   | politics | aggregate  | timesfm-2.5 |    0.143 |  1.315 |   0.178 |       0.750 |        0.812 |     0.517 |   0.160 |   0.076 |        0.098 |
| politics_coup        | politics | individual | timesfm-2.5 |    0.085 |  0.819 |   0.218 |       0.417 |        0.777 |     0.330 |   0.296 |   0.131 |        0.179 |
| politics_impeachment | politics | individual | timesfm-2.5 |    0.073 |  0.924 |   0.261 |       0.750 |        0.839 |     0.389 |   0.166 |   0.114 |        0.149 |
| politics_referendum  | politics | individual | timesfm-2.5 |    0.119 |  1.531 |   0.296 |       0.583 |        0.783 |     0.626 |   0.202 |   0.087 |        0.118 |
| politics_sanctions   | politics | individual | timesfm-2.5 |    0.267 |  1.615 |   0.212 |       0.667 |        0.789 |     0.628 |   0.183 |   0.127 |        0.146 |
| politics_tariffs     | politics | individual | timesfm-2.5 |    0.302 |  1.309 |   0.211 |       0.750 |        0.780 |     0.546 |   0.212 |   0.317 |        0.284 |
| quakes_m45           | weather  | aggregate  | timesfm-2.5 |    7.724 |  0.953 |   0.313 |       0.750 |        0.750 |     0.386 |   0.142 |   0.178 |        0.181 |
| silver               | markets  | individual | timesfm-2.5 |    6.228 | 10.918 |   0.087 |       0.583 |        0.786 |     4.325 |   0.245 |   0.010 |        0.141 |
| sp500                | markets  | aggregate  | timesfm-2.5 |  107.505 |  2.841 |   0.015 |       0.583 |        0.798 |     1.129 |   0.223 |   0.036 |        0.035 |
| space_launches       | tech     | aggregate  | timesfm-2.5 |  218.395 |  8.692 |   0.333 |       0.250 |        0.556 |     3.938 |   0.353 |   0.026 |        0.045 |
| tech_composite       | tech     | aggregate  | timesfm-2.5 |    0.066 |  0.642 |   0.081 |       0.667 |        0.753 |     0.259 |   0.165 |   0.467 |        0.447 |
| tlt                  | markets  | individual | timesfm-2.5 |    0.921 |  1.387 |   0.011 |       0.417 |        0.885 |     0.553 |   0.266 |  -0.016 |        0.172 |
| tsla                 | markets  | individual | timesfm-2.5 |   23.710 |  3.161 |   0.062 |       0.750 |        0.865 |     1.257 |   0.246 |  -0.016 |       -0.039 |
| us10y                | markets  | aggregate  | timesfm-2.5 |    0.093 |  1.887 |   0.020 |       0.273 |        0.845 |     0.731 |   0.285 |  -0.106 |        0.051 |
| vix                  | markets  | aggregate  | timesfm-2.5 |    1.906 |  1.829 |   0.101 |       0.583 |        0.865 |     0.729 |   0.242 |  -0.072 |       -0.005 |
| weather_arctic_ice   | weather  | aggregate  | timesfm-2.5 |    0.106 |  1.521 |   0.016 |       1.000 |        0.863 |     0.601 |   0.006 |   0.793 |        0.764 |
| weather_london       | weather  | individual | timesfm-2.5 |    2.976 |  1.559 |   0.137 |       0.833 |        0.774 |     0.592 |   0.112 |   0.410 |        0.439 |
| weather_los_angeles  | weather  | individual | timesfm-2.5 |    2.750 |  1.580 |   0.091 |       0.583 |        0.762 |     0.624 |   0.180 |   0.053 |        0.045 |
| weather_new_delhi    | weather  | individual | timesfm-2.5 |    2.035 |  1.669 |   0.061 |       0.583 |        0.833 |     0.664 |   0.240 |   0.286 |        0.281 |
| weather_sydney       | weather  | individual | timesfm-2.5 |    2.338 |  1.019 |   0.111 |       0.750 |        0.804 |     0.392 |   0.159 |   0.022 |        0.106 |
| weather_tokyo        | weather  | individual | timesfm-2.5 |    3.372 |  1.492 |   0.127 |       0.833 |        0.637 |     0.573 |   0.143 |   0.052 |        0.060 |
| weather_world_air    | weather  | aggregate  | timesfm-2.5 |    0.082 |  2.042 |   0.005 |       0.917 |        0.869 |     0.774 |   0.087 |   0.581 |        0.573 |
| weather_world_sea    | weather  | aggregate  | timesfm-2.5 |    0.021 |  3.078 |   0.001 |       0.667 |        0.869 |     1.141 |   0.154 |   0.108 |        0.161 |
| wiki_ai              | tech     | individual | timesfm-2.5 | 1460.623 |  1.079 |   0.111 |       0.833 |        0.765 |     0.443 |   0.124 |   0.263 |        0.256 |
| wiki_battery         | tech     | individual | timesfm-2.5 |  153.006 |  1.060 |   0.200 |       0.917 |        0.798 |     0.418 |   0.163 |   0.413 |        0.479 |
| wiki_crispr          | tech     | individual | timesfm-2.5 |   89.381 |  0.594 |   0.116 |       0.583 |        0.732 |     0.238 |   0.221 |   0.324 |        0.348 |
| wiki_ev              | tech     | individual | timesfm-2.5 |   46.749 |  0.516 |   0.108 |       0.750 |        0.765 |     0.202 |   0.215 |   0.341 |        0.361 |
| wiki_fusion          | tech     | individual | timesfm-2.5 |   93.887 |  0.805 |   0.123 |       0.583 |        0.717 |     0.333 |   0.190 |   0.318 |        0.265 |
| wiki_gene_therapy    | tech     | individual | timesfm-2.5 |   27.974 |  0.491 |   0.153 |       0.667 |        0.723 |     0.197 |   0.149 |   0.371 |        0.386 |
| wiki_humanoid        | tech     | individual | timesfm-2.5 |   57.987 |  0.983 |   0.163 |       0.667 |        0.723 |     0.401 |   0.181 |   0.447 |        0.465 |
| wiki_llm             | tech     | individual | timesfm-2.5 |  307.917 |  0.567 |   0.091 |       0.833 |        0.756 |     0.232 |   0.142 |   0.513 |        0.502 |
| wiki_quantum         | tech     | individual | timesfm-2.5 |  365.001 |  0.928 |   0.135 |       0.583 |        0.750 |     0.403 |   0.241 |   0.501 |        0.486 |
| wiki_self_driving    | tech     | individual | timesfm-2.5 |   57.541 |  0.545 |   0.117 |       0.250 |        0.696 |     0.216 |   0.396 |   0.414 |        0.428 |
| wiki_starship        | tech     | individual | timesfm-2.5 |  880.775 |  0.933 |   0.281 |       0.667 |        0.738 |     0.409 |   0.247 |   0.152 |        0.130 |
| xom                  | markets  | individual | timesfm-2.5 |    5.497 |  4.403 |   0.038 |       0.333 |        0.806 |     1.794 |   0.288 |  -0.052 |       -0.043 |

## 8. What the model expects next

![What the model expects next](plots/outlook.png)

Latest forecasts recorded in the ledger (made with data up to each series' last date). Changes are relative to the last observed value; the range is the 10%-90% band; "chance higher" is the model's probability that the value on the target date is above today's (scored later with the Brier score: 0 is perfect, 0.25 is a coin flip).

### World events in the news

| series         |   last | target date   | median   | chance higher   | range (10%-90%)   |
|:---------------|-------:|:--------------|:---------|:----------------|:------------------|
| news_ai        |  2.692 | 2026-12-26    | +0.8%    | 51%             | -24.4% to +36.8%  |
| news_climate   |  0.628 | 2026-12-26    | +22.4%   | 77%             | -14.6% to +80.7%  |
| news_composite |  0.823 | 2026-12-24    | +1.3%    | 55%             | -11.0% to +20.3%  |
| news_cyber     |  0.07  | 2026-12-26    | -46.1%   | 19%             | -77.4% to +38.5%  |
| news_election  |  5.286 | 2026-12-26    | -11.7%   | 28%             | -29.4% to +23.0%  |
| news_energy    |  0.259 | 2026-12-26    | +15.1%   | 64%             | -31.9% to +98.1%  |
| news_housing   |  0.1   | 2026-12-26    | +46.3%   | 82%             | -14.1% to +147.7% |
| news_inflation |  1.97  | 2026-12-26    | -2.1%    | 46%             | -27.5% to +32.7%  |
| news_jobs      |  0.685 | 2026-12-26    | +7.1%    | 64%             | -16.5% to +39.7%  |
| news_pandemic  |  1.58  | 2026-12-26    | -0.8%    | 48%             | -17.4% to +20.5%  |
| news_protest   |  1.237 | 2026-12-24    | +22.0%   | 84%             | -4.8% to +79.0%   |
| news_war       |  0.566 | 2026-12-26    | -28.4%   | 17%             | -50.2% to +12.3%  |
| news_wildfire  |  0.54  | 2026-12-26    | +0.1%    | 50%             | -21.2% to +35.5%  |

![news_ai](plots/news_ai.png)
![news_climate](plots/news_climate.png)
![news_composite](plots/news_composite.png)
![news_cyber](plots/news_cyber.png)
![news_election](plots/news_election.png)
![news_energy](plots/news_energy.png)
![news_housing](plots/news_housing.png)
![news_inflation](plots/news_inflation.png)
![news_jobs](plots/news_jobs.png)
![news_pandemic](plots/news_pandemic.png)
![news_protest](plots/news_protest.png)
![news_war](plots/news_war.png)
![news_wildfire](plots/news_wildfire.png)

### Political events

| series               |   last | target date   | median   | chance higher   | range (10%-90%)    |
|:---------------------|-------:|:--------------|:---------|:----------------|:-------------------|
| politics_ceasefire   |  0.361 | 2026-12-25    | +13.5%   | 60%             | -40.7% to +141.2%  |
| politics_composite   |  0.842 | 2026-12-25    | +0.5%    | 51%             | -21.4% to +47.3%   |
| politics_coup        |  0.243 | 2026-12-26    | +13.8%   | 69%             | -16.8% to +92.9%   |
| politics_immigration |  1.416 | 2026-12-26    | -6.1%    | 40%             | -31.8% to +41.9%   |
| politics_impeachment |  0.176 | 2026-12-26    | +9.2%    | 61%             | -29.2% to +96.8%   |
| politics_nato        |  0.624 | 2026-12-26    | +29.0%   | 74%             | -20.7% to +138.3%  |
| politics_referendum  |  0.371 | 2026-12-26    | -15.9%   | 32%             | -41.6% to +51.1%   |
| politics_sanctions   |  1.112 | 2026-12-26    | -0.4%    | 49%             | -27.3% to +46.4%   |
| politics_summits     |  0.014 | 2026-12-26    | +49.5%   | 58%             | -153.1% to +725.0% |
| politics_tariffs     |  1.541 | 2026-12-26    | -31.0%   | 19%             | -54.8% to +24.2%   |
| politics_un          |  0.746 | 2026-12-26    | +10.1%   | 65%             | -19.1% to +70.5%   |

![politics_ceasefire](plots/politics_ceasefire.png)
![politics_composite](plots/politics_composite.png)
![politics_coup](plots/politics_coup.png)
![politics_immigration](plots/politics_immigration.png)
![politics_impeachment](plots/politics_impeachment.png)
![politics_nato](plots/politics_nato.png)
![politics_referendum](plots/politics_referendum.png)
![politics_sanctions](plots/politics_sanctions.png)
![politics_summits](plots/politics_summits.png)
![politics_tariffs](plots/politics_tariffs.png)
![politics_un](plots/politics_un.png)

### Stock and value markets

| series     |      last | target date   | median   | chance higher   | range (10%-90%)   |
|:-----------|----------:|:--------------|:---------|:----------------|:------------------|
| aapl       |   358.54  | 2026-12-28    | +0.3%    | 52%             | -6.2% to +5.3%    |
| amd        |   424.54  | 2026-12-28    | -2.8%    | 45%             | -25.9% to +31.6%  |
| amzn       |   254.12  | 2026-12-28    | +0.1%    | 50%             | -9.8% to +9.1%    |
| audusd     |     0.665 | 2026-12-28    | +0.1%    | 51%             | -2.9% to +3.4%    |
| bitcoin    | 59437.9   | 2026-12-26    | -1.2%    | 46%             | -17.1% to +20.1%  |
| brk        |   580.79  | 2026-12-28    | +0.3%    | 52%             | -6.1% to +8.1%    |
| cocoa      |  5385     | 2026-12-28    | -1.1%    | 47%             | -18.6% to +20.3%  |
| copper     |     5.517 | 2026-12-28    | -3.2%    | 36%             | -15.8% to +8.9%   |
| corn       |   446.75  | 2026-12-28    | +0.9%    | 56%             | -7.0% to +11.7%   |
| dax        | 25441.2   | 2026-12-28    | +1.7%    | 67%             | -3.0% to +5.9%    |
| ethereum   |  1647.53  | 2026-12-26    | -0.4%    | 49%             | -24.4% to +37.0%  |
| eurusd     |     1.097 | 2026-12-28    | +0.0%    | 51%             | -2.3% to +2.7%    |
| ftse       | 10698.8   | 2026-12-28    | +1.2%    | 66%             | -2.3% to +4.2%    |
| gbpusd     |     1.311 | 2026-12-28    | +0.1%    | 53%             | -2.1% to +2.4%    |
| gold       |  3639.6   | 2026-12-28    | -0.1%    | 49%             | -9.1% to +11.3%   |
| googl      |   274.96  | 2026-12-28    | -1.1%    | 46%             | -13.7% to +12.2%  |
| hsi        | 22694.8   | 2026-12-28    | +0.2%    | 51%             | -7.9% to +9.3%    |
| intc       |    57.4   | 2026-12-28    | -1.4%    | 48%             | -29.5% to +50.7%  |
| jpm        |   322.96  | 2026-12-28    | +1.0%    | 58%             | -6.1% to +7.6%    |
| ko         |    97.4   | 2026-12-28    | -0.4%    | 46%             | -6.5% to +6.6%    |
| meta       |   628.96  | 2026-12-28    | +2.3%    | 58%             | -12.8% to +17.6%  |
| msci_world |   197.66  | 2026-12-28    | +2.9%    | 77%             | -2.4% to +6.9%    |
| msft       |   492.85  | 2026-12-28    | -1.0%    | 45%             | -11.6% to +8.7%   |
| nasdaq100  | 26726.4   | 2026-12-28    | +1.7%    | 60%             | -9.1% to +10.6%   |
| natgas     |     3.491 | 2026-12-28    | +1.5%    | 53%             | -17.8% to +31.4%  |
| nflx       |    60.93  | 2026-12-28    | -0.9%    | 47%             | -15.5% to +17.2%  |
| nikkei     | 58711.1   | 2026-12-28    | +0.9%    | 54%             | -9.9% to +12.3%   |
| nvda       |   150.49  | 2026-12-28    | +0.1%    | 50%             | -26.8% to +26.6%  |
| oil_wti    |    83.08  | 2026-12-28    | -1.3%    | 45%             | -13.8% to +14.8%  |
| platinum   |  1313.9   | 2026-12-28    | -1.5%    | 43%             | -12.4% to +12.4%  |
| silver     |    43.167 | 2026-12-28    | -1.2%    | 46%             | -14.2% to +16.0%  |
| solana     |    70.46  | 2026-12-26    | +0.4%    | 51%             | -20.9% to +30.7%  |
| soybeans   |  1266.25  | 2026-12-28    | +0.1%    | 51%             | -6.8% to +7.8%    |
| sp500      |  7297.49  | 2026-12-28    | +2.4%    | 71%             | -3.7% to +6.9%    |
| tlt        |    81.27  | 2026-12-28    | +1.2%    | 70%             | -1.8% to +4.0%    |
| tsla       |   400     | 2026-12-28    | -1.4%    | 45%             | -16.9% to +14.1%  |
| us10y      |     4.936 | 2026-12-28    | -0.3%    | 47%             | -6.5% to +6.5%    |
| usdjpy     |   159.515 | 2026-12-28    | +0.4%    | 62%             | -1.6% to +1.8%    |
| visa       |   429.56  | 2026-12-28    | -0.2%    | 48%             | -7.2% to +6.3%    |
| vix        |    23.81  | 2026-12-28    | -18.3%   | 20%             | -36.4% to +14.8%  |
| wheat      |   566.5   | 2026-12-28    | +1.6%    | 60%             | -5.8% to +12.6%   |
| wmt        |   133.13  | 2026-12-28    | +0.1%    | 51%             | -8.5% to +8.1%    |
| xom        |   160.18  | 2026-12-28    | -0.1%    | 49%             | -9.9% to +10.9%   |
| xrp        |     0.938 | 2026-12-26    | -2.5%    | 42%             | -18.3% to +27.7%  |

![aapl](plots/aapl.png)
![amd](plots/amd.png)
![amzn](plots/amzn.png)
![audusd](plots/audusd.png)
![bitcoin](plots/bitcoin.png)
![brk](plots/brk.png)
![cocoa](plots/cocoa.png)
![copper](plots/copper.png)
![corn](plots/corn.png)
![dax](plots/dax.png)
![ethereum](plots/ethereum.png)
![eurusd](plots/eurusd.png)
![ftse](plots/ftse.png)
![gbpusd](plots/gbpusd.png)
![gold](plots/gold.png)
![googl](plots/googl.png)
![hsi](plots/hsi.png)
![intc](plots/intc.png)
![jpm](plots/jpm.png)
![ko](plots/ko.png)
![meta](plots/meta.png)
![msci_world](plots/msci_world.png)
![msft](plots/msft.png)
![nasdaq100](plots/nasdaq100.png)
![natgas](plots/natgas.png)
![nflx](plots/nflx.png)
![nikkei](plots/nikkei.png)
![nvda](plots/nvda.png)
![oil_wti](plots/oil_wti.png)
![platinum](plots/platinum.png)
![silver](plots/silver.png)
![solana](plots/solana.png)
![soybeans](plots/soybeans.png)
![sp500](plots/sp500.png)
![tlt](plots/tlt.png)
![tsla](plots/tsla.png)
![us10y](plots/us10y.png)
![usdjpy](plots/usdjpy.png)
![visa](plots/visa.png)
![vix](plots/vix.png)
![wheat](plots/wheat.png)
![wmt](plots/wmt.png)
![xom](plots/xom.png)
![xrp](plots/xrp.png)

### New technologies

| series             |      last | target date   | median   | chance higher   | range (10%-90%)   |
|:-------------------|----------:|:--------------|:---------|:----------------|:------------------|
| adoption_ev        |    25     | 2028-01-01    | +11.9%   | 71%             | -20.4% to +38.9%  |
| adoption_internet  |    73.6   | 2028-01-01    | +5.8%    | 79%             | -2.9% to +19.5%   |
| adoption_solar     |     8.745 | 2028-01-01    | +49.5%   | 95%             | +15.3% to +94.2%  |
| adoption_wind      |     8.539 | 2028-01-01    | +6.9%    | 73%             | -9.3% to +22.4%   |
| space_launches     |  4510     | 2028-01-01    | -37.8%   | 11%             | -68.1% to +1.7%   |
| tech_composite     |     0.612 | 2026-12-25    | -10.0%   | 20%             | -22.1% to +6.5%   |
| wiki_6g            |   432     | 2026-12-25    | +8.2%    | 72%             | -7.7% to +42.8%   |
| wiki_ai            | 11619     | 2026-12-25    | -17.4%   | 14%             | -32.0% to +3.2%   |
| wiki_ar            |   363     | 2026-12-25    | -23.6%   | 5%              | -39.6% to -4.1%   |
| wiki_battery       |   232     | 2026-12-25    | +7.0%    | 62%             | -18.6% to +66.2%  |
| wiki_crispr        |   427     | 2026-12-25    | -9.3%    | 30%             | -33.3% to +19.2%  |
| wiki_cultured_meat |   279     | 2026-12-25    | -6.2%    | 38%             | -26.2% to +33.9%  |
| wiki_drones        |   760     | 2026-12-25    | -0.9%    | 46%             | -16.2% to +21.4%  |
| wiki_ev            |   306     | 2026-12-25    | -0.2%    | 49%             | -16.1% to +21.1%  |
| wiki_fusion        |   443     | 2026-12-25    | +15.2%   | 78%             | -9.4% to +54.1%   |
| wiki_gene_therapy  |   109     | 2026-12-25    | -12.8%   | 26%             | -34.6% to +16.6%  |
| wiki_humanoid      |   278     | 2026-12-25    | -18.7%   | 17%             | -34.0% to +8.8%   |
| wiki_llm           |  3126     | 2026-12-25    | -25.7%   | 5%              | -37.1% to -11.8%  |
| wiki_mrna          |   167     | 2026-12-25    | +10.8%   | 69%             | -14.0% to +58.8%  |
| wiki_neuralink     |   996     | 2026-12-25    | -9.6%    | 35%             | -31.1% to +50.6%  |
| wiki_quantum       |  1638     | 2026-12-25    | -7.8%    | 31%             | -22.2% to +20.3%  |
| wiki_self_driving  |   392     | 2026-12-25    | -16.7%   | 15%             | -32.8% to +4.0%   |
| wiki_semaglutide   |  1061     | 2026-12-25    | -4.1%    | 36%             | -20.6% to +25.0%  |
| wiki_smr           |   298     | 2026-12-25    | -9.4%    | 32%             | -33.7% to +24.6%  |
| wiki_starship      |  1469     | 2026-12-25    | +2.3%    | 54%             | -19.8% to +85.8%  |
| wiki_vr            |   410     | 2026-12-25    | -6.2%    | 30%             | -22.2% to +12.9%  |

![adoption_ev](plots/adoption_ev.png)
![adoption_internet](plots/adoption_internet.png)
![adoption_solar](plots/adoption_solar.png)
![adoption_wind](plots/adoption_wind.png)
![space_launches](plots/space_launches.png)
![tech_composite](plots/tech_composite.png)
![wiki_6g](plots/wiki_6g.png)
![wiki_ai](plots/wiki_ai.png)
![wiki_ar](plots/wiki_ar.png)
![wiki_battery](plots/wiki_battery.png)
![wiki_crispr](plots/wiki_crispr.png)
![wiki_cultured_meat](plots/wiki_cultured_meat.png)
![wiki_drones](plots/wiki_drones.png)
![wiki_ev](plots/wiki_ev.png)
![wiki_fusion](plots/wiki_fusion.png)
![wiki_gene_therapy](plots/wiki_gene_therapy.png)
![wiki_humanoid](plots/wiki_humanoid.png)
![wiki_llm](plots/wiki_llm.png)
![wiki_mrna](plots/wiki_mrna.png)
![wiki_neuralink](plots/wiki_neuralink.png)
![wiki_quantum](plots/wiki_quantum.png)
![wiki_self_driving](plots/wiki_self_driving.png)
![wiki_semaglutide](plots/wiki_semaglutide.png)
![wiki_smr](plots/wiki_smr.png)
![wiki_starship](plots/wiki_starship.png)
![wiki_vr](plots/wiki_vr.png)

### Weather and the planet

| series              |   last | target date   | median   | chance higher   | range (10%-90%)    |
|:--------------------|-------:|:--------------|:---------|:----------------|:-------------------|
| quakes_m45          |  7     | 2026-12-11    | +85.3%   | 95%             | +5.5% to +230.1%   |
| rain_cape_town      |  0.8   | 2026-12-11    | -91.3%   | 16%             | -92.3% to +65.9%   |
| rain_london         |  0.6   | 2026-12-11    | -45.9%   | 45%             | -184.5% to +732.1% |
| rain_los_angeles    |  0     | 2026-12-11    | +inf%    | 56%             | -inf% to +inf%     |
| rain_mumbai         |  0     | 2026-12-11    | +inf%    | 51%             | -inf% to +inf%     |
| rain_new_delhi      |  0     | 2026-12-11    | +inf%    | 54%             | -inf% to +inf%     |
| rain_new_york       | 10.4   | 2026-12-11    | -97.8%   | 5%              | -103.8% to -21.9%  |
| rain_paris          |  0     | 2026-12-11    | +inf%    | 54%             | -inf% to +inf%     |
| rain_sao_paulo      |  2.2   | 2026-12-11    | +148.1%  | 68%             | -155.3% to +873.3% |
| rain_singapore      | 18.7   | 2026-12-11    | -69.3%   | 15%             | -104.4% to +20.2%  |
| rain_sydney         |  6.1   | 2026-12-11    | -88.5%   | 16%             | -114.2% to +30.9%  |
| rain_tokyo          |  6.4   | 2026-12-11    | -95.6%   | 5%              | -96.8% to -3.9%    |
| weather_arctic_ice  |  9.549 | 2026-12-11    | +15.0%   | 95%             | +11.8% to +19.3%   |
| weather_cape_town   | 23     | 2026-12-11    | +10.1%   | 76%             | -6.8% to +37.2%    |
| weather_london      |  5.2   | 2026-12-11    | +53.2%   | 83%             | -13.0% to +134.8%  |
| weather_los_angeles | 29.2   | 2026-12-11    | -27.4%   | 5%              | -42.7% to -8.4%    |
| weather_mumbai      | 32.8   | 2026-12-11    | +3.1%    | 70%             | -4.6% to +10.2%    |
| weather_new_delhi   | 24.6   | 2026-12-11    | -10.6%   | 5%              | -23.0% to -1.3%    |
| weather_new_york    | 14     | 2026-12-11    | -49.5%   | 11%             | -97.3% to +1.0%    |
| weather_paris       |  2.8   | 2026-12-11    | +180.1%  | 95%             | +26.8% to +361.3%  |
| weather_sao_paulo   | 23.2   | 2026-12-11    | +19.2%   | 85%             | -4.7% to +38.2%    |
| weather_singapore   | 31.7   | 2026-12-11    | +0.9%    | 59%             | -5.8% to +5.0%     |
| weather_sydney      | 25.5   | 2026-12-11    | +2.9%    | 57%             | -16.5% to +30.7%   |
| weather_tokyo       | 15.4   | 2026-12-11    | -20.4%   | 18%             | -47.8% to +7.9%    |
| weather_world_air   | 14.484 | 2026-12-06    | -4.0%    | 5%              | -6.5% to -2.1%     |
| weather_world_sea   | 20.997 | 2026-11-26    | -0.1%    | 35%             | -0.4% to +0.2%     |

![quakes_m45](plots/quakes_m45.png)
![rain_cape_town](plots/rain_cape_town.png)
![rain_london](plots/rain_london.png)
![rain_los_angeles](plots/rain_los_angeles.png)
![rain_mumbai](plots/rain_mumbai.png)
![rain_new_delhi](plots/rain_new_delhi.png)
![rain_new_york](plots/rain_new_york.png)
![rain_paris](plots/rain_paris.png)
![rain_sao_paulo](plots/rain_sao_paulo.png)
![rain_singapore](plots/rain_singapore.png)
![rain_sydney](plots/rain_sydney.png)
![rain_tokyo](plots/rain_tokyo.png)
![weather_arctic_ice](plots/weather_arctic_ice.png)
![weather_cape_town](plots/weather_cape_town.png)
![weather_london](plots/weather_london.png)
![weather_los_angeles](plots/weather_los_angeles.png)
![weather_mumbai](plots/weather_mumbai.png)
![weather_new_delhi](plots/weather_new_delhi.png)
![weather_new_york](plots/weather_new_york.png)
![weather_paris](plots/weather_paris.png)
![weather_sao_paulo](plots/weather_sao_paulo.png)
![weather_singapore](plots/weather_singapore.png)
![weather_sydney](plots/weather_sydney.png)
![weather_tokyo](plots/weather_tokyo.png)
![weather_world_air](plots/weather_world_air.png)
![weather_world_sea](plots/weather_world_sea.png)

## 9. The long-term monitor

Every sealed forecast that has come due, scored against what really happened. Unlike the backtest, none of these could have been fitted to the outcome. Run `psychohistory monitor` for the same in the terminal; the app's Monitor view draws it month by month.

| Model | Forecasts | Weekly batches | Skill vs "no change" | In 80% range | Right direction | Brier |
|---|---|---|---|---|---|---|
| auto-ets | 8829 | 15 | -0.1% | 79% | 51% | 0.248 |
| chronos-bolt | 8829 | 15 | +11.4% | 66% | 67% | 0.195 |
| ensemble | 8829 | 15 | +5.8% | 77% | 63% | 0.201 |
| radiant | 5311 | 9 | +14.5% | 67% | 69% | 0.188 |
| radiant-core | 5311 | 9 | +1.5% | 64% | 66% | 0.238 |
| seldon | 5311 | 9 | +8.2% | 67% | 68% | 0.192 |
| seldon-laws | 7665 | 13 | +5.8% | 64% | 59% | 0.210 |
| timesfm-2.5 | 8829 | 15 | +12.8% | 65% | 67% | 0.199 |

**Is timesfm-2.5 really better than "no change"?** A Diebold-Mariano test on the weekly batches (Newey-West variance, as the batches' horizons overlap, with the Harvey-Leybourne-Newbold small-sample correction and Student's t):

- All areas: better than no change (p = 0.00)
- Stock and value markets: not distinguishable from no change (p = 0.14)
- World events in the news: better than no change (p = 0.02)
- Political events: not distinguishable from no change (p = 0.06)
- New technologies: better than no change (p = 0.00)
- Weather and the planet: not distinguishable from no change (p = 0.63)

**Drift alarms** (forecasts due in the last 13 weeks): 204 raised. Every forecaster is tested on every series at once, so alarms must pass a Benjamini-Hochberg false-discovery cut of 5%.
- auto-ets on news_composite: edge lost
- auto-ets on news_inflation: edge lost
- auto-ets on politics_sanctions: range too wide
- auto-ets on weather_new_delhi: range too wide
- auto-ets on weather_new_delhi: edge lost
- auto-ets on weather_world_sea: edge lost
- chronos-bolt on politics_referendum: edge lost
- chronos-bolt on us10y: edge lost
- chronos-bolt on weather_arctic_ice: edge lost
- chronos-bolt on weather_london: edge lost
- chronos-bolt on weather_world_sea: edge lost
- chronos-bolt on wiki_crispr: edge lost
- ensemble on politics_sanctions: edge lost
- ensemble on quakes_m45: edge lost
- ensemble on weather_london: edge lost
- ensemble on weather_new_delhi: range too wide
- ensemble on weather_world_sea: edge lost
- ensemble on wiki_battery: edge lost
- ensemble on wiki_humanoid: edge lost
- radiant on weather_london: edge lost
- radiant on weather_world_sea: edge lost
- radiant on wiki_crispr: edge lost
- radiant-core on politics_sanctions: edge lost
- radiant-core on weather_london: edge lost
- seldon on weather_arctic_ice: edge lost
- seldon on weather_london: edge lost
- seldon on weather_world_sea: edge lost
- seldon on wiki_crispr: edge lost
- seldon-laws on politics_sanctions: edge lost
- seldon-laws on weather_arctic_ice: range too wide
- seldon-laws on weather_london: edge lost
- seldon-laws on weather_new_delhi: edge lost
- seldon-laws on wiki_crispr: edge lost
- timesfm-2.5 on sp500: edge lost
- timesfm-2.5 on weather_london: edge lost
- timesfm-2.5 on weather_world_sea: edge lost
- timesfm-2.5 on wiki_crispr: edge lost
- timesfm-2.5 on wiki_ev: edge lost
- auto-ets on aapl: range too wide
- auto-ets on copper: range too narrow
- auto-ets on gold: range too narrow
- auto-ets on gold: worse than no change
- auto-ets on msci_world: range too narrow
- auto-ets on msci_world: worse than no change
- auto-ets on nasdaq100: range too narrow
- auto-ets on news_inflation: range too wide
- auto-ets on news_pandemic: range too wide
- auto-ets on news_protest: range too wide
- auto-ets on news_protest: worse than no change
- auto-ets on nvda: range too narrow
- auto-ets on politics_ceasefire: range too wide
- auto-ets on politics_coup: range too wide
- auto-ets on politics_referendum: range too wide
- auto-ets on quakes_m45: range too wide
- auto-ets on silver: range too narrow
- auto-ets on sp500: range too narrow
- auto-ets on sp500: worse than no change
- auto-ets on tech_composite: range too wide
- auto-ets on weather_london: range too wide
- auto-ets on wiki_ai: range too wide
- auto-ets on wiki_battery: range too wide
- auto-ets on wiki_crispr: range too wide
- auto-ets on wiki_crispr: worse than no change
- auto-ets on wiki_ev: range too wide
- auto-ets on wiki_fusion: range too wide
- auto-ets on wiki_fusion: worse than no change
- auto-ets on wiki_gene_therapy: range too wide
- auto-ets on wiki_humanoid: range too wide
- auto-ets on wiki_llm: range too wide
- auto-ets on wiki_quantum: range too wide
- auto-ets on wiki_starship: range too wide
- chronos-bolt on aapl: range too wide
- chronos-bolt on bitcoin: range too narrow
- chronos-bolt on copper: range too narrow
- chronos-bolt on gold: range too narrow
- chronos-bolt on news_climate: range too narrow
- chronos-bolt on news_inflation: range too narrow
- chronos-bolt on news_war: range too narrow
- chronos-bolt on nvda: range too narrow
- chronos-bolt on politics_sanctions: range too wide
- chronos-bolt on silver: range too narrow
- chronos-bolt on vix: range too narrow
- chronos-bolt on weather_new_delhi: range too wide
- chronos-bolt on weather_tokyo: range too wide
- chronos-bolt on wiki_battery: range too wide
- chronos-bolt on wiki_crispr: range too narrow
- chronos-bolt on wiki_ev: range too narrow
- chronos-bolt on wiki_llm: range too narrow
- chronos-bolt on wiki_self_driving: range too wide
- ensemble on copper: range too narrow
- ensemble on gold: range too narrow
- ensemble on msci_world: range too narrow
- ensemble on news_climate: range too narrow
- ensemble on news_protest: range too wide
- ensemble on nvda: range too narrow
- ensemble on politics_ceasefire: range too wide
- ensemble on politics_coup: range too wide
- ensemble on politics_referendum: range too wide
- ensemble on politics_sanctions: range too wide
- ensemble on quakes_m45: range too wide
- ensemble on silver: range too narrow
- ensemble on sp500: range too narrow
- ensemble on tech_composite: range too wide
- ensemble on weather_london: range too wide
- ensemble on weather_sydney: range too wide
- ensemble on weather_tokyo: range too wide
- ensemble on wiki_ai: range too wide
- ensemble on wiki_battery: range too wide
- ensemble on wiki_crispr: range too wide
- ensemble on wiki_fusion: range too wide
- ensemble on wiki_gene_therapy: range too wide
- ensemble on wiki_humanoid: range too wide
- ensemble on wiki_quantum: range too wide
- ensemble on wiki_starship: range too wide
- radiant on copper: range too narrow
- radiant on gold: range too narrow
- radiant on msci_world: range too narrow
- radiant on news_inflation: range too narrow
- radiant on news_protest: range too narrow
- radiant on news_war: range too narrow
- radiant on politics_referendum: range too wide
- radiant on politics_sanctions: range too wide
- radiant on silver: range too narrow
- radiant on sp500: range too narrow
- radiant on vix: range too narrow
- radiant on weather_new_delhi: range too wide
- radiant on weather_sydney: range too wide
- radiant on weather_tokyo: range too wide
- radiant on wiki_crispr: range too narrow
- radiant on wiki_quantum: range too wide
- radiant-core on copper: range too narrow
- radiant-core on copper: worse than no change
- radiant-core on gold: range too narrow
- radiant-core on nasdaq100: range too narrow
- radiant-core on news_climate: range too narrow
- radiant-core on news_inflation: range too narrow
- radiant-core on nvda: range too narrow
- radiant-core on politics_sanctions: range too wide
- radiant-core on silver: range too narrow
- radiant-core on sp500: range too narrow
- radiant-core on tech_composite: range too narrow
- radiant-core on weather_arctic_ice: range too wide
- radiant-core on weather_sydney: range too narrow
- radiant-core on wiki_ai: range too narrow
- seldon on copper: range too narrow
- seldon on gold: range too narrow
- seldon on msci_world: range too narrow
- seldon on news_climate: range too narrow
- seldon on news_inflation: range too narrow
- seldon on news_protest: range too narrow
- seldon on nvda: range too narrow
- seldon on politics_sanctions: range too wide
- seldon on silver: range too narrow
- seldon on sp500: range too narrow
- seldon on vix: range too narrow
- seldon on weather_new_delhi: range too wide
- seldon on weather_sydney: range too wide
- seldon on weather_tokyo: range too wide
- seldon on wiki_crispr: range too narrow
- seldon on wiki_llm: range too narrow
- seldon on wiki_quantum: range too wide
- seldon on wiki_self_driving: range too wide
- seldon-laws on bitcoin: range too narrow
- seldon-laws on copper: range too narrow
- seldon-laws on copper: worse than no change
- seldon-laws on gold: range too narrow
- seldon-laws on gold: worse than no change
- seldon-laws on msci_world: range too narrow
- seldon-laws on msci_world: worse than no change
- seldon-laws on nasdaq100: range too narrow
- seldon-laws on nasdaq100: worse than no change
- seldon-laws on news_climate: range too narrow
- seldon-laws on news_composite: range too narrow
- seldon-laws on news_election: range too narrow
- seldon-laws on news_inflation: range too narrow
- seldon-laws on news_protest: range too narrow
- seldon-laws on nvda: range too narrow
- seldon-laws on politics_sanctions: range too wide
- seldon-laws on silver: range too narrow
- seldon-laws on sp500: range too narrow
- seldon-laws on sp500: worse than no change
- seldon-laws on vix: range too narrow
- seldon-laws on wiki_llm: range too narrow
- seldon-laws on wiki_self_driving: range too wide
- timesfm-2.5 on copper: range too narrow
- timesfm-2.5 on gold: range too narrow
- timesfm-2.5 on msci_world: range too narrow
- timesfm-2.5 on msci_world: worse than no change
- timesfm-2.5 on news_climate: range too narrow
- timesfm-2.5 on news_inflation: range too narrow
- timesfm-2.5 on news_protest: range too narrow
- timesfm-2.5 on news_war: range too narrow
- timesfm-2.5 on nvda: range too narrow
- timesfm-2.5 on politics_referendum: range too wide
- timesfm-2.5 on politics_sanctions: range too wide
- timesfm-2.5 on silver: range too narrow
- timesfm-2.5 on sp500: range too narrow
- timesfm-2.5 on sp500: worse than no change
- timesfm-2.5 on weather_new_delhi: range too wide
- timesfm-2.5 on weather_sydney: range too wide
- timesfm-2.5 on weather_tokyo: range too wide
- timesfm-2.5 on wiki_crispr: range too narrow
- timesfm-2.5 on wiki_ev: range too narrow
- timesfm-2.5 on wiki_llm: range too narrow

## 10. Volatility forecasts

Each market's volatility over the next week and month, forecast at every weekly origin from 2005-12-20 to 2026-11-14 and scored with QLIKE against the volatility that followed. Skill is against last month's volatility carried forward, on the same windows; p is a Diebold-Mariano test.

| Forecaster | Ahead | Windows | Skill | Beat it in | Typical miss | p |
|---|---|---|---|---|---|---|
| garch | 1 week | 19884 | +17.1% | 20 of 20 markets | 33% | 0.000 |
| ewma | 1 week | 19884 | +11.2% | 19 of 20 markets | 31% | 0.000 |
| timesfm-2.5 | 1 week | 168 | +10.3% | 7 of 14 markets | 23% | 0.170 |
| last-month | 1 week | 19884 | baseline |  | 32% |  |
| chronos-bolt | 1 week | 168 | -6.7% | 6 of 14 markets | 25% | 0.448 |
| seldon-laws | 1 week | 168 | -7.7% | 5 of 14 markets | 32% | 0.354 |
| radiant-core | 1 week | 168 | -40.4% | 3 of 14 markets | 39% | 0.717 |
| radiant | 1 week | 168 | -49.5% | 6 of 14 markets | 28% | 0.950 |
| seldon | 1 week | 168 | -105.5% | 4 of 14 markets | 35% | 0.371 |
| garch | 1 month | 19822 | +30.0% | 19 of 20 markets | 25% | 0.000 |
| ewma | 1 month | 19822 | +17.4% | 20 of 20 markets | 22% | 0.000 |
| last-month | 1 month | 19822 | baseline |  | 24% |  |
| seldon-laws | 1 month | 168 | -54.8% | 3 of 14 markets | 23% | 0.393 |
| timesfm-2.5 | 1 month | 168 | -62.0% | 7 of 14 markets | 25% | 0.109 |
| radiant-core | 1 month | 168 | -81.9% | 7 of 14 markets | 28% | 0.290 |
| chronos-bolt | 1 month | 168 | -88.6% | 9 of 14 markets | 19% | 0.022 |
| radiant | 1 month | 168 | -94.3% | 3 of 14 markets | 26% | 0.073 |
| seldon | 1 month | 168 | -197.3% | 4 of 14 markets | 32% | 0.032 |

Sealed volatility forecasts are in `predictions/vol_ledger.csv`, fingerprinted in `predictions/vol_seals.csv` and scored in `predictions/vol_scored.csv`.

## 11. Event odds

The chance that a news or technology series reaches, four weeks ahead, a level it reaches only one day in ten (a spike: above the 90th percentile of its last two years) or falls to a low it sees one day in ten (a lull). Odds are scored with the Brier score; skill is against climatology (10%) and against persistence (what followed days like the origin), on the same forecasts. p is a Diebold-Mariano test of the edge over climatology.

| Event | Forecaster | Forecasts | Happened | Said | Brier | vs climatology | vs persistence | p |
|---|---|---|---|---|---|---|---|---|
| lull | radiant | 300 | 19% | 21% | 0.1328 | +18.1% | +9.6% | 0.032 |
| lull | timesfm-2.5 | 300 | 19% | 20% | 0.1332 | +17.8% | +9.3% | 0.033 |
| lull | seldon-laws | 300 | 19% | 24% | 0.1373 | +15.3% | +6.5% | 0.098 |
| lull | seldon | 300 | 19% | 20% | 0.1429 | +11.8% | +2.6% | 0.131 |
| lull | chronos-bolt | 300 | 19% | 18% | 0.1450 | +10.6% | +1.2% | 0.118 |
| lull | persistence | 300 | 19% | 13% | 0.1468 | +9.4% | baseline | 0.155 |
| lull | radiant-core | 300 | 19% | 27% | 0.1524 | +6.0% | -3.9% | 0.584 |
| lull | climatology | 300 | 19% | 10% | 0.1621 | baseline | -10.4% |  |
| spike | timesfm-2.5 | 300 | 8% | 5% | 0.0664 | +13.3% | +6.7% | 0.016 |
| spike | chronos-bolt | 300 | 8% | 5% | 0.0674 | +12.1% | +5.4% | 0.032 |
| spike | radiant | 300 | 8% | 6% | 0.0676 | +11.8% | +5.1% | 0.043 |
| spike | seldon | 300 | 8% | 7% | 0.0700 | +8.7% | +1.8% | 0.339 |
| spike | persistence | 300 | 8% | 9% | 0.0712 | +7.1% | baseline | 0.012 |
| spike | climatology | 300 | 8% | 10% | 0.0766 | baseline | -7.6% |  |
| spike | seldon-laws | 300 | 8% | 11% | 0.0777 | -1.4% | -9.1% | 0.867 |
| spike | radiant-core | 300 | 8% | 11% | 0.0811 | -5.8% | -13.8% | 0.629 |

Sealed event odds are in `predictions/event_ledger.csv`, fingerprinted in `predictions/event_seals.csv` and scored in `predictions/event_scored.csv`.
