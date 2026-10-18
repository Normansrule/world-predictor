"""The README progress tracker, drawn from docs/progress.json (the single source of truth).

``render_markdown`` writes the checklist between the ``<!-- progress:start -->`` and
``<!-- progress:end -->`` markers in README.md, and ``render_svg`` draws one progress bar per
area. Tests check that every item marked done names a file that exists, so the tracker cannot
claim work the repository does not contain.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "progress.json"
START, END = "<!-- progress:start -->", "<!-- progress:end -->"


def load(path: Path = SOURCE) -> list[dict]:
    return json.loads(path.read_text())["areas"]


def counts(area: dict) -> tuple[int, int]:
    return sum(1 for i in area["items"] if i["done"]), len(area["items"])


def render_markdown(areas: list[dict]) -> str:
    done = sum(counts(a)[0] for a in areas)
    total = sum(counts(a)[1] for a in areas)
    lines = [START, "", f"**{done} of {total} milestones done ({done / total:.0%}).** Drawn from "
             "[`docs/progress.json`](docs/progress.json); tests check every ticked item against the repository.", ""]
    for area in areas:
        d, n = counts(area)
        lines += [f"<details{' open' if d < n else ''}><summary><b>{area['icon']} {area['name']}</b> · {d}/{n}</summary>", ""]
        for item in area["items"]:
            lines.append(f"- [{'x' if item['done'] else ' '}] {item['title']}")
        lines += ["", "</details>", ""]
    lines.append(END)
    return "\n".join(lines)


def update_readme(readme: Path, areas: list[dict]) -> bool:
    text = readme.read_text()
    if START not in text or END not in text:
        return False
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    readme.write_text(before + render_markdown(areas) + after)
    return True


THEMES = {
    "light": {"bg": "#fcfcfb", "text": "#0b0b0b", "muted": "#52514e", "track": "#e4e3df", "bar": "#2a78d6", "full": "#1baf7a"},
    "dark": {"bg": "#1a1a19", "text": "#f0efec", "muted": "#c3c2b7", "track": "#383835", "bar": "#3987e5", "full": "#2cc28c"},
}


def render_svg(areas: list[dict], theme: str = "light") -> str:
    c = THEMES[theme]
    row, top = 46, 64
    height = top + row * len(areas) + 20
    rows = []
    for i, area in enumerate(areas):
        d, n = counts(area)
        y = top + i * row
        width = 520 * d / n
        colour = c["full"] if d == n else c["bar"]
        rows.append(
            f'<text x="32" y="{y + 15}" class="name">{area["icon"]}  {escape(area["name"])}</text>'
            f'<rect x="340" y="{y + 2}" width="520" height="16" rx="8" fill="{c["track"]}"/>'
            f'<rect class="bar" style="animation-delay:{0.15 * i:.2f}s" x="340" y="{y + 2}" width="{width:.1f}" height="16" rx="8" fill="{colour}"/>'
            f'<text x="880" y="{y + 15}" class="num">{d}/{n}  ·  {d / n:.0%}</text>'
        )
    done = sum(counts(a)[0] for a in areas)
    total = sum(counts(a)[1] for a in areas)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {height}" role="img" aria-label="Progress: {done} of {total} milestones done">
<style>
  .name {{ font: 600 15px Inter, system-ui, sans-serif; fill: {c['text']}; }}
  .num {{ font: 500 14px Inter, system-ui, sans-serif; fill: {c['muted']}; }}
  .title {{ font: 600 13px Inter, system-ui, sans-serif; fill: {c['muted']}; letter-spacing: .08em; }}
  .bar {{ transform-origin: 340px 0; transform: scaleX(0); animation: grow 1.1s cubic-bezier(.2,.7,.2,1) forwards; }}
  @keyframes grow {{ to {{ transform: scaleX(1); }} }}
  @media (prefers-reduced-motion: reduce) {{ .bar {{ animation: none; transform: none; }} }}
</style>
<rect width="1000" height="{height}" rx="14" fill="{c['bg']}"/>
<text x="32" y="38" class="title">PROGRESS  ·  {done} OF {total} MILESTONES DONE</text>
{''.join(rows)}
</svg>
"""


def write_all(readme: Path = ROOT / "README.md", assets: Path = ROOT / "docs" / "assets") -> None:
    areas = load()
    for theme in THEMES:
        (assets / f"progress-{theme}.svg").write_text(render_svg(areas, theme))
    update_readme(readme, areas)
