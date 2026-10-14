# Credits and attribution

World Predictions is a thin experimental layer on top of other people's open work. Everything it
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
- Plotly for Python (MIT), used for `results/dashboard.html` <https://github.com/plotly/plotly.py>
- statsforecast by Nixtla (Apache 2.0), optional, used for the AutoETS / AutoARIMA baselines
  <https://github.com/Nixtla/statsforecast>
- tabulate (MIT) <https://github.com/astanin/python-tabulate>
- PyTorch (BSD-3-Clause), installed with TimesFM <https://pytorch.org/>
- Hugging Face Hub client (Apache 2.0) <https://github.com/huggingface/huggingface_hub>

## Further references

Twenty open-source repositories and the modelling theories this project draws on are listed in
[REFERENCES.md](REFERENCES.md).

## Inspiration

- Isaac Asimov, *Foundation* (1951) and the Foundation series, which introduced Hari Seldon and
  psychohistory. Only the idea is referenced; no text from the books is reproduced.

## Methods

- MASE: Rob J. Hyndman and Anne B. Koehler, "Another look at measures of forecast accuracy",
  *International Journal of Forecasting* 22(4), 2006.
- Pinball (quantile) loss and interval coverage follow standard probabilistic forecasting practice,
  as in Gneiting and Raftery, "Strictly proper scoring rules, prediction, and estimation", *JASA* 2007.
