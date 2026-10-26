# World Predictor: Seldon scorecard

_Generated 2026-10-26 with model `timesfm-2.5`. Skill = 1 - MAE(model) / MAE(naive random walk); positive is better than naive. Coverage80 should be close to 0.80 for an honest forecaster. Brier scores the probability of going up (0.25 = coin flip, lower is better). See docs/METHODOLOGY.md._

## In plain English

- timesfm-2.5 beat the simple guess "tomorrow looks like today" in 2 of 3 areas: world news (8% less error), technology (45% less error).
- Seldon, our own forecaster built from five laws of crowd behaviour, won 1 of 3 areas (markets) against timesfm-2.5, with lower error on 11 of 29 series.
- Hari Seldon's bet held here: big aggregates such as indices and averages were easier to predict than single stocks or topics (13% vs 4% skill).
- In world news, its edge lasts up to about 28 days ahead.
- In markets, it had no edge at any distance ahead.
- In technology, its edge lasts up to about 28 days ahead.
- When it gave 70% or more odds of a rise, the rise really happened 87% of the time (53 forecasts).

![Replay of past forecasts against what really happened](plots/replay.gif)

_Each frame is a forecast made in the past: the orange band is what the model expected, the dark dots are what really happened._

## Seldon vs timesfm-2.5: the duel

Seldon is this project's own forecaster (`src/psychohistory/seldon.py`): five simple laws of crowd behaviour (inertia, drift, momentum, reversion, a weekly rhythm), each voting by how well it predicted the same series before. It forecasts the same windows as TimesFM and is scored by the same code. A series is won by whichever had the lower average error there. Skill is against "no change" (positive is better); range skill scores the whole 80% range (pinball loss).

| Area | Series | Seldon won | TimesFM won | Skill: TimesFM / Seldon | Range skill: TimesFM / Seldon | In 80% range: TimesFM / Seldon | Winner |
|---|---|---|---|---|---|---|---|
| Stock and value markets | 12 | 9 | 3 | -2% / +3% | +1% / +3% | 82% / 78% | Seldon |
| World events in the news | 6 | 1 | 5 | +8% / +8% | +12% / +9% | 78% / 80% | timesfm-2.5 |
| New technologies | 11 | 1 | 10 | +45% / +24% | +44% / +24% | 75% / 70% | timesfm-2.5 |
| **All areas** | 29 | 11 | 18 | +13% / +5% | +16% / +11% | 78% / 76% | timesfm-2.5 |

## 1. Can the future be predicted?

![Skill by domain](plots/skill_by_domain.png)

- **World events in the news**: timesfm-2.5 beats the naive baseline (8% less error).
- **Stock and value markets**: timesfm-2.5 about the same as the naive baseline.
- **New technologies**: timesfm-2.5 beats the naive baseline (45% less error).

| domain   | model        |   series |   median_skill |   median_mase |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|---------------:|--------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       12 |         -0.000 |         4.083 |       0.493 |        0.807 |   0.251 |
| markets  | chronos-bolt |       12 |         -0.050 |         4.225 |       0.556 |        0.809 |   0.255 |
| markets  | drift        |       12 |          0.026 |         3.920 |       0.583 |        0.640 |   0.254 |
| markets  | ensemble     |       12 |          0.001 |         4.052 |       0.590 |        0.832 |   0.244 |
| markets  | mean         |       12 |         -1.140 |         8.430 |       0.507 |        0.494 |   0.325 |
| markets  | naive        |       12 |          0.000 |         4.133 |     nan     |        0.633 |   0.250 |
| markets  | seldon       |       12 |          0.027 |         3.980 |       0.597 |        0.784 |   0.240 |
| markets  | timesfm-2.5  |       12 |         -0.021 |         4.239 |       0.521 |        0.816 |   0.245 |
| news     | auto-ets     |        6 |         -0.089 |         1.299 |       0.611 |        0.903 |   0.246 |
| news     | chronos-bolt |        6 |          0.073 |         1.137 |       0.597 |        0.750 |   0.237 |
| news     | drift        |        6 |         -0.010 |         1.268 |       0.444 |        0.862 |   0.254 |
| news     | ensemble     |        6 |          0.089 |         1.139 |       0.625 |        0.862 |   0.228 |
| news     | mean         |        6 |         -0.093 |         1.222 |       0.611 |        0.688 |   0.231 |
| news     | naive        |        6 |          0.000 |         1.255 |     nan     |        0.867 |   0.250 |
| news     | seldon       |        6 |          0.075 |         1.149 |       0.597 |        0.804 |   0.231 |
| news     | timesfm-2.5  |        6 |          0.079 |         1.103 |       0.611 |        0.780 |   0.226 |
| tech     | auto-ets     |       11 |         -0.027 |         2.209 |       0.672 |        0.819 |   0.190 |
| tech     | bass         |        3 |         -1.365 |       108.159 |       0.333 |        0.000 |   0.602 |
| tech     | chronos-bolt |       11 |          0.447 |         0.772 |       0.809 |        0.776 |   0.142 |
| tech     | drift        |       11 |          0.014 |         1.348 |       0.634 |        0.639 |   0.184 |
| tech     | ensemble     |       11 |          0.280 |         1.221 |       0.733 |        0.858 |   0.167 |
| tech     | mean         |       11 |          0.140 |         1.133 |       0.537 |        0.526 |   0.388 |
| tech     | naive        |       11 |          0.000 |         1.361 |     nan     |        0.639 |   0.297 |
| tech     | seldon       |       11 |          0.244 |         1.046 |       0.718 |        0.698 |   0.180 |
| tech     | timesfm-2.5  |       11 |          0.452 |         0.774 |       0.771 |        0.752 |   0.160 |

