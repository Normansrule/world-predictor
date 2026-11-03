# World Predictor: Seldon scorecard

_Generated 2026-11-02 with model `timesfm-2.5`. Skill = 1 - MAE(model) / MAE(naive random walk); positive is better than naive. Coverage80 should be close to 0.80 for an honest forecaster. Brier scores the probability of going up (0.25 = coin flip, lower is better). See docs/METHODOLOGY.md._

## In plain English

- timesfm-2.5 beat the simple guess "tomorrow looks like today" in 2 of 3 areas: world news (21% less error), technology (44% less error).
- Seldon, our own forecaster (crowd laws with timesfm-2.5 as one voter), won none of the 3 areas against timesfm-2.5, with lower error on 0 of 29 series and higher on 2.
- Hari Seldon's bet did not hold here: aggregates were not easier to predict than individual series (18% vs 25% skill).
- In world news, its edge lasts up to about 28 days ahead.
- In markets, it had no edge at any distance ahead.
- In technology, its edge lasts up to about 28 days ahead.
- When it gave 70% or more odds of a rise, the rise really happened 79% of the time (48 forecasts).

![Replay of past forecasts against what really happened](plots/replay.gif)

_Each frame is a forecast made in the past: the orange band is what the model expected, the dark dots are what really happened._

## Seldon vs timesfm-2.5: the duel

Seldon is this project's own forecaster (`src/psychohistory/seldon.py`): four laws of crowd behaviour (inertia, drift, momentum, reversion, on top of the weekly rhythm) with TimesFM as one more voter, the laws' share learned per area from finished windows only. It forecasts the same windows as TimesFM and is scored by the same code. A series is won by whichever had the lower average error there; a series where the full Seldon gave TimesFM the whole vote is a tie. Skill is against "no change" (positive is better); range skill scores the whole 80% range (pinball loss).

**The full Seldon** (crowd laws and TimesFM in one council)

| Area | Series | Seldon won | TimesFM won | Seldon's error vs TimesFM | Skill: TimesFM / Seldon | Range skill: TimesFM / Seldon | In 80% range: TimesFM / Seldon | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 12 | 0 | 0 | +0% | -1% / -1% | +1% / +1% | 77% / 77% | tie |
| World events in the news | 6 | 0 | 0 | +0% | +21% / +21% | +21% / +21% | 76% / 76% | tie |
| New technologies | 11 | 0 | 2 | +3% | +44% / +43% | +42% / +35% | 74% / 72% | timesfm-2.5 |
| **All areas** | 29 | 0 | 2 | +1% | +18% / +18% | +16% / +16% | 76% / 75% | timesfm-2.5 |

_This run recorded TimesFM and the crowd laws but not the full Seldon, so the full Seldon was replayed from their recorded paths, learning its shares from earlier windows only (`backtest.replay_seldon`). Errors, wins and the 80% range are exact; range skill is close._

**The crowd laws alone** (`seldon-laws`, no TimesFM vote)

| Area | Series | Laws won | TimesFM won | Laws' error vs TimesFM | Skill: TimesFM / Laws | Range skill: TimesFM / Laws | In 80% range: TimesFM / Laws | Winner |
|---|---|---|---|---|---|---|---|---|
| Stock and value markets | 12 | 6 | 6 | -2% | -1% / -0% | +1% / +1% | 77% / 77% | tie |
| World events in the news | 6 | 0 | 6 | +10% | +21% / +15% | +21% / +15% | 76% / 79% | timesfm-2.5 |
| New technologies | 11 | 1 | 10 | +27% | +44% / +19% | +42% / +24% | 74% / 68% | timesfm-2.5 |
| **All areas** | 29 | 7 | 22 | +12% | +18% / +6% | +16% / +11% | 76% / 74% | timesfm-2.5 |

## 1. Can the future be predicted?

![Skill by domain](plots/skill_by_domain.png)

- **World events in the news**: timesfm-2.5 beats the naive baseline (21% less error).
- **Stock and value markets**: timesfm-2.5 about the same as the naive baseline.
- **New technologies**: timesfm-2.5 beats the naive baseline (44% less error).

