# Credits and attribution

World Predictor is a thin experimental layer on top of other people's open work. Everything it
uses is listed here with its licence or terms. If you reuse this project, please keep these
credits.

## Forecasting model

### TimesFM, Google Research
- Code: <https://github.com/google-research/timesfm> (Apache License 2.0)
- Python package: <https://pypi.org/project/timesfm/>
- Weights:
  - TimesFM 2.5 (default here): <https://huggingface.co/google/timesfm-2.5-200m-pytorch> (Apache License 2.0)
  - TimesFM 3.0 (optional): <https://huggingface.co/google/timesfm-3.0-pytorch>, licensed under
    `timesfm-non-commercial-license-v1.0`: non-commercial, non-production use only.
  - All releases: <https://huggingface.co/collections/google/timesfm-release-66e4be5fdb56e960c1e482a6>
- Paper: Abhimanyu Das, Weihao Kong, Rajat Sen, Yichen Zhou. *A decoder-only foundation model for
  time-series forecasting.* ICML 2024. <https://arxiv.org/abs/2310.10688>
- Blog posts: <https://research.google/blog/a-decoder-only-foundation-model-for-time-series-forecasting/>
  and <https://research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/>

TimesFM is "not an officially supported Google product" (from its README). This project is not
affiliated with or endorsed by Google.

```bibtex
@inproceedings{das2024decoder,
  title     = {A decoder-only foundation model for time-series forecasting},
  author    = {Das, Abhimanyu and Kong, Weihao and Sen, Rajat and Zhou, Yichen},
  booktitle = {Forty-first International Conference on Machine Learning},
  year      = {2024}
}
```

### Chronos, Amazon Science (optional rival model)
- Code: <https://github.com/amazon-science/chronos-forecasting> (Apache License 2.0)
- Weights: <https://huggingface.co/amazon/chronos-bolt-small> and <https://huggingface.co/amazon/chronos-2>;
  check each model card for its licence before commercial use.
- Paper: Abdul Fatir Ansari et al. *Chronos: Learning the Language of Time Series.* TMLR 2024.
  <https://arxiv.org/abs/2403.07815>

## Data sources

### World events: The GDELT Project
- DOC 2.0 API: <https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/>
- Home: <https://www.gdeltproject.org/>
- Terms: GDELT data is free and open for unlimited use with attribution:
  "The GDELT Project, https://www.gdeltproject.org/". <https://www.gdeltproject.org/about.html#termsofuse>

### Markets: Yahoo Finance via yfinance
- yfinance by Ran Aroussi and contributors: <https://github.com/ranaroussi/yfinance> (Apache License 2.0)
- Price data comes from Yahoo Finance. yfinance is not affiliated with Yahoo, and the data is
  intended for personal and research use under Yahoo's terms:
  <https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html>. For that reason this repository
  does **not** commit raw price data; it is downloaded locally into `data/`.

### Technology attention: Wikimedia Pageviews API
- <https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews>
- Wikimedia Foundation; pageview data is released into the public domain (CC0).
  <https://wikitech.wikimedia.org/wiki/Analytics/Data_Lake/Traffic/Pageviews>

### Technology adoption: Our World in Data
- <https://ourworldindata.org/> charts used: `share-electricity-solar`, `share-electricity-wind`,
  `share-of-individuals-using-the-internet`.
- Licence: CC BY 4.0. Underlying sources (Ember, Energy Institute Statistical Review of World
  Energy, International Telecommunication Union, World Bank) are credited on each OWID chart page.

## Software

- NumPy (BSD-3-Clause) <https://numpy.org/>
- pandas (BSD-3-Clause) <https://pandas.pydata.org/>
- Matplotlib (Matplotlib licence, BSD-compatible) <https://matplotlib.org/>
- Requests (Apache 2.0) <https://requests.readthedocs.io/>
- Plotly for Python (MIT), used only for the offline `results/dashboard.html` <https://github.com/plotly/plotly.py>.
  The web app in `site/` uses no chart library: its charts are hand-written SVG.
- statsforecast by Nixtla (Apache 2.0), optional, used for the AutoETS / AutoARIMA baselines
  <https://github.com/Nixtla/statsforecast>
- tabulate (MIT) <https://github.com/astanin/python-tabulate>
- PyTorch (BSD-3-Clause), installed with TimesFM <https://pytorch.org/>
- Hugging Face Hub client (Apache 2.0) <https://github.com/huggingface/huggingface_hub>

## Further references

Twenty open-source repositories and the modelling theories this project draws on are listed in
[REFERENCES.md](REFERENCES.md).

## Inspiration

- **Design.** The look and motion were inspired by, and contain no code from: Apple's product pages
  (exploded-view scrolling), Bartosz Ciechanowski's explorable explanations, Teenage Engineering,
  Nothing, Framework, Stripe, Linear, Vercel, The Pudding, Reuters Graphics, Our World in Data,
  Distill, Observable Plot, Metaculus, Polymarket, earth.nullschool.net, Windy, Codrops, Bramus Van
  Damme's scroll-driven animation demos, Josh W. Comeau, MDN, GSAP ScrollTrigger and Scrollama
  (patterns only), and the READMEs of Supabase, Excalidraw, tldraw, uv, Rich and VHS via
  awesome-readme. All fifty are listed with links in [docs/DESIGN.md](docs/DESIGN.md).
- **Design.** The "Sealed Ledger" terminal redesign (October 2026) used three design-engineering guides
  as checklists, with no code taken from them: [Impeccable](https://github.com/pbakaus/impeccable) by
  Paul Bakaus (Apache-2.0), [taste-skill](https://github.com/Leonxlnx/taste-skill) (MIT) and
  [Emil Kowalski's skills](https://github.com/emilkowalski/skills) (MIT). The concept, colours, type and
  how it was audited are in [docs/DESIGN.md](docs/DESIGN.md).
- **Fonts.** Newsreader, IBM Plex Sans and IBM Plex Mono, all under the SIL Open Font Licence, served by Google Fonts.

- **World Monitor** by koala73 (AGPL-3.0) <https://github.com/koala73/worldmonitor>, and Alek's fork
  **Terra Atlas** <https://github.com/Normansrule/worldmonitor>. World Predictor borrows their product
  idea: a GitHub Pages web app plus a full downloadable version, built from the same static site and
  released from tags. No code was copied, so World Monitor's AGPL licence does not apply here.

- Isaac Asimov, *Foundation* (1951) and the Foundation series, which introduced Hari Seldon and
  psychohistory. Only the idea is referenced; no text from the books is reproduced. The challenger
  model, Seldon, is named after him.

## Methods

Cited in APA style (7th edition); the full bibliography is in [REFERENCES.md](REFERENCES.md#bibliography-apa-7th-edition).

- Mean absolute scaled error (MASE): Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting, 22*(4), 679–688. https://doi.org/10.1016/j.ijforecast.2006.03.001
- Pinball (quantile) loss: Koenker, R., & Bassett, G., Jr. (1978). Regression quantiles. *Econometrica, 46*(1), 33–50. https://doi.org/10.2307/1913643
- Proper scoring and interval coverage: Gneiting, T., & Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *Journal of the American Statistical Association, 102*(477), 359–378. https://doi.org/10.1198/016214506000001437
- Brier score for the odds: Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review, 78*(1), 1–3. https://doi.org/10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2
- Rolling-origin backtests: Tashman, L. J. (2000). Out-of-sample tests of forecasting accuracy: An analysis and review. *International Journal of Forecasting, 16*(4), 437–450. https://doi.org/10.1016/S0169-2070(00)00065-0
