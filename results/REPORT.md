# World Predictor: Seldon scorecard

_Generated 2026-10-19 with model `timesfm-2.5`. Skill = 1 - MAE(model) / MAE(naive random walk); positive is better than naive. Coverage80 should be close to 0.80 for an honest forecaster. Brier scores the probability of going up (0.25 = coin flip, lower is better). See docs/METHODOLOGY.md._

## In plain English

- timesfm-2.5 beat the simple guess "tomorrow looks like today" in 2 of 3 areas: world news (12% less error), technology (43% less error).
- Seldon was right here: big aggregates such as indices and averages were easier to predict than single stocks or topics (28% vs 12% skill).
- In world news, its edge lasts up to about 28 days ahead.
- In markets, it had no edge at any distance ahead.
- In technology, its edge lasts up to about 28 days ahead.
- When it gave 70% or more odds of a rise, the rise really happened 84% of the time (31 forecasts).

![Replay of past forecasts against what really happened](plots/replay.gif)

_Each frame is a forecast made in the past: the orange band is what the model expected, the dark dots are what really happened._

## 1. Can the future be predicted?

![Skill by domain](plots/skill_by_domain.png)

- **World events in the news**: timesfm-2.5 beats the naive baseline (12% less error).
- **Stock and value markets**: timesfm-2.5 about the same as the naive baseline.
- **New technologies**: timesfm-2.5 beats the naive baseline (43% less error).

| domain   | model        |   series |   median_skill |   median_mase |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|---------------:|--------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |       12 |         -0.001 |         3.905 |       0.499 |        0.798 |   0.260 |
| markets  | chronos-bolt |       12 |         -0.045 |         4.118 |       0.561 |        0.813 |   0.259 |
| markets  | drift        |       12 |          0.009 |         3.729 |       0.533 |        0.654 |   0.264 |
| markets  | ensemble     |       12 |          0.017 |         3.802 |       0.588 |        0.830 |   0.248 |
| markets  | mean         |       12 |         -1.292 |         8.428 |       0.489 |        0.488 |   0.370 |
| markets  | naive        |       12 |          0.000 |         3.869 |     nan     |        0.642 |   0.250 |
| markets  | timesfm-2.5  |       12 |          0.008 |         3.830 |       0.523 |        0.829 |   0.245 |
| news     | auto-ets     |        5 |         -0.241 |         1.787 |       0.533 |        0.887 |   0.246 |
| news     | chronos-bolt |        5 |          0.037 |         1.139 |       0.650 |        0.743 |   0.212 |
| news     | drift        |        5 |         -0.009 |         1.549 |       0.383 |        0.848 |   0.260 |
| news     | ensemble     |        5 |          0.102 |         1.258 |       0.633 |        0.843 |   0.223 |
| news     | mean         |        5 |          0.001 |         1.294 |       0.567 |        0.686 |   0.263 |
| news     | naive        |        5 |          0.000 |         1.535 |     nan     |        0.849 |   0.250 |
| news     | timesfm-2.5  |        5 |          0.117 |         1.100 |       0.667 |        0.791 |   0.214 |
| tech     | auto-ets     |        8 |         -0.468 |         2.057 |       0.509 |        0.959 |   0.259 |
| tech     | chronos-bolt |        8 |          0.411 |         0.753 |       0.725 |        0.759 |   0.174 |
| tech     | drift        |        8 |          0.005 |         1.268 |       0.485 |        0.866 |   0.256 |
| tech     | ensemble     |        8 |          0.172 |         1.135 |       0.580 |        0.931 |   0.223 |
| tech     | mean         |        8 |          0.121 |         1.076 |       0.750 |        0.713 |   0.170 |
| tech     | naive        |        8 |          0.000 |         1.280 |     nan     |        0.866 |   0.250 |
| tech     | timesfm-2.5  |        8 |          0.426 |         0.738 |       0.767 |        0.763 |   0.158 |