## 2. Seldon's law of large numbers: aggregates vs individuals

Psychohistory only claims to work for very large populations. If that holds here, aggregate series (indices, composites, world totals) should show higher skill and lower MASE than individual ones.

| domain   | scale      | model       |   series |   median_skill |   median_mase |
|:---------|:-----------|:------------|---------:|---------------:|--------------:|
| markets  | aggregate  | timesfm-2.5 |        3 |          0.129 |         3.098 |
| markets  | individual | timesfm-2.5 |        9 |         -0.034 |         4.719 |
| news     | aggregate  | timesfm-2.5 |        1 |          0.120 |         1.174 |
| news     | individual | timesfm-2.5 |        5 |          0.039 |         1.060 |
| tech     | aggregate  | timesfm-2.5 |        4 |          0.478 |        15.981 |
| tech     | individual | timesfm-2.5 |        7 |          0.432 |         0.764 |

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
| oil_wti        | markets  | 2026-02-23 |        0.190 |  13.582 |
| aapl           | markets  | 2026-06-23 |        0.190 |   8.678 |
| bitcoin        | markets  | 2026-01-14 |        0.214 |  13.993 |
| wiki_llm       | tech     | 2026-08-26 |        0.214 |   1.460 |
| wiki_quantum   | tech     | 2025-11-19 |        0.214 |   1.250 |
| oil_wti        | markets  | 2026-01-22 |        0.238 |   3.055 |
| xom            | markets  | 2026-01-21 |        0.286 |  10.969 |
| msci_world     | markets  | 2026-02-20 |        0.286 |   5.947 |
| news_climate   | news     | 2026-02-20 |        0.286 |   1.245 |

## 4. Prediction ledger (true out-of-sample test)

![Time Vault track record](plots/track_record.png)

_Predictions are sealed with a date before the future happens and opened when it arrives. The left line should settle near 80%; the right line should sit below the coin-flip line._

| domain   | model        |   series |   predictions |   median_skill |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|--------------:|---------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       12 |           155 |         -0.003 |       0.540 |        0.866 |   0.251 |
| markets  | chronos-bolt |       12 |           155 |         -0.087 |       0.419 |        0.859 |   0.279 |
| markets  | ensemble     |       12 |           155 |         -0.043 |       0.425 |        0.854 |   0.259 |
| markets  | seldon       |       12 |            26 |         -0.010 |       0.208 |        0.479 |   0.255 |
| markets  | timesfm-2.5  |       12 |           155 |         -0.028 |       0.440 |        0.835 |   0.257 |
| news     | auto-ets     |        6 |            90 |          0.011 |       0.572 |        0.815 |   0.241 |
| news     | chronos-bolt |        6 |            90 |         -0.017 |       0.636 |        0.695 |   0.225 |
| news     | ensemble     |        6 |            90 |          0.005 |       0.634 |        0.782 |   0.227 |
| news     | seldon       |        6 |            24 |          0.016 |       0.653 |        0.500 |   0.231 |
| news     | timesfm-2.5  |        6 |            90 |         -0.037 |       0.586 |        0.704 |   0.257 |
| tech     | auto-ets     |        8 |           168 |         -0.103 |       0.524 |        0.964 |   0.250 |
| tech     | chronos-bolt |        8 |           168 |          0.597 |       0.798 |        0.911 |   0.131 |
| tech     | ensemble     |        8 |           168 |          0.440 |       0.762 |        0.988 |   0.139 |
| tech     | seldon       |        8 |            32 |          0.576 |       0.750 |        0.938 |   0.137 |
| tech     | timesfm-2.5  |        8 |           168 |          0.618 |       0.827 |        0.875 |   0.112 |