| domain   | model        |   series |   median_skill |   median_mase |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|---------------:|--------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       12 |          0.001 |         4.694 |       0.405 |        0.775 |   0.255 |
| markets  | chronos-bolt |       12 |         -0.064 |         4.487 |       0.482 |        0.747 |   0.269 |
| markets  | drift        |       12 |         -0.003 |         4.635 |       0.517 |        0.614 |   0.267 |
| markets  | ensemble     |       12 |         -0.015 |         4.493 |       0.516 |        0.777 |   0.258 |
| markets  | mean         |       12 |         -1.074 |         8.451 |       0.477 |        0.511 |   0.400 |
| markets  | naive        |       12 |          0.000 |         4.694 |     nan     |        0.619 |   0.250 |
| markets  | seldon       |       12 |         -0.012 |         4.744 |       0.454 |        0.766 |   0.269 |
| markets  | seldon-laws  |       12 |         -0.005 |         4.699 |       0.460 |        0.772 |   0.253 |
| markets  | timesfm-2.5  |       12 |         -0.012 |         4.744 |       0.454 |        0.766 |   0.269 |
| news     | auto-ets     |        6 |         -0.060 |         1.577 |       0.625 |        0.881 |   0.240 |
| news     | chronos-bolt |        6 |          0.205 |         1.195 |       0.708 |        0.738 |   0.207 |
| news     | drift        |        6 |         -0.002 |         1.561 |       0.417 |        0.802 |   0.260 |
| news     | ensemble     |        6 |          0.179 |         1.280 |       0.653 |        0.843 |   0.213 |
| news     | mean         |        6 |          0.171 |         1.305 |       0.694 |        0.679 |   0.209 |
| news     | naive        |        6 |          0.000 |         1.556 |     nan     |        0.806 |   0.250 |
| news     | seldon       |        6 |          0.215 |         1.228 |       0.681 |        0.761 |   0.202 |
| news     | seldon-laws  |        6 |          0.146 |         1.333 |       0.639 |        0.785 |   0.215 |
| news     | timesfm-2.5  |        6 |          0.215 |         1.228 |       0.681 |        0.761 |   0.202 |
| tech     | auto-ets     |       11 |          0.066 |         1.577 |       0.598 |        0.817 |   0.220 |
| tech     | bass         |        3 |         -1.365 |       108.159 |       0.333 |        0.000 |   0.602 |
| tech     | chronos-bolt |       11 |          0.465 |         0.806 |       0.788 |        0.760 |   0.146 |
| tech     | drift        |       11 |         -0.024 |         1.405 |       0.689 |        0.649 |   0.181 |
| tech     | ensemble     |       11 |          0.361 |         0.989 |       0.659 |        0.852 |   0.190 |
| tech     | mean         |       11 |          0.139 |         1.179 |       0.348 |        0.522 |   0.502 |
| tech     | naive        |       11 |          0.000 |         1.433 |     nan     |        0.653 |   0.297 |
| tech     | seldon       |       11 |          0.428 |         0.801 |       0.750 |        0.724 |   0.162 |
| tech     | seldon-laws  |       11 |          0.194 |         0.935 |       0.742 |        0.683 |   0.181 |
| tech     | timesfm-2.5  |       11 |          0.441 |         0.801 |       0.750 |        0.745 |   0.161 |

## 2. Seldon's law of large numbers: aggregates vs individuals

Psychohistory only claims to work for very large populations. If that holds here, aggregate series (indices, composites, world totals) should show higher skill and lower MASE than individual ones.

