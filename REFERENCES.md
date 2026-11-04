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
| 17 | [projectmesa/mesa](https://github.com/projectmesa/mesa) | **Inspired** `psychohistory simulate`. Agent-based modelling in Python, the closest open-source cousin of psychohistory: simulate many individuals and watch aggregate behaviour emerge. The toy crowd here is plain NumPy in the same spirit. |

### Visuals and presentation

| # | Repository | What it contributes here |
|---|---|---|
| 18 | [plotly/plotly.py](https://github.com/plotly/plotly.py) | **Used**: the interactive `results/dashboard.html`, with hover tooltips and a series picker on the fan chart. |
| 19 | [owid/owid-grapher](https://github.com/owid/owid-grapher) | Our World in Data's chart engine. Its one-question-per-chart layout, plain captions, play-button timelines and source lines are the model for the dashboard and its animated replay. |
| 20 | [streamlit/streamlit](https://github.com/streamlit/streamlit) | Python apps for data exploration. The natural next step if the dashboard becomes an interactive app with live re-forecasting. |

## Modelling theories behind the tests

| Theory | Source | Where it shows up |
|---|---|---|
| Psychohistory | Isaac Asimov, *Foundation* (1951) | The whole project: forecast populations, not individuals. |
| Cliodynamics | Peter Turchin, *Historical Dynamics* (2003); the Seshat Global History Databank | The real-world attempt at mathematical history, and the scientific framing for the news domain. |
| Law of large numbers | Jacob Bernoulli, *Ars Conjectandi* (1713) | Test 2: aggregates should be more predictable than individuals. Shown directly by the toy crowd in `psychohistory simulate`. |
| Efficient-market hypothesis | Eugene Fama, "Efficient Capital Markets" (1970) | Why the naive random walk is the right market baseline, and why beating it is hard. |
| Fat tails and black swans | Benoit Mandelbrot (1963); Nassim Taleb, *The Black Swan* (2007) | Test 5, Seldon crises: shocks that fall outside forecast bands. |
| Chaos and limits to predictability | Edward Lorenz, "Deterministic Nonperiodic Flow" (1963) | Test 3, the Seldon horizon: skill should decay as the forecast reaches further ahead. |
| Forecast combination | Bates and Granger, "The Combination of Forecasts" (1969) | **Built in**: Seldon weighs its laws by their past error, a sharpened Bates-Granger combination. |
| Damped trend | Gardner and McKenzie, "Forecasting Trends in Time Series" (1985) | Seldon's momentum law: a trend that fades a little every step. |
| Mean reversion | Uhlenbeck and Ornstein, "On the Theory of the Brownian Motion" (1930) | Seldon's reversion law: an excited series is pulled back toward its recent normal. |
| Forecasting competitions | Makridakis, Spiliotis and Assimakopoulos, "The M4 Competition" (2020) | The held-out public data Seldon is checked on (`scripts/seldon_m4_check.py`). |
| Bass diffusion model | Frank Bass, "A New Product Growth Model" (1969) | **Built in** as the `bass` model: an S-curve fitted to each technology-adoption series and run against TimesFM. |
| Gartner hype cycle | Gartner (1995) | Why attention to a technology (Wikipedia views) spikes and fades even while adoption keeps rising. |
| Proper scoring rules | Glenn Brier (1950); Gneiting and Raftery (2007) | Brier and pinball scores; honest odds (test 4). |
| Superforecasting | Philip Tetlock and Dan Gardner, *Superforecasting* (2015) | Keeping a dated prediction ledger and scoring calibration over time. |
| Forecast accuracy measures | Hyndman and Koehler (2006) | MASE, which makes gold prices and news shares comparable. |
| Forecast combination puzzle | Stock and Watson (2004); Smith and Wallis (2009); Timmermann (2006); Clemen (1989) | The bake-off (`scripts/seldon_bakeoff.py`): weights learned from a short record tend to lose to simple ones, which is why Seldon's share rule now waits for ten windows and a 2% edge. |
| Averaging quantiles | Lichtendahl, Grushka-Cockayne and Winkler (2013) | **Built in**: the full Seldon blends TimesFM and the laws decile by decile. |
| Volatility clustering | Engle (1982); Bollerslev (1986) | The GARCH(1,1) volatility forecasts. |
| Small-sample tests | Student (1908); Diebold and Mariano (1995); Harvey, Leybourne and Newbold (1997); Benjamini and Hochberg (1995) | The monitor's drift alarms and the year ledger's "real or luck" verdict on each series. |
| Split normal | Wallis (2014) | Event odds: reading a spike or lull probability off a forecast's 10%, 50% and 90% levels. |
| Rule of succession, skill scores | Laplace (1814); Wilks (2011) | Event odds: the persistence baseline and the Brier skill score. |
| Behavioural finance | Jegadeesh and Titman (1993); De Bondt and Thaler (1985); Lehmann (1990); Moskowitz, Ooi and Pedersen (2012); Daniel and Moskowitz (2016); Shiller (2000) | **Built in**: Radiant's core turns momentum, overreaction, short-term reversal and momentum crashes into signals. |
| Herding and attention | Bikhchandani, Hirshleifer and Welch (1992); Barber and Odean (2008); Da, Engelberg and Gao (2011) | Radiant's momentum and attention-spike signals; why news and interest burst and fade. |
| Fear gauge | Whaley (2000) | The VIX, tracked in the year ledger and the terminal. |
| Learning from experts | Freund and Schapire (1997); Cesa-Bianchi and Lugosi (2006); Hoerl and Kennard (1970) | **Built in**: Radiant's exponential-weights mix, and the ridge regression behind its core. |

## App design basis

| Project | Licence | What World Predictor takes from it |
|---|---|---|
| [koala73/worldmonitor](https://github.com/koala73/worldmonitor) | AGPL-3.0 | The idea of one app shipped two ways: a GitHub Pages web app and a downloadable full version. Ideas only, no code copied. |
| [Normansrule/worldmonitor](https://github.com/Normansrule/worldmonitor) (Terra Atlas) | AGPL-3.0 | The `site/` + `site/app/` Pages layout and the tag-driven release workflow, re-implemented from scratch. |

## Bibliography (APA 7th edition)

Every source this project uses or learns from, in APA style (American Psychological Association,
7th edition). Web pages and repositories without a publication date are cited as (n.d.), "no
date", with the day they were retrieved; several undated works by one author are told apart as
(n.d.-a), (n.d.-b) and so on.

### Research papers and books

- Ansari, A. F., Stella, L., Turkmen, C., Zhang, X., Mercado, P., Shen, H., Shchur, O., Rangapuram, S. S., Pineda Arango, S., Kapoor, S., Zschiegner, J., Maddix, D. C., Wang, H., Mahoney, M. W., Torkkola, K., Wilson, A. G., Bohlke-Schneider, M., & Wang, Y. (2024). Chronos: Learning the language of time series. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2403.07815
- Asimov, I. (1951). *Foundation*. Gnome Press.
- Asimov, I. (1953). *Second Foundation*. Gnome Press.
- Assimakopoulos, V., & Nikolopoulos, K. (2000). The theta model: A decomposition approach to forecasting. *International Journal of Forecasting, 16*(4), 521–530. https://doi.org/10.1016/S0169-2070(00)00066-2
- Barber, B. M., & Odean, T. (2008). All that glitters: The effect of attention and news on the buying behavior of individual and institutional investors. *The Review of Financial Studies, 21*(2), 785–818. https://doi.org/10.1093/rfs/hhm079
- Bass, F. M. (1969). A new product growth for model consumer durables. *Management Science, 15*(5), 215–227. https://doi.org/10.1287/mnsc.15.5.215
- Bates, J. M., & Granger, C. W. J. (1969). The combination of forecasts. *Operational Research Quarterly, 20*(4), 451–468. https://doi.org/10.1057/jors.1969.103
- Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society: Series B (Methodological), 57*(1), 289–300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x
- Bernoulli, J. (1713). *Ars conjectandi*. Thurnisiorum.
- Bikhchandani, S., Hirshleifer, D., & Welch, I. (1992). A theory of fads, fashion, custom, and cultural change as informational cascades. *Journal of Political Economy, 100*(5), 992–1026. https://doi.org/10.1086/261849
- Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity. *Journal of Econometrics, 31*(3), 307–327. https://doi.org/10.1016/0304-4076(86)90063-1
- Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review, 78*(1), 1–3. https://doi.org/10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2
- Cesa-Bianchi, N., & Lugosi, G. (2006). *Prediction, learning, and games*. Cambridge University Press. https://doi.org/10.1017/CBO9780511546921
- Clemen, R. T. (1989). Combining forecasts: A review and annotated bibliography. *International Journal of Forecasting, 5*(4), 559–583. https://doi.org/10.1016/0169-2070(89)90012-5
- Da, Z., Engelberg, J., & Gao, P. (2011). In search of attention. *The Journal of Finance, 66*(5), 1461–1499. https://doi.org/10.1111/j.1540-6261.2011.01679.x
- Daniel, K., & Moskowitz, T. J. (2016). Momentum crashes. *Journal of Financial Economics, 122*(2), 221–247. https://doi.org/10.1016/j.jfineco.2015.12.002
- Das, A., Kong, W., Sen, R., & Zhou, Y. (2024). A decoder-only foundation model for time-series forecasting. In *Proceedings of the 41st International Conference on Machine Learning* (Proceedings of Machine Learning Research, Vol. 235). PMLR. https://arxiv.org/abs/2310.10688
- De Bondt, W. F. M., & Thaler, R. (1985). Does the stock market overreact? *The Journal of Finance, 40*(3), 793–805. https://doi.org/10.1111/j.1540-6261.1985.tb05004.x
- Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics, 13*(3), 253–263. https://doi.org/10.1080/07350015.1995.10524599
- Engle, R. F. (1982). Autoregressive conditional heteroscedasticity with estimates of the variance of United Kingdom inflation. *Econometrica, 50*(4), 987–1007. https://doi.org/10.2307/1912773
- Fama, E. F. (1970). Efficient capital markets: A review of theory and empirical work. *The Journal of Finance, 25*(2), 383–417. https://doi.org/10.2307/2325486
- Fenn, J., & Raskino, M. (2008). *Mastering the hype cycle: How to choose the right innovation at the right time*. Harvard Business Press.
- Freund, Y., & Schapire, R. E. (1997). A decision-theoretic generalization of on-line learning and an application to boosting. *Journal of Computer and System Sciences, 55*(1), 119–139. https://doi.org/10.1006/jcss.1997.1504
- Gardner, E. S., Jr., & McKenzie, E. (1985). Forecasting trends in time series. *Management Science, 31*(10), 1237–1246. https://doi.org/10.1287/mnsc.31.10.1237
- Gneiting, T., & Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *Journal of the American Statistical Association, 102*(477), 359–378. https://doi.org/10.1198/016214506000001437
- Harvey, D., Leybourne, S., & Newbold, P. (1997). Testing the equality of prediction mean squared errors. *International Journal of Forecasting, 13*(2), 281–291. https://doi.org/10.1016/S0169-2070(96)00719-4
- Herbster, M., & Warmuth, M. K. (1998). Tracking the best expert. *Machine Learning, 32*(2), 151–178. https://doi.org/10.1023/A:1007424614876
- Hoerl, A. E., & Kennard, R. W. (1970). Ridge regression: Biased estimation for nonorthogonal problems. *Technometrics, 12*(1), 55–67. https://doi.org/10.1080/00401706.1970.10488634
- Hyndman, R. J., & Billah, B. (2003). Unmasking the Theta method. *International Journal of Forecasting, 19*(2), 287–290. https://doi.org/10.1016/S0169-2070(01)00143-1
- Hyndman, R. J., & Khandakar, Y. (2008). Automatic time series forecasting: The forecast package for R. *Journal of Statistical Software, 27*(3), 1–22. https://doi.org/10.18637/jss.v027.i03
- Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting, 22*(4), 679–688. https://doi.org/10.1016/j.ijforecast.2006.03.001
- Hyndman, R. J., Koehler, A. B., Snyder, R. D., & Grose, S. (2002). A state space framework for automatic forecasting using exponential smoothing methods. *International Journal of Forecasting, 18*(3), 439–454. https://doi.org/10.1016/S0169-2070(01)00110-8
- Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market efficiency. *The Journal of Finance, 48*(1), 65–91. https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
- J.P. Morgan/Reuters. (1996). *RiskMetrics: Technical document* (4th ed.). Morgan Guaranty Trust Company.
- Kivinen, J., & Warmuth, M. K. (1997). Exponentiated gradient versus gradient descent for linear predictors. *Information and Computation, 132*(1), 1–63. https://doi.org/10.1006/inco.1996.2612
- Koenker, R., & Bassett, G., Jr. (1978). Regression quantiles. *Econometrica, 46*(1), 33–50. https://doi.org/10.2307/1913643
- Laplace, P.-S. (1814). *Essai philosophique sur les probabilités*. Courcier.
- Leetaru, K., & Schrodt, P. A. (2013, April). *GDELT: Global data on events, location, and tone, 1979–2012* [Paper presentation]. International Studies Association Annual Convention, San Francisco, CA, United States.
- Lehmann, B. N. (1990). Fads, martingales, and market efficiency. *The Quarterly Journal of Economics, 105*(1), 1–28. https://doi.org/10.2307/2937816
- Lichtendahl, K. C., Jr., Grushka-Cockayne, Y., & Winkler, R. L. (2013). Is it better to average probabilities or quantiles? *Management Science, 59*(7), 1594–1611. https://doi.org/10.1287/mnsc.1120.1667
- Lorenz, E. N. (1963). Deterministic nonperiodic flow. *Journal of the Atmospheric Sciences, 20*(2), 130–141. https://doi.org/10.1175/1520-0469(1963)020<0130:DNF>2.0.CO;2
- Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2020). The M4 Competition: 100,000 time series and 61 forecasting methods. *International Journal of Forecasting, 36*(1), 54–74. https://doi.org/10.1016/j.ijforecast.2019.04.014
- Mandelbrot, B. (1963). The variation of certain speculative prices. *The Journal of Business, 36*(4), 394–419. https://doi.org/10.1086/294632
- Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). Time series momentum. *Journal of Financial Economics, 104*(2), 228–250. https://doi.org/10.1016/j.jfineco.2011.11.003
- Newey, W. K., & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica, 55*(3), 703–708. https://doi.org/10.2307/1913610
- Patton, A. J. (2011). Volatility forecast comparison using imperfect volatility proxies. *Journal of Econometrics, 160*(1), 246–256. https://doi.org/10.1016/j.jeconom.2010.03.034
- Shiller, R. J. (2000). *Irrational exuberance*. Princeton University Press.
- Smith, J., & Wallis, K. F. (2009). A simple explanation of the forecast combination puzzle. *Oxford Bulletin of Economics and Statistics, 71*(3), 331–355. https://doi.org/10.1111/j.1468-0084.2008.00541.x
- Stock, J. H., & Watson, M. W. (2004). Combination forecasts of output growth in a seven-country data set. *Journal of Forecasting, 23*(6), 405–430. https://doi.org/10.1002/for.928
- Student. (1908). The probable error of a mean. *Biometrika, 6*(1), 1–25. https://doi.org/10.1093/biomet/6.1.1
- Taleb, N. N. (2007). *The black swan: The impact of the highly improbable*. Random House.
- Tashman, L. J. (2000). Out-of-sample tests of forecasting accuracy: An analysis and review. *International Journal of Forecasting, 16*(4), 437–450. https://doi.org/10.1016/S0169-2070(00)00065-0
- Tetlock, P. E., & Gardner, D. (2015). *Superforecasting: The art and science of prediction*. Crown.
- Timmermann, A. (2006). Forecast combinations. In G. Elliott, C. W. J. Granger, & A. Timmermann (Eds.), *Handbook of economic forecasting* (Vol. 1, pp. 135–196). Elsevier. https://doi.org/10.1016/S1574-0706(05)01004-9
- Turchin, P. (2003). *Historical dynamics: Why states rise and fall*. Princeton University Press.
- Uhlenbeck, G. E., & Ornstein, L. S. (1930). On the theory of the Brownian motion. *Physical Review, 36*(5), 823–841. https://doi.org/10.1103/PhysRev.36.823
- Wallis, K. F. (2014). The two-piece normal, binormal, or double Gaussian distribution: Its origin and rediscoveries. *Statistical Science, 29*(1), 106–112. https://doi.org/10.1214/13-STS417
- Whaley, R. E. (2000). The investor fear gauge. *The Journal of Portfolio Management, 26*(3), 12–17. https://doi.org/10.3905/jpm.2000.319728
- Wilks, D. S. (2011). *Statistical methods in the atmospheric sciences* (3rd ed.). Academic Press.

### Models, software and data

- Amazon Science. (n.d.). *chronos-forecasting* [Computer software]. GitHub. https://github.com/amazon-science/chronos-forecasting
- Amazon Web Services Labs. (n.d.). *gluonts* [Computer software]. GitHub. https://github.com/awslabs/gluonts
- Aroussi, R. (n.d.). *yfinance* [Computer software]. GitHub. https://github.com/ranaroussi/yfinance
- AutoGluon. (n.d.). *fev* [Computer software]. GitHub. https://github.com/autogluon/fev
- Bakaus, P. (n.d.). *impeccable* [Computer software]. GitHub. https://github.com/pbakaus/impeccable
- BlackRock. (n.d.). *iShares 20+ Year Treasury Bond ETF (TLT)* [Data set]. Retrieved November 2, 2026, from https://www.ishares.com/us/products/239454/
- Cboe Global Markets. (n.d.-a). *Cboe 10-Year U.S. Treasury Note Yield Index (TNX)* [Data set]. Retrieved November 2, 2026, from https://www.cboe.com/
- Cboe Global Markets. (n.d.-b). *Cboe Volatility Index (VIX)* [Data set]. Retrieved November 2, 2026, from https://www.cboe.com/tradable_products/vix/
- Garza, A., Mergenthaler Canseco, M., Challú, C., & Olivares, K. G. (2022). *StatsForecast: Lightning fast forecasting with statistical and econometric models* [Computer software]. GitHub. https://github.com/Nixtla/statsforecast
- Google Research. (n.d.). *timesfm* [Computer software]. GitHub. https://github.com/google-research/timesfm
- IBM. (n.d.). *IBM Plex* [Typeface]. GitHub. https://github.com/IBM/plex
- koala73. (n.d.). *worldmonitor* [Computer software]. GitHub. https://github.com/koala73/worldmonitor
- Kowalski, E. (n.d.). *skills* [Computer software]. GitHub. https://github.com/emilkowalski/skills
- Leonxlnx. (n.d.). *taste-skill* [Computer software]. GitHub. https://github.com/Leonxlnx/taste-skill
- Mcompetitions. (n.d.). *M4-methods* [Data set and computer software]. GitHub. https://github.com/Mcompetitions/M4-methods
- Meta. (n.d.). *prophet* [Computer software]. GitHub. https://github.com/facebook/prophet
- MOMENT contributors. (n.d.). *moment* [Computer software]. GitHub. https://github.com/moment-timeseries-foundation-model/moment
- Nixtla. (n.d.-a). *neuralforecast* [Computer software]. GitHub. https://github.com/Nixtla/neuralforecast
- Nixtla. (n.d.-b). *nixtla* [Computer software]. GitHub. https://github.com/Nixtla/nixtla
- Normansrule. (n.d.). *worldmonitor (Terra Atlas)* [Computer software]. GitHub. https://github.com/Normansrule/worldmonitor
- Our World in Data. (n.d.). *Our World in Data* [Data set]. Retrieved October 20, 2026, from https://ourworldindata.org/
- Plotly. (n.d.). *plotly.py* [Computer software]. GitHub. https://github.com/plotly/plotly.py
- Production Type. (n.d.). *Newsreader* [Typeface]. Google Fonts. https://fonts.google.com/specimen/Newsreader
- properscoring contributors. (n.d.). *properscoring* [Computer software]. GitHub. https://github.com/properscoring/properscoring
- Salesforce AI Research. (n.d.-a). *gift-eval* [Computer software]. GitHub. https://github.com/SalesforceAIResearch/gift-eval
- Salesforce AI Research. (n.d.-b). *uni2ts* [Computer software]. GitHub. https://github.com/SalesforceAIResearch/uni2ts
- Sheppard, K. (n.d.). *arch* [Computer software]. GitHub. https://github.com/bashtage/arch
- sktime contributors. (n.d.). *sktime* [Computer software]. GitHub. https://github.com/sktime/sktime
- statsmodels contributors. (n.d.). *statsmodels* [Computer software]. GitHub. https://github.com/statsmodels/statsmodels
- Streamlit. (n.d.). *streamlit* [Computer software]. GitHub. https://github.com/streamlit/streamlit
- The GDELT Project. (n.d.). *GDELT DOC 2.0 API* [Data set]. Retrieved October 20, 2026, from https://www.gdeltproject.org/
- time-series-foundation-models. (n.d.). *lag-llama* [Computer software]. GitHub. https://github.com/time-series-foundation-models/lag-llama
- Unit8. (n.d.). *darts* [Computer software]. GitHub. https://github.com/unit8co/darts
- Wikimedia Foundation. (n.d.). *Wikimedia REST API: Pageviews* [Data set]. Retrieved October 20, 2026, from https://wikimedia.org/api/rest_v1/
- Yahoo. (n.d.). *Yahoo Finance* [Data set]. Retrieved October 20, 2026, from https://finance.yahoo.com/

### Design and presentation

The sites and repositories behind the terminal's look and motion. [docs/DESIGN.md](docs/DESIGN.md)
says what was taken from each one.

- 1minus1. (n.d.). *1minus1*. Retrieved October 21, 2026, from https://1minus1.com/
- Apache Software Foundation. (n.d.). *echarts* [Computer software]. GitHub. https://github.com/apache/echarts
- Apple Inc. (n.d.-a). *AirPods Pro*. Retrieved October 20, 2026, from https://www.apple.com/airpods-pro/
- Apple Inc. (n.d.-b). *Apple*. Retrieved October 21, 2026, from https://www.apple.com/
- Apple Inc. (n.d.-c). *Apple Vision Pro*. Retrieved October 20, 2026, from https://www.apple.com/apple-vision-pro/
- Apple Inc. (n.d.-d). *Human interface guidelines*. Retrieved November 2, 2026, from https://developer.apple.com/design/human-interface-guidelines/
- Apple Inc. (n.d.-e). *MacBook Pro*. Retrieved October 20, 2026, from https://www.apple.com/macbook-pro/
- Astral Software Inc. (n.d.). *uv* [Computer software]. GitHub. https://github.com/astral-sh/uv
- Astro Technology Company. (n.d.). *starlight* [Computer software]. GitHub. https://github.com/withastro/starlight
- Asturiano, V. (n.d.). *globe.gl* [Computer software]. GitHub. https://github.com/vasturiano/globe.gl
- Awwwards. (n.d.-a). *AirPods Pro: Product scroll-triggered animation*. Retrieved October 20, 2026, from https://www.awwwards.com/inspiration/product-scroll-triggered-animation-apple-airpods-pro
- Awwwards. (n.d.-b). *Interactive product scroll animation for agricultural website: Farm Minerals*. Retrieved October 20, 2026, from https://www.awwwards.com/inspiration/interactive-product-scroll-animation-for-agricultural-website-farm-minerals
- Awwwards. (n.d.-c). *Interactive WebGL exploded view: IYO*. Retrieved October 20, 2026, from https://www.awwwards.com/inspiration/interactive-webgl-exploded-view-iyo
- Beccario, C. (n.d.-a). *earth* [Computer software]. GitHub. https://github.com/cambecc/earth
- Beccario, C. (n.d.-b). *earth: A global map of wind, weather, and ocean conditions*. Retrieved October 20, 2026, from https://earth.nullschool.net/
- Bostock, M. (n.d.). *d3* [Computer software]. GitHub. https://github.com/d3/d3
- Bycroft, B. (n.d.). *llm-viz* [Computer software]. GitHub. https://github.com/bbycroft/llm-viz
- Charm. (n.d.). *vhs* [Computer software]. GitHub. https://github.com/charmbracelet/vhs
- Ciechanowski, B. (n.d.). *Mechanical watch*. Retrieved October 20, 2026, from https://ciechanow.ski/mechanical-watch/
- Codrops. (n.d.). *Codrops*. Retrieved October 20, 2026, from https://tympanus.net/codrops/
- Comeau, J. W. (n.d.). *Scroll-driven animations*. Retrieved October 20, 2026, from https://joshwcomeau.com/animation/scroll-driven-animations
- darkroom.engineering. (n.d.). *lenis* [Computer software]. GitHub. https://github.com/darkroomengineering/lenis
- Ding, S. (n.d.). *cobe* [Computer software]. GitHub. https://github.com/shuding/cobe
- Distill. (n.d.). *Distill*. Retrieved October 20, 2026, from https://distill.pub/
- Dogstudio. (n.d.). *Dogstudio*. Retrieved October 21, 2026, from https://dogstudio.co/
- Excalidraw. (n.d.). *excalidraw* [Computer software]. GitHub. https://github.com/excalidraw/excalidraw
- Framework Computer Inc. (n.d.). *Framework*. Retrieved October 20, 2026, from https://frame.work/
- GitHub. (n.d.-a). *Basic writing and formatting syntax*. Retrieved October 20, 2026, from https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax
- GitHub. (n.d.-b). *How we built the GitHub globe*. Retrieved October 20, 2026, from https://github.blog/engineering/user-experience/how-we-built-the-github-globe/
- Goldenberg, R. (n.d.). *scrollama* [Computer software]. GitHub. https://github.com/russellsamora/scrollama
- Grafana Labs. (n.d.). *grafana* [Computer software]. GitHub. https://github.com/grafana/grafana
- GreenSock. (n.d.). *ScrollTrigger*. Retrieved October 20, 2026, from https://gsap.com/docs/v3/Plugins/ScrollTrigger/
- Igloo Inc. (n.d.). *Igloo Inc.*. Retrieved October 20, 2026, from https://www.igloo.inc/
- kepler.gl contributors. (n.d.). *kepler.gl* [Computer software]. GitHub. https://github.com/keplergl/kepler.gl
- kyechan99. (n.d.). *capsule-render* [Computer software]. GitHub. https://github.com/kyechan99/capsule-render
- Linear Orbit, Inc. (n.d.). *Linear*. Retrieved October 20, 2026, from https://linear.app/
- Lusion. (n.d.). *Lusion*. Retrieved October 20, 2026, from https://lusion.co/
- Magic UI. (n.d.). *magicui* [Computer software]. GitHub. https://github.com/magicuidesign/magicui
- MapLibre contributors. (n.d.). *maplibre-gl-js* [Computer software]. GitHub. https://github.com/maplibre/maplibre-gl-js
- MDN contributors. (n.d.-a). *view()*. Retrieved October 20, 2026, from https://developer.mozilla.org/en-US/docs/Web/CSS/animation-timeline/view
- MDN contributors. (n.d.-b). *View Transition API*. Retrieved October 20, 2026, from https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API
- Mesa contributors. (n.d.). *mesa* [Computer software]. GitHub. https://github.com/mesa/mesa
- Metaculus. (n.d.-a). *Metaculus*. Retrieved October 20, 2026, from https://www.metaculus.com/
- Metaculus. (n.d.-b). *metaculus* [Computer software]. GitHub. https://github.com/Metaculus/metaculus
- Motion Canvas contributors. (n.d.). *motion-canvas* [Computer software]. GitHub. https://github.com/motion-canvas/motion-canvas
- Motion Division Ltd. (n.d.-a). *Motion*. Retrieved October 20, 2026, from https://motion.dev/
- Motion Division Ltd. (n.d.-b). *motion* [Computer software]. GitHub. https://github.com/motiondivision/motion
- Nothing Technology Ltd. (n.d.). *Nothing*. Retrieved October 20, 2026, from https://nothing.tech/
- Observable, Inc. (n.d.-a). *Observable Plot*. Retrieved October 20, 2026, from https://observablehq.github.io/plot/
- Observable, Inc. (n.d.-b). *plot* [Computer software]. GitHub. https://github.com/observablehq/plot
- Our World in Data. (n.d.-b). *owid-grapher* [Computer software]. GitHub. https://github.com/owid/owid-grapher
- Polymarket. (n.d.). *Polymarket*. Retrieved October 20, 2026, from https://polymarket.com/
- The Pudding. (n.d.). *The Pudding*. Retrieved October 20, 2026, from https://pudding.cool/
- Raycast Technologies Ltd. (n.d.). *Raycast*. Retrieved October 20, 2026, from https://www.raycast.com/
- Reuters. (n.d.). *Reuters Graphics*. Retrieved October 20, 2026, from https://www.reuters.com/graphics/
- Rive, Inc. (n.d.). *Rive*. Retrieved October 20, 2026, from https://rive.app/
- shadcn. (n.d.). *ui* [Computer software]. GitHub. https://github.com/shadcn-ui/ui
- Simon, B. (n.d.). *Bruno Simon: Creative developer*. Retrieved October 20, 2026, from https://bruno-simon.com/
- Singers, M. (n.d.). *awesome-readme* [Computer software]. GitHub. https://github.com/matiassingers/awesome-readme
- Spline. (n.d.). *Spline*. Retrieved October 20, 2026, from https://spline.design/
- Stripe, Inc. (n.d.-a). *Stripe*. Retrieved October 20, 2026, from https://stripe.com/
- Stripe, Inc. (n.d.-b). *Stripe Press*. Retrieved October 20, 2026, from https://press.stripe.com/
- Supabase. (n.d.). *supabase* [Computer software]. GitHub. https://github.com/supabase/supabase
- Teenage Engineering. (n.d.). *Teenage Engineering*. Retrieved October 20, 2026, from https://teenage.engineering/
- Textualize. (n.d.). *rich* [Computer software]. GitHub. https://github.com/Textualize/rich
- tldraw. (n.d.). *tldraw* [Computer software]. GitHub. https://github.com/tldraw/tldraw
- Van Damme, B. (n.d.). *Scroll-driven animations*. Retrieved October 20, 2026, from https://scroll-driven-animations.style/
- Vercel Inc. (n.d.). *Vercel*. Retrieved October 20, 2026, from https://vercel.com/
- vis.gl contributors. (n.d.). *deck.gl* [Computer software]. GitHub. https://github.com/visgl/deck.gl
- Windyty, SE. (n.d.). *Windy*. Retrieved October 20, 2026, from https://www.windy.com/
- World Wide Web Consortium. (2023). *Web content accessibility guidelines (WCAG) 2.2* (W3C Recommendation). https://www.w3.org/TR/WCAG22/
- xyflow. (n.d.). *xyflow* [Computer software]. GitHub. https://github.com/xyflow/xyflow