## 5. How far ahead can it see?

Median skill versus the naive baseline by how many steps ahead the forecast is (days for news and tech attention, trading days for markets; yearly adoption series are too short for this and are left out). Where skill drops to zero is the limit of the model's foresight in that domain.

![Skill by step](plots/skill_by_step.png)

| domain   |   1 step |    2-5 |   6-10 |   11-20 |   21+ |
|:---------|---------:|-------:|-------:|--------:|------:|
| markets  |   -0.062 | -0.003 | -0.030 |  -0.018 | 0.023 |
| news     |    0.116 |  0.046 |  0.063 |   0.079 | 0.111 |
| tech     |    0.033 |  0.519 |  0.327 |   0.360 | 0.301 |

## 6. Are its odds honest?

Backtest forecasts grouped by the chance they gave of the series ending higher. `said` is the average probability given, `happened` is how often it really went up. When the two match, the odds can be taken at face value.

| domain   | odds given   |   forecasts |   said |   happened |
|:---------|:-------------|------------:|-------:|-----------:|
| markets  | 20%-40%      |           8 |  0.379 |      0.500 |
| markets  | 40%-60%      |         110 |  0.491 |      0.609 |
| markets  | 60%-80%      |          26 |  0.657 |      0.692 |
| news     | 0%-20%       |           7 |  0.133 |      0.000 |
| news     | 20%-40%      |          17 |  0.306 |      0.529 |
| news     | 40%-60%      |          25 |  0.516 |      0.560 |
| news     | 60%-80%      |          20 |  0.683 |      0.600 |
| news     | 80%-100%     |           3 |  0.843 |      1.000 |
| tech     | 0%-20%       |          17 |  0.120 |      0.235 |
| tech     | 20%-40%      |          25 |  0.301 |      0.200 |
| tech     | 40%-60%      |          22 |  0.489 |      0.636 |
| tech     | 60%-80%      |          34 |  0.693 |      0.676 |
| tech     | 80%-100%     |          23 |  0.901 |      1.000 |

## 7. Every series

