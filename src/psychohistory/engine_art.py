"""Artwork for "How a forecast is built": one forecast card taken apart into six layers.

The same six layers are drawn twice from this file, so the two never drift apart:

* ``site_layers_html`` writes inline SVG for the landing page, where scrolling pulls the layers
  apart and puts them back together (see ``site/assets/site.css``);
* ``readme_svg`` writes a static exploded diagram for the README, in light and dark versions.

Each layer is a flat plate in the same 480 x 280 frame. Stacked, they read as one finished card:
the history line, cut into TimesFM's input patches, with the forecast fan and what really happened.
"""

from __future__ import annotations

import math
from html import escape
from pathlib import Path

W, H = 480, 280
NOW = 40  # index of "now" in the 64-point example series
N = 64

LAYERS = [
    ("Sources", "GDELT news attention, Yahoo Finance prices, Wikipedia pageviews and Our World in Data."),
    ("History", "Years of daily or weekly values for one series: the past the model is allowed to see."),
    ("Context window", "TimesFM reads the history in patches of 32 steps, like words in a sentence."),
    ("TimesFM 2.5", "Google Research's open forecasting model. Nothing is trained on our data."),
    ("Forecast", "A range for every step ahead: the middle guess and an 80% band, sealed with a date."),
    ("Score", "When the future arrives, reality is drawn over the fan and the forecast is scored."),
]

# CSS custom properties for the site; concrete colours for the README.
SITE = {"ink": "var(--text)", "muted": "var(--muted)", "line": "var(--line)", "plate": "var(--surface)",
        "forecast": "var(--orange)", "real": "var(--blue)", "good": "var(--green)", "band": "var(--band)"}
THEMES = {
    "light": {"ink": "#12141b", "muted": "#555a66", "line": "#ddd6c8", "plate": "#fffdf8", "bg": "#f5f2ea",
              "forecast": "#c06a12", "real": "#1d6f8f", "good": "#1f8a63", "band": "rgba(192,106,18,.18)"},
    "dark": {"ink": "#edf1f7", "muted": "#9aa9bf", "line": "#22314b", "plate": "#0e1524", "bg": "#070b14",
             "forecast": "#f2b54a", "real": "#6fd3e6", "good": "#5fd3a0", "band": "rgba(242,181,74,.2)"},
}
# CSS rotateX(55deg) rotateZ(-35deg) applied to a flat plate is this 2D affine map.
_C, _S, _K = math.cos(math.radians(35)), math.sin(math.radians(35)), math.cos(math.radians(55))
ISO = (_C, -_S * _K, _S, _C * _K)


def _series() -> list[float]:
    """A calm, rising example line: deterministic so the artwork never changes between builds."""
    return [0.35 + 0.006 * i + 0.05 * math.sin(i / 3.1) + 0.025 * math.sin(i / 1.3) for i in range(N)]


def _xy(i: int, v: float) -> tuple[float, float]:
    return 40 + i * (W - 80) / (N - 1), H - 50 - v * (H - 100)


def _path(points) -> str:
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _fan(c: dict) -> str:
    v = _series()
    upper, lower, mid = [], [], []
    for i in range(NOW, N):
        spread = 0.012 + 0.0075 * (i - NOW)
        centre = v[NOW] + 0.006 * (i - NOW)
        upper.append(_xy(i, centre + spread)); lower.append(_xy(i, centre - spread)); mid.append(_xy(i, centre))
    band = _path(upper + lower[::-1]) + "Z"
    return (f'<path d="{band}" fill="{c["band"]}"/>'
            f'<path d="{_path(mid)}" fill="none" stroke="{c["forecast"]}" stroke-width="2.5" stroke-dasharray="6 5"/>')


def layer_bodies(c: dict) -> list[str]:
    """SVG for each plate's content (no plate outline), in the shared 480 x 280 frame."""
    v = _series()
    history = _path([_xy(i, v[i]) for i in range(NOW + 1)])
    nx, _ = _xy(NOW, 0)
    sources = "".join(
        f'<g transform="translate({60 + 95 * k} 120)"><rect width="84" height="40" rx="10" fill="none" stroke="{c["muted"]}"/>'
        f'<text x="42" y="25" text-anchor="middle" font-size="13" fill="{c["ink"]}">{name}</text></g>'
        for k, name in enumerate(("GDELT", "Yahoo", "Wikipedia", "OWID")))
    patch_w = (nx - 40) / 3
    patches = "".join(
        f'<rect x="{40 + k * patch_w:.1f}" y="40" width="{patch_w - 4:.1f}" height="{H - 80}" rx="6" '
        f'fill="{c["real"]}" opacity="{0.10 if k % 2 else 0.18}"/>' for k in range(3))
    cells = "".join(
        f'<rect x="{170 + 22 * (k % 7)}" y="{90 + 22 * (k // 7)}" width="16" height="16" rx="3" fill="{c["forecast"]}" '
        f'opacity="{0.25 + 0.6 * ((k * 37) % 10) / 10:.2f}"/>' for k in range(28))
    actual = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{c["real"]}"/>'
        for x, y in (_xy(i, v[i] + 0.004 * ((i * 7) % 5 - 2)) for i in range(NOW + 1, N, 2)))
    return [
        sources,
        f'<path d="{history}" fill="none" stroke="{c["ink"]}" stroke-width="2.5" stroke-linejoin="round"/>',
        patches + f'<text x="44" y="32" font-size="12" fill="{c["muted"]}">patch 1 · patch 2 · patch 3</text>',
        cells + f'<text x="240" y="228" text-anchor="middle" font-size="14" font-weight="600" fill="{c["ink"]}">TimesFM 2.5</text>',
        f'<line x1="{nx:.1f}" y1="30" x2="{nx:.1f}" y2="{H - 30}" stroke="{c["muted"]}" stroke-dasharray="3 4"/>'
        f'<text x="{nx + 6:.1f}" y="42" font-size="12" fill="{c["muted"]}">now</text>' + _fan(c),
        actual + f'<g transform="translate({W - 128} 26)"><rect width="100" height="30" rx="15" fill="{c["good"]}" opacity=".16"/>'
        f'<text x="50" y="20" text-anchor="middle" font-size="13" font-weight="600" fill="{c["good"]}">inside 80%</text></g>',
    ]