## 2. Seldon's law of large numbers: aggregates vs individuals

Psychohistory only claims to work for very large populations. If that holds here, aggregate series (indices, composites, world totals) should show higher skill and lower MASE than individual ones.

| domain   | scale      | model       |   series |   median_skill |   median_mase |
|:---------|:-----------|:------------|---------:|---------------:|--------------:|
| markets  | aggregate  | timesfm-2.5 |        3 |          0.096 |         2.507 |
| markets  | individual | timesfm-2.5 |        9 |         -0.010 |         4.366 |
| news     | individual | timesfm-2.5 |        5 |          0.117 |         1.100 |
| tech     | aggregate  | timesfm-2.5 |        1 |          0.458 |         0.641 |
| tech     | individual | timesfm-2.5 |        7 |          0.405 |         0.834 |

## 3. Seldon crises: what the model did not see coming

Backtest windows where most actual values fell outside the model's 80% band.

| series_id     | domain   | origin     |   coverage80 |   mase |
|:--------------|:---------|:-----------|-------------:|-------:|
| silver        | markets  | 2026-06-17 |        0.048 | 14.223 |
| xom           | markets  | 2026-01-15 |        0.095 | 12.983 |
| oil_wti       | markets  | 2026-02-17 |        0.143 | 12.029 |
| wiki_crispr   | tech     | 2026-03-05 |        0.143 |  1.030 |
| gold          | markets  | 2026-06-17 |        0.190 | 11.173 |
| aapl          | markets  | 2025-10-15 |        0.190 |  7.108 |
| wiki_humanoid | tech     | 2025-12-11 |        0.214 |  1.828 |
| oil_wti       | markets  | 2026-05-18 |        0.286 | 10.667 |
| wiki_fusion   | tech     | 2026-06-25 |        0.286 |  1.044 |
| wiki_quantum  | tech     | 2025-12-11 |        0.286 |  0.875 |
| bitcoin       | markets  | 2026-05-31 |        0.357 |  7.163 |
| news_climate  | news     | 2026-02-16 |        0.357 |  1.206 |
| wiki_crispr   | tech     | 2026-06-25 |        0.357 |  0.629 |
| wiki_ai       | tech     | 2026-07-23 |        0.393 |  1.264 |
| gold          | markets  | 2026-01-15 |        0.429 | 16.609 |

## 4. Prediction ledger (true out-of-sample test)

![Time Vault track record](plots/track_record.png)

_Predictions are sealed with a date before the future happens and opened when it arrives. The left line should settle near 80%; the right line should sit below the coin-flip line._

| domain   | model        |   series |   predictions |   median_skill |   direction |   coverage80 |   brier |
|:---------|:-------------|---------:|--------------:|---------------:|------------:|-------------:|--------:|
| markets  | auto-ets     |        5 |             5 |          0.000 |       0.600 |        1.000 |   0.249 |
| markets  | chronos-bolt |        5 |             5 |         -0.112 |       0.600 |        1.000 |   0.271 |
| markets  | ensemble     |        5 |             5 |          0.025 |       0.600 |        1.000 |   0.243 |
| markets  | timesfm-2.5  |        5 |             5 |          0.141 |       0.800 |        1.000 |   0.224 |
| news     | auto-ets     |        3 |             3 |          0.007 |       0.667 |        1.000 |   0.211 |
| news     | chronos-bolt |        3 |             3 |          0.022 |       0.667 |        0.667 |   0.316 |
| news     | ensemble     |        3 |             3 |          0.009 |       0.667 |        0.667 |   0.295 |
| news     | timesfm-2.5  |        3 |             3 |         -0.372 |       0.333 |        0.667 |   0.401 |
| tech     | auto-ets     |        8 |            24 |         -0.065 |       0.417 |        0.875 |   0.250 |
| tech     | chronos-bolt |        8 |            24 |          0.654 |       0.750 |        0.875 |   0.160 |
| tech     | ensemble     |        8 |            24 |          0.455 |       0.750 |        0.917 |   0.156 |
| tech     | timesfm-2.5  |        8 |            24 |          0.643 |       0.750 |        0.833 |   0.160 |