| series_id         | domain   | scale      | model       |      mae |   mase |   smape |   direction |   coverage80 |   pinball |   brier |   skill |   prob_skill |
|:------------------|:---------|:-----------|:------------|---------:|-------:|--------:|------------:|-------------:|----------:|--------:|--------:|-------------:|
| aapl              | markets  | individual | timesfm-2.5 |   11.498 |  4.892 |   0.040 |       0.500 |        0.770 |     1.842 |   0.256 |  -0.034 |       -0.000 |
| adoption_internet | tech     | aggregate  | timesfm-2.5 |    2.341 |  0.774 |   0.032 |       1.000 |        1.000 |     0.260 |   0.002 |   0.460 |        0.526 |
| adoption_solar    | tech     | aggregate  | timesfm-2.5 |    0.254 | 64.139 |   0.421 |       0.750 |        0.417 |    27.337 |   0.197 |   0.441 |        0.282 |
| adoption_wind     | tech     | aggregate  | timesfm-2.5 |    0.165 | 31.187 |   0.249 |       0.833 |        0.694 |    12.482 |   0.124 |   0.646 |        0.416 |
| bitcoin           | markets  | individual | timesfm-2.5 | 4302.526 |  3.477 |   0.056 |       0.583 |        0.893 |     1.508 |   0.246 |  -0.065 |       -0.100 |
| copper            | markets  | individual | timesfm-2.5 |    0.206 |  3.848 |   0.035 |       0.250 |        0.865 |     1.480 |   0.262 |  -0.048 |       -0.034 |
| gold              | markets  | individual | timesfm-2.5 |  189.141 |  8.163 |   0.042 |       0.500 |        0.813 |     3.150 |   0.266 |  -0.077 |        0.028 |
| msci_world        | markets  | aggregate  | timesfm-2.5 |    3.020 |  3.098 |   0.016 |       0.667 |        0.726 |     1.223 |   0.187 |   0.187 |        0.203 |
| nasdaq100         | markets  | aggregate  | timesfm-2.5 |  607.815 |  3.405 |   0.022 |       0.500 |        0.837 |     1.353 |   0.251 |   0.052 |        0.084 |
| news_climate      | news     | individual | timesfm-2.5 |    0.140 |  1.060 |   0.169 |       0.500 |        0.723 |     0.413 |   0.253 |   0.034 |        0.088 |
| news_composite    | news     | aggregate  | timesfm-2.5 |    0.094 |  1.174 |   0.099 |       0.750 |        0.807 |     0.470 |   0.196 |   0.120 |        0.137 |
| news_election     | news     | individual | timesfm-2.5 |    0.509 |  1.033 |   0.123 |       0.333 |        0.833 |     0.412 |   0.314 |   0.008 |        0.094 |
| news_inflation    | news     | individual | timesfm-2.5 |    0.291 |  0.950 |   0.151 |       0.750 |        0.789 |     0.375 |   0.200 |   0.195 |        0.210 |
| news_pandemic     | news     | individual | timesfm-2.5 |    0.214 |  1.146 |   0.106 |       0.750 |        0.774 |     0.479 |   0.157 |   0.160 |        0.149 |
| news_protest      | news     | individual | timesfm-2.5 |    0.452 |  1.543 |   0.191 |       0.583 |        0.756 |     0.649 |   0.236 |   0.039 |        0.069 |
| nvda              | markets  | individual | timesfm-2.5 |    8.831 |  4.630 |   0.045 |       0.417 |        0.833 |     1.797 |   0.248 |  -0.039 |       -0.030 |
| oil_wti           | markets  | individual | timesfm-2.5 |    6.723 |  4.719 |   0.082 |       0.500 |        0.718 |     1.922 |   0.265 |  -0.025 |        0.010 |
| silver            | markets  | individual | timesfm-2.5 |    6.283 | 11.885 |   0.088 |       0.333 |        0.841 |     4.542 |   0.262 |  -0.007 |        0.163 |
| sp500             | markets  | aggregate  | timesfm-2.5 |  112.125 |  2.959 |   0.016 |       0.667 |        0.790 |     1.177 |   0.193 |   0.129 |        0.165 |
| tech_composite    | tech     | aggregate  | timesfm-2.5 |    0.063 |  0.618 |   0.076 |       0.583 |        0.783 |     0.251 |   0.221 |   0.497 |        0.486 |
| tsla              | markets  | individual | timesfm-2.5 |   19.229 |  2.540 |   0.048 |       0.833 |        0.940 |     1.068 |   0.235 |  -0.017 |       -0.081 |
| wiki_ai           | tech     | individual | timesfm-2.5 | 1450.256 |  1.074 |   0.110 |       0.917 |        0.780 |     0.442 |   0.140 |   0.452 |        0.452 |
| wiki_crispr       | tech     | individual | timesfm-2.5 |   88.122 |  0.573 |   0.110 |       0.833 |        0.741 |     0.228 |   0.108 |   0.587 |        0.625 |
| wiki_ev           | tech     | individual | timesfm-2.5 |   42.647 |  0.461 |   0.095 |       0.818 |        0.812 |     0.184 |   0.189 |   0.345 |        0.403 |
| wiki_fusion       | tech     | individual | timesfm-2.5 |   90.128 |  0.764 |   0.114 |       0.583 |        0.795 |     0.314 |   0.220 |   0.432 |        0.444 |
| wiki_humanoid     | tech     | individual | timesfm-2.5 |   56.279 |  0.949 |   0.152 |       0.667 |        0.750 |     0.391 |   0.241 |   0.300 |        0.296 |
| wiki_llm          | tech     | individual | timesfm-2.5 |  283.550 |  0.521 |   0.084 |       0.833 |        0.786 |     0.215 |   0.135 |   0.505 |        0.490 |
| wiki_quantum      | tech     | individual | timesfm-2.5 |  375.137 |  0.958 |   0.135 |       0.667 |        0.714 |     0.417 |   0.187 |   0.294 |        0.258 |
| xom               | markets  | individual | timesfm-2.5 |    6.081 |  4.907 |   0.042 |       0.500 |        0.766 |     1.922 |   0.262 |  -0.010 |        0.006 |