def site_layers_html() -> str:
    """Six stacked inline SVG plates for the landing page's sticky stage."""
    out = []
    for i, ((name, _), body) in enumerate(zip(LAYERS, layer_bodies(SITE))):
        plate = f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" class="plate{" base" if i == len(LAYERS) - 1 else ""}"/>'
        # Sources and the model are scaffolding: they only show once the card is pulled apart.
        inner = " inner" if name in ("Sources", "TimesFM 2.5") else ""
        out.append(f'<svg class="explode__layer{inner}" style="--i:{i}" viewBox="0 0 {W} {H}" aria-hidden="true">{plate}<g class="body">{body}</g></svg>')
    return "\n          ".join(out)


def site_labels_html() -> str:
    return "\n          ".join(
        f'<li style="--i:{i}"><b>{escape(name)}</b><span>{escape(text)}</span></li>' for i, (name, text) in enumerate(LAYERS))


def readme_svg(theme: str) -> str:
    """The exploded engine as one static picture, with a numbered callout for each layer."""
    c = THEMES[theme]
    a, b, cc, d = ISO
    # Where the plate's corners land after the tilt: x from 0 to a*W + cc*H, y from b*W to d*H.
    rise, drop, reach = -b * W, d * H, a * W + cc * H
    left, top, gap = 36, 24 + rise, 112
    width = int(left + reach + 420)
    height = int(top + gap * (len(LAYERS) - 1) + drop + 28)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">',
             f'<rect width="{width}" height="{height}" rx="20" fill="{c["bg"]}"/>']
    bodies = layer_bodies(c)
    # Draw the bottom plate first so upper plates sit on top of it.
    for i in reversed(range(len(LAYERS))):
        last = i == len(LAYERS) - 1
        parts.append(f'<g transform="matrix({a:.4f} {b:.4f} {cc:.4f} {d:.4f} {left} {top + gap * i:.1f})">'
                     f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="{c["plate"]}" fill-opacity="{1 if last else .6}" '
                     f'stroke="{c["line"]}" stroke-width="1.5"/>{bodies[i]}</g>')
    label_x = left + reach + 70
    for i, (name, text) in enumerate(LAYERS):
        # Callout from the plate's right-hand corner (W, H after the tilt) to its label.
        cx, cy = left + reach, top + gap * i + b * W + d * H
        lines = _wrap(text, 46)
        parts.append(f'<line x1="{cx + 6:.0f}" y1="{cy:.0f}" x2="{label_x - 18}" y2="{cy:.0f}" stroke="{c["muted"]}" stroke-width="1" stroke-dasharray="2 4"/>'
                     f'<circle cx="{label_x - 4}" cy="{cy:.0f}" r="13" fill="{c["bg"]}" stroke="{c["forecast"]}" stroke-width="1.5"/>'
                     f'<text x="{label_x - 4}" y="{cy + 5:.0f}" text-anchor="middle" font-size="13" font-weight="700" fill="{c["forecast"]}">{i + 1}</text>'
                     f'<text x="{label_x + 20}" y="{cy - 4:.0f}" font-size="18" font-weight="700" fill="{c["ink"]}" font-family="Fraunces, Georgia, serif">{escape(name)}</text>'
                     + "".join(f'<text x="{label_x + 20}" y="{cy + 16 + 16 * k:.0f}" font-size="12.5" fill="{c["muted"]}">{escape(line)}</text>'
                               for k, line in enumerate(lines)))
    parts.append("</svg>")
    return "".join(parts)


def _wrap(text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width and line:
            lines.append(line); line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line]


def write_readme_art(assets: Path) -> list[Path]:
    paths = []
    for theme in THEMES:
        path = assets / f"engine-{theme}.svg"
        path.write_text(readme_svg(theme))
        paths.append(path)
    return paths


START, END = "<!-- engine:start -->", "<!-- engine:end -->"


def update_site(index: Path) -> bool:
    """Write the layers and labels between the engine markers in site/index.html."""
    text = index.read_text()
    if START not in text or END not in text:
        return False
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    block = (f'{START}\n        <div class="explode__scene">\n          {site_layers_html()}\n'
             f'          <p class="explode__caption"><span class="assembled">One finished forecast. Keep scrolling.</span></p>\n        </div>\n'
             f'        <ol class="explode__labels">\n          {site_labels_html()}\n        </ol>\n        {END}')
    index.write_text(before + block + after)
    return True