## 5. How far ahead can it see?

Median skill versus the naive baseline by how many steps ahead the forecast is (days for news and tech attention, trading days for markets; yearly adoption series are too short for this and are left out). Where skill drops to zero is the limit of the model's foresight in that domain.

![Skill by step](plots/skill_by_step.png)

| domain   |   1 step |    2-5 |   6-10 |   11-20 |   21+ |
|:---------|---------:|-------:|-------:|--------:|------:|
| markets  |    0.021 | -0.016 |  0.001 |   0.006 | 0.015 |
| news     |    0.173 |  0.204 |  0.082 |   0.189 | 0.128 |
| tech     |    0.277 |  0.447 |  0.255 |   0.322 | 0.320 |

## 6. Are its odds honest?

Backtest forecasts grouped by the chance they gave of the series ending higher. `said` is the average probability given, `happened` is how often it really went up. When the two match, the odds can be taken at face value.

| domain   | odds given   |   forecasts |   said |   happened |
|:---------|:-------------|------------:|-------:|-----------:|
| markets  | 20%-40%      |           9 |  0.376 |      0.444 |
| markets  | 40%-60%      |         103 |  0.484 |      0.553 |
| markets  | 60%-80%      |          32 |  0.651 |      0.688 |
| news     | 0%-20%       |           8 |  0.136 |      0.000 |
| news     | 20%-40%      |          15 |  0.297 |      0.467 |
| news     | 40%-60%      |          21 |  0.496 |      0.619 |
| news     | 60%-80%      |          12 |  0.693 |      0.583 |
| news     | 80%-100%     |           4 |  0.858 |      1.000 |
| tech     | 0%-20%       |          16 |  0.113 |      0.000 |
| tech     | 20%-40%      |          23 |  0.324 |      0.261 |
| tech     | 40%-60%      |          22 |  0.530 |      0.273 |
| tech     | 60%-80%      |          28 |  0.690 |      0.821 |
| tech     | 80%-100%     |           7 |  0.867 |      1.000 |

## 7. Every series