## 8. What the model expects next

![What the model expects next](plots/outlook.png)

Latest forecasts recorded in the ledger (made with data up to each series' last date). Changes are relative to the last observed value; the range is the 10%-90% band; "chance higher" is the model's probability that the value on the target date is above today's (scored later with the Brier score: 0 is perfect, 0.25 is a coin flip).

### World events in the news

| series         |   last | target date   | median   | chance higher   | range (10%-90%)   |
|:---------------|-------:|:--------------|:---------|:----------------|:------------------|
| news_climate   |  0.558 | 2026-11-23    | +52.9%   | 95%             | +11.8% to +117.0% |
| news_composite |  1.316 | 2026-11-23    | -29.8%   | 5%              | -40.6% to -10.2%  |
| news_election  | 15.704 | 2026-11-23    | -64.9%   | 5%              | -73.9% to -41.2%  |
| news_inflation |  2.119 | 2026-11-23    | -11.0%   | 29%             | -32.2% to +19.2%  |
| news_pandemic  |  1.472 | 2026-11-23    | +6.6%    | 70%             | -8.9% to +29.1%   |
| news_protest   |  2.944 | 2026-11-23    | -31.8%   | 14%             | -49.0% to +6.4%   |

![news_climate](plots/news_climate.png)
![news_composite](plots/news_composite.png)
![news_election](plots/news_election.png)
![news_inflation](plots/news_inflation.png)
![news_pandemic](plots/news_pandemic.png)
![news_protest](plots/news_protest.png)

### Stock and value markets

| series     |      last | target date   | median   | chance higher   | range (10%-90%)   |
|:-----------|----------:|:--------------|:---------|:----------------|:------------------|
| aapl       |   347.73  | 2026-11-23    | +0.9%    | 57%             | -6.6% to +6.8%    |
| bitcoin    | 80153.8   | 2026-11-23    | -0.8%    | 47%             | -17.0% to +16.2%  |
| copper     |     6.517 | 2026-11-24    | -0.4%    | 44%             | -7.6% to +4.5%    |
| gold       |  4031.3   | 2026-11-24    | -0.6%    | 46%             | -7.8% to +8.2%    |
| msci_world |   205.15  | 2026-11-23    | +2.1%    | 79%             | -1.2% to +4.5%    |
| nasdaq100  | 28957.5   | 2026-11-23    | +1.9%    | 65%             | -4.9% to +7.6%    |
| nvda       |   210.96  | 2026-11-23    | -0.2%    | 49%             | -11.4% to +10.7%  |
| oil_wti    |   101.1   | 2026-11-24    | -4.5%    | 34%             | -19.4% to +10.8%  |
| silver     |    54.09  | 2026-11-24    | -0.9%    | 47%             | -12.8% to +16.3%  |
| sp500      |  7623.68  | 2026-11-23    | +1.7%    | 74%             | -1.9% to +4.3%    |
| tsla       |   372.22  | 2026-11-23    | -0.4%    | 49%             | -17.2% to +16.6%  |
| xom        |   183.21  | 2026-11-23    | +1.0%    | 54%             | -10.4% to +14.3%  |

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
| tech_composite    |     0.616 | 2026-11-22    | +5.4%    | 72%             | -5.4% to +22.2%   |
| wiki_ai           | 12179     | 2026-11-22    | -4.7%    | 38%             | -20.1% to +21.8%  |
| wiki_crispr       |   639     | 2026-11-22    | -0.6%    | 48%             | -15.0% to +20.8%  |
| wiki_ev           |   340     | 2026-11-22    | +12.6%   | 83%             | -3.5% to +37.0%   |
| wiki_fusion       |   501     | 2026-11-22    | +3.6%    | 58%             | -15.9% to +36.6%  |
| wiki_humanoid     |   250     | 2026-11-22    | +11.3%   | 77%             | -7.1% to +46.1%   |
| wiki_llm          |  2789     | 2026-11-22    | -1.1%    | 45%             | -11.0% to +14.5%  |
| wiki_quantum      |  1350     | 2026-11-22    | +6.7%    | 67%             | -9.3% to +39.5%   |

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