| domain   | scale      | model       |   series |   median_skill |   median_mase |
|:---------|:-----------|:------------|---------:|---------------:|--------------:|
| markets  | aggregate  | timesfm-2.5 |        3 |         -0.081 |         3.745 |
| markets  | individual | timesfm-2.5 |        9 |         -0.007 |         4.775 |
| news     | aggregate  | timesfm-2.5 |        1 |          0.183 |         1.303 |
| news     | individual | timesfm-2.5 |        5 |          0.247 |         1.152 |
| tech     | aggregate  | timesfm-2.5 |        4 |          0.493 |        15.981 |
| tech     | individual | timesfm-2.5 |        7 |          0.367 |         0.801 |

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
| oil_wti        | markets  | 2026-03-03 |        0.048 |  14.407 |
| wiki_ai        | tech     | 2026-09-05 |        0.071 |   5.248 |
| gold           | markets  | 2026-08-03 |        0.095 |  14.222 |
| news_inflation | news     | 2026-02-25 |        0.107 |   2.119 |
| nasdaq100      | markets  | 2026-04-01 |        0.143 |  11.570 |
| sp500          | markets  | 2026-04-01 |        0.143 |  10.210 |
| msci_world     | markets  | 2026-04-01 |        0.143 |   8.255 |
| nasdaq100      | markets  | 2026-05-01 |        0.143 |   8.043 |
| sp500          | markets  | 2026-05-01 |        0.143 |   5.332 |

## 4. Prediction ledger (true out-of-sample test)

![Time Vault track record](plots/track_record.png)

_Predictions are sealed with a date before the future happens and opened when it arrives. The left line should settle near 80%; the right line should sit below the coin-flip line._

| domain   | model        |   series |   predictions |   median_skill |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|--------------:|---------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       12 |           443 |         -0.002 |       0.482 |        0.887 |   0.253 |
| markets  | chronos-bolt |       12 |           443 |         -0.100 |       0.462 |        0.830 |   0.274 |
| markets  | ensemble     |       12 |           443 |         -0.036 |       0.468 |        0.851 |   0.256 |
| markets  | seldon-laws  |       12 |           176 |         -0.019 |       0.342 |        0.777 |   0.259 |
| markets  | timesfm-2.5  |       12 |           443 |          0.000 |       0.497 |        0.847 |   0.252 |
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
| markets  |    0.034 | -0.021 | -0.031 |  -0.003 | -0.000 |
| news     |    0.183 |  0.258 |  0.246 |   0.186 |  0.192 |
| tech     |    0.039 |  0.576 |  0.367 |   0.445 |  0.322 |

## 6. Are its odds honest?

Backtest forecasts grouped by the chance they gave of the series ending higher. `said` is the average probability given, `happened` is how often it really went up. When the two match, the odds can be taken at face value.

| domain   | odds given   |   forecasts |   said |   happened |
|:---------|:-------------|------------:|-------:|-----------:|
| markets  | 20%-40%      |           8 |  0.380 |      0.500 |
| markets  | 40%-60%      |         111 |  0.483 |      0.577 |
| markets  | 60%-80%      |          25 |  0.663 |      0.320 |
| news     | 0%-20%       |          14 |  0.100 |      0.143 |
| news     | 20%-40%      |          23 |  0.299 |      0.478 |
| news     | 40%-60%      |          17 |  0.477 |      0.529 |
| news     | 60%-80%      |          14 |  0.693 |      0.929 |
| news     | 80%-100%     |           4 |  0.853 |      0.750 |
| tech     | 0%-20%       |          16 |  0.155 |      0.312 |
| tech     | 20%-40%      |          38 |  0.308 |      0.237 |
| tech     | 40%-60%      |          29 |  0.514 |      0.586 |
| tech     | 60%-80%      |          16 |  0.697 |      0.812 |
| tech     | 80%-100%     |          22 |  0.911 |      1.000 |

## 7. Every series