| series_id      | domain   | scale      | model       |      mae |   mase |   smape |   direction |   coverage80 |   pinball |   brier |   skill |   prob_skill |
|:---------------|:---------|:-----------|:------------|---------:|-------:|--------:|------------:|-------------:|----------:|--------:|--------:|-------------:|
| aapl           | markets  | individual | timesfm-2.5 |    9.790 |  4.177 |   0.034 |       0.417 |        0.782 |     1.622 |   0.253 |  -0.010 |        0.009 |
| bitcoin        | markets  | individual | timesfm-2.5 | 4133.105 |  3.301 |   0.057 |       0.583 |        0.869 |     1.406 |   0.252 |   0.009 |       -0.034 |
| copper         | markets  | individual | timesfm-2.5 |    0.186 |  3.482 |   0.032 |       0.417 |        0.897 |     1.377 |   0.276 |  -0.074 |       -0.086 |
| gold           | markets  | individual | timesfm-2.5 |  194.031 |  8.547 |   0.043 |       0.333 |        0.738 |     3.326 |   0.269 |  -0.018 |        0.087 |
| msci_world     | markets  | aggregate  | timesfm-2.5 |    2.361 |  2.425 |   0.012 |       0.750 |        0.825 |     0.970 |   0.204 |   0.132 |        0.149 |
| nasdaq100      | markets  | aggregate  | timesfm-2.5 |  603.216 |  3.373 |   0.022 |       0.583 |        0.790 |     1.354 |   0.236 |   0.063 |        0.075 |
| news_climate   | news     | individual | timesfm-2.5 |    0.146 |  1.100 |   0.174 |       0.583 |        0.765 |     0.425 |   0.238 |  -0.063 |       -0.009 |
| news_election  | news     | individual | timesfm-2.5 |    0.526 |  1.067 |   0.127 |       0.750 |        0.842 |     0.430 |   0.199 |   0.305 |        0.323 |
| news_inflation | news     | individual | timesfm-2.5 |    0.290 |  0.947 |   0.151 |       0.583 |        0.771 |     0.370 |   0.236 |   0.117 |        0.131 |
| news_pandemic  | news     | individual | timesfm-2.5 |    0.220 |  1.181 |   0.109 |       0.583 |        0.777 |     0.478 |   0.221 |   0.337 |        0.365 |
| news_protest   | news     | individual | timesfm-2.5 |    0.425 |  1.448 |   0.182 |       0.833 |        0.801 |     0.603 |   0.174 |   0.076 |        0.108 |
| nvda           | markets  | individual | timesfm-2.5 |    8.353 |  4.366 |   0.042 |       0.500 |        0.857 |     1.731 |   0.240 |  -0.046 |       -0.058 |
| oil_wti        | markets  | individual | timesfm-2.5 |    7.186 |  5.038 |   0.085 |       0.500 |        0.746 |     1.990 |   0.233 |   0.024 |        0.109 |
| silver         | markets  | individual | timesfm-2.5 |    6.568 | 12.044 |   0.094 |       0.417 |        0.817 |     4.480 |   0.261 |   0.007 |        0.186 |
| sp500          | markets  | aggregate  | timesfm-2.5 |   94.893 |  2.507 |   0.013 |       0.750 |        0.841 |     0.987 |   0.206 |   0.096 |        0.133 |
| tech_composite | tech     | aggregate  | timesfm-2.5 |    0.066 |  0.641 |   0.079 |       0.583 |        0.768 |     0.261 |   0.218 |   0.458 |        0.447 |
| tsla           | markets  | individual | timesfm-2.5 |   19.005 |  2.524 |   0.048 |       0.667 |        0.960 |     1.020 |   0.229 |   0.042 |        0.001 |
| wiki_ai        | tech     | individual | timesfm-2.5 | 1412.887 |  1.044 |   0.108 |       0.833 |        0.762 |     0.430 |   0.131 |   0.405 |        0.388 |
| wiki_crispr    | tech     | individual | timesfm-2.5 |   98.530 |  0.643 |   0.124 |       0.917 |        0.702 |     0.257 |   0.111 |   0.447 |        0.442 |
| wiki_ev        | tech     | individual | timesfm-2.5 |   45.997 |  0.495 |   0.102 |       0.636 |        0.807 |     0.194 |   0.218 |   0.263 |        0.364 |
| wiki_fusion    | tech     | individual | timesfm-2.5 |   97.904 |  0.834 |   0.125 |       0.750 |        0.717 |     0.349 |   0.164 |   0.398 |        0.358 |
| wiki_humanoid  | tech     | individual | timesfm-2.5 |   54.893 |  0.928 |   0.149 |       0.833 |        0.771 |     0.385 |   0.119 |   0.341 |        0.318 |
| wiki_llm       | tech     | individual | timesfm-2.5 |  282.001 |  0.514 |   0.083 |       0.833 |        0.801 |     0.211 |   0.135 |   0.512 |        0.519 |
| wiki_quantum   | tech     | individual | timesfm-2.5 |  356.300 |  0.910 |   0.127 |       0.750 |        0.774 |     0.400 |   0.167 |   0.446 |        0.404 |
| xom            | markets  | individual | timesfm-2.5 |    6.137 |  4.955 |   0.043 |       0.364 |        0.825 |     1.927 |   0.285 |  -0.064 |       -0.030 |

## 8. What the model expects next

![What the model expects next](plots/outlook.png)

Latest forecasts recorded in the ledger (made with data up to each series' last date). Changes are relative to the last observed value; the range is the 10%-90% band; "chance higher" is the model's probability that the value on the target date is above today's (scored later with the Brier score: 0 is perfect, 0.25 is a coin flip).

### World events in the news

| series         |   last | target date   | median   | chance higher   | range (10%-90%)   |
|:---------------|-------:|:--------------|:---------|:----------------|:------------------|
| news_climate   |  0.83  | 2026-11-16    | +4.9%    | 59%             | -20.3% to +45.4%  |
| news_composite |  1.173 | 2026-11-16    | -25.8%   | 5%              | -36.3% to -7.7%   |
| news_election  |  7.01  | 2026-11-16    | -25.0%   | 18%             | -43.4% to +13.9%  |
| news_inflation |  2.454 | 2026-11-16    | -20.4%   | 17%             | -40.1% to +7.7%   |
| news_pandemic  |  1.64  | 2026-11-16    | -3.6%    | 38%             | -17.8% to +16.9%  |
| news_protest   |  4.514 | 2026-11-16    | -52.7%   | 5%              | -65.0% to -23.8%  |

![news_climate](plots/news_climate.png)
![news_composite](plots/news_composite.png)
![news_election](plots/news_election.png)
![news_inflation](plots/news_inflation.png)
![news_pandemic](plots/news_pandemic.png)
![news_protest](plots/news_protest.png)

### Stock and value markets

| series     |      last | target date   | median   | chance higher   | range (10%-90%)   |
|:-----------|----------:|:--------------|:---------|:----------------|:------------------|
| aapl       |   343.46  | 2026-11-16    | +0.8%    | 56%             | -6.1% to +6.7%    |
| bitcoin    | 82300     | 2026-11-16    | +0.0%    | 50%             | -15.2% to +16.3%  |
| copper     |     6.576 | 2026-11-17    | +0.1%    | 51%             | -7.4% to +4.5%    |
| gold       |  4190.1   | 2026-11-17    | -0.0%    | 50%             | -7.3% to +8.9%    |
| msci_world |   206.34  | 2026-11-16    | +1.7%    | 73%             | -1.9% to +4.0%    |
| nasdaq100  | 29187.6   | 2026-11-16    | +2.0%    | 64%             | -5.7% to +7.9%    |
| nvda       |   214.13  | 2026-11-16    | -0.2%    | 49%             | -12.3% to +11.1%  |
| oil_wti    |    98.19  | 2026-11-17    | -4.7%    | 33%             | -18.8% to +10.5%  |
| silver     |    57.76  | 2026-11-17    | -0.2%    | 49%             | -12.7% to +17.9%  |
| sp500      |  7659.44  | 2026-11-16    | +1.5%    | 71%             | -2.2% to +4.0%    |
| tsla       |   354.72  | 2026-11-16    | -0.7%    | 48%             | -18.5% to +17.6%  |
| xom        |   178.98  | 2026-11-16    | +0.8%    | 53%             | -9.7% to +13.0%   |

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
| tech_composite    |     0.622 | 2026-11-15    | +9.1%    | 84%             | -1.9% to +25.8%   |
| wiki_ai           | 11974     | 2026-11-15    | -0.4%    | 49%             | -19.4% to +31.3%  |
| wiki_crispr       |   673     | 2026-11-15    | -1.0%    | 47%             | -15.0% to +19.2%  |
| wiki_ev           |   396     | 2026-11-15    | -3.0%    | 39%             | -17.3% to +18.2%  |
| wiki_fusion       |   471     | 2026-11-15    | +11.6%   | 75%             | -9.4% to +45.9%   |
| wiki_humanoid     |   233     | 2026-11-15    | +22.0%   | 90%             | -0.1% to +60.7%   |
| wiki_llm          |  2942     | 2026-11-15    | +0.4%    | 52%             | -10.3% to +16.8%  |
| wiki_quantum      |  1322     | 2026-11-15    | +12.0%   | 79%             | -5.2% to +47.6%   |

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