| series_id         | domain   | scale      | model       |      mae |   mase |   smape |   direction |   coverage80 |   pinball |   brier |   skill |   prob_skill |
|:------------------|:---------|:-----------|:------------|---------:|-------:|--------:|------------:|-------------:|----------:|--------:|--------:|-------------:|
| aapl              | markets  | individual | timesfm-2.5 |   11.277 |  4.775 |   0.039 |       0.500 |        0.734 |     1.849 |   0.241 |  -0.007 |       -0.008 |
| adoption_internet | tech     | aggregate  | timesfm-2.5 |    2.341 |  0.774 |   0.032 |       1.000 |        1.000 |     0.260 |   0.002 |   0.460 |        0.526 |
| adoption_solar    | tech     | aggregate  | timesfm-2.5 |    0.254 | 64.139 |   0.421 |       0.750 |        0.417 |    27.337 |   0.197 |   0.441 |        0.282 |
| adoption_wind     | tech     | aggregate  | timesfm-2.5 |    0.165 | 31.187 |   0.249 |       0.833 |        0.694 |    12.482 |   0.124 |   0.646 |        0.416 |
| bitcoin           | markets  | individual | timesfm-2.5 | 5007.985 |  3.973 |   0.067 |       0.250 |        0.842 |     1.589 |   0.257 |  -0.001 |        0.006 |
| copper            | markets  | individual | timesfm-2.5 |    0.203 |  3.794 |   0.034 |       0.364 |        0.877 |     1.461 |   0.262 |  -0.012 |       -0.008 |
| gold              | markets  | individual | timesfm-2.5 |  185.485 |  8.103 |   0.041 |       0.583 |        0.798 |     3.305 |   0.238 |   0.020 |        0.084 |
| msci_world        | markets  | aggregate  | timesfm-2.5 |    3.606 |  3.696 |   0.019 |       0.500 |        0.679 |     1.460 |   0.338 |  -0.089 |       -0.055 |
| nasdaq100         | markets  | aggregate  | timesfm-2.5 |  917.026 |  5.125 |   0.033 |       0.500 |        0.651 |     2.030 |   0.292 |  -0.072 |       -0.050 |
| news_climate      | news     | individual | timesfm-2.5 |    0.131 |  0.994 |   0.159 |       0.667 |        0.771 |     0.383 |   0.225 |   0.097 |        0.118 |
| news_composite    | news     | aggregate  | timesfm-2.5 |    0.088 |  1.303 |   0.093 |       0.667 |        0.771 |     0.521 |   0.206 |   0.183 |        0.155 |
| news_election     | news     | individual | timesfm-2.5 |    0.568 |  1.152 |   0.128 |       0.667 |        0.807 |     0.474 |   0.186 |   0.247 |        0.290 |
| news_inflation    | news     | individual | timesfm-2.5 |    0.302 |  0.988 |   0.156 |       0.667 |        0.771 |     0.388 |   0.232 |   0.278 |        0.265 |
| news_pandemic     | news     | individual | timesfm-2.5 |    0.247 |  1.331 |   0.123 |       0.500 |        0.702 |     0.553 |   0.225 |   0.346 |        0.338 |
| news_protest      | news     | individual | timesfm-2.5 |    0.506 |  1.723 |   0.212 |       0.917 |        0.747 |     0.731 |   0.141 |   0.137 |        0.130 |
| nvda              | markets  | individual | timesfm-2.5 |   11.417 |  5.819 |   0.057 |       0.417 |        0.786 |     2.226 |   0.273 |  -0.014 |        0.074 |
| oil_wti           | markets  | individual | timesfm-2.5 |    6.717 |  4.713 |   0.081 |       0.250 |        0.754 |     1.909 |   0.285 |  -0.012 |        0.043 |
| silver            | markets  | individual | timesfm-2.5 |    5.571 | 10.092 |   0.080 |       0.500 |        0.837 |     4.059 |   0.244 |   0.015 |        0.123 |
| sp500             | markets  | aggregate  | timesfm-2.5 |  141.923 |  3.745 |   0.020 |       0.583 |        0.647 |     1.509 |   0.281 |  -0.081 |       -0.061 |
| tech_composite    | tech     | aggregate  | timesfm-2.5 |    0.071 |  0.697 |   0.086 |       0.750 |        0.723 |     0.281 |   0.175 |   0.526 |        0.492 |
| tsla              | markets  | individual | timesfm-2.5 |   22.525 |  2.994 |   0.057 |       0.667 |        0.881 |     1.181 |   0.247 |   0.037 |        0.018 |
| wiki_ai           | tech     | individual | timesfm-2.5 | 1684.216 |  1.250 |   0.125 |       0.667 |        0.747 |     0.529 |   0.205 |   0.376 |        0.347 |
| wiki_crispr       | tech     | individual | timesfm-2.5 |   85.733 |  0.563 |   0.107 |       0.667 |        0.792 |     0.229 |   0.152 |   0.482 |        0.460 |
| wiki_ev           | tech     | individual | timesfm-2.5 |   40.368 |  0.442 |   0.092 |       0.833 |        0.839 |     0.174 |   0.181 |   0.367 |        0.430 |
| wiki_fusion       | tech     | individual | timesfm-2.5 |   94.003 |  0.801 |   0.122 |       0.833 |        0.738 |     0.332 |   0.153 |   0.224 |        0.214 |
| wiki_humanoid     | tech     | individual | timesfm-2.5 |   60.447 |  1.021 |   0.165 |       0.667 |        0.690 |     0.423 |   0.204 |   0.262 |        0.231 |
| wiki_llm          | tech     | individual | timesfm-2.5 |  286.393 |  0.527 |   0.085 |       0.750 |        0.804 |     0.212 |   0.146 |   0.641 |        0.604 |
| wiki_quantum      | tech     | individual | timesfm-2.5 |  367.397 |  0.935 |   0.133 |       0.500 |        0.747 |     0.410 |   0.235 |   0.299 |        0.258 |
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
| aapl       |   341.41  | 2026-12-01    | +1.0%    | 57%             | -6.9% to +6.3%    |
| bitcoin    | 77790.1   | 2026-11-30    | -1.5%    | 45%             | -17.5% to +15.9%  |
| copper     |     6.541 | 2026-12-01    | -0.3%    | 45%             | -7.4% to +3.9%    |
| gold       |  3957.8   | 2026-12-01    | -0.6%    | 45%             | -8.0% to +8.1%    |
| msci_world |   205.545 | 2026-12-01    | +1.8%    | 78%             | -1.3% to +4.2%    |
| nasdaq100  | 28510.9   | 2026-12-01    | +2.6%    | 68%             | -4.7% to +8.9%    |
| nvda       |   207.36  | 2026-12-01    | +0.3%    | 51%             | -10.2% to +10.6%  |
| oil_wti    |    97.49  | 2026-12-01    | -2.9%    | 39%             | -18.3% to +11.1%  |
| silver     |    50.905 | 2026-12-01    | -0.8%    | 47%             | -13.0% to +15.5%  |
| sp500      |  7613.91  | 2026-12-01    | +1.7%    | 73%             | -2.1% to +4.4%    |
| tsla       |   407.43  | 2026-12-01    | +0.7%    | 52%             | -14.8% to +16.8%  |
| xom        |   182.29  | 2026-12-01    | +0.6%    | 53%             | -9.4% to +10.4%   |

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
![tsla](plots/tsla.png)
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
| auto-ets | 954 | 5 | -0.2% | 91% | 51% | 0.251 |
| chronos-bolt | 954 | 5 | +7.2% | 76% | 60% | 0.219 |
| ensemble | 954 | 5 | -0.2% | 88% | 58% | 0.212 |
| seldon-laws | 364 | 3 | +0.1% | 73% | 52% | 0.217 |
| timesfm-2.5 | 954 | 5 | +5.6% | 76% | 63% | 0.205 |

**Is timesfm-2.5 really better than "no change"?** A Diebold-Mariano test on the weekly batches (Newey-West variance, as the batches' horizons overlap, with the Harvey-Leybourne-Newbold small-sample correction and Student's t):

- All areas: not distinguishable from no change (p = 0.25)
- Stock and value markets: not distinguishable from no change (p = 0.83)
- World events in the news: not distinguishable from no change
- New technologies: not distinguishable from no change (p = 0.47)

**Drift alarms** (forecasts due in the last 13 weeks): 24 raised. Every forecaster is tested on every series at once, so alarms must pass a Benjamini-Hochberg false-discovery cut of 5%.
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
- ensemble on aapl: edge lost
- ensemble on news_election: edge lost
- ensemble on wiki_humanoid: edge lost
- ensemble on wiki_quantum: range too wide
- timesfm-2.5 on aapl: range too wide
- timesfm-2.5 on bitcoin: range too wide
- timesfm-2.5 on news_election: edge lost
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
