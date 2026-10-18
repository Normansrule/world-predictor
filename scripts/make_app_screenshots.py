"""Screenshots of the web app for the README (docs/assets/app-*.png and app-replay.gif).

    pip install playwright && playwright install chromium
    python scripts/make_app_screenshots.py            # uses site/app/data/data.js

Pass --chromium /path/to/chrome to use an existing browser instead of Playwright's download.
"""

from __future__ import annotations

import argparse
import asyncio
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
VIEWS = {"overview": 1500, "outlook": 1500, "replay": 1000, "crowd": 1000, "vault": 900}


async def shoot(chromium: str | None, site: Path) -> None:
    from playwright.async_api import async_playwright

    app = (site / "app" / "index.html").resolve().as_uri()
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chromium) if chromium else await p.chromium.launch()
        for scheme in ("light", "dark"):
            page = await browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme=scheme, device_scale_factor=1)
            for view, height in VIEWS.items():
                if scheme == "dark" and view != "overview":
                    continue
                await page.goto(f"{app}#{view}")
                await page.wait_for_timeout(2400)  # let the charts finish drawing in
                png = await page.screenshot(clip={"x": 0, "y": 0, "width": 1280, "height": height}, full_page=True)
                suffix = "" if scheme == "light" else "-dark"
                Image.open(io.BytesIO(png)).convert("RGB").save(ASSETS / f"app-{view}{suffix}.png", optimize=True)
                if scheme == "dark" and view == "overview":  # the landing page's tilt-in preview
                    shot = Image.open(io.BytesIO(png)).convert("RGB").crop((0, 0, 1280, 800))
                    shot.save(ROOT / "site" / "assets" / "app-preview.png", optimize=True)
            await page.close()
        # Animated replay: step the slider through every past forecast.
        page = await browser.new_page(viewport={"width": 1100, "height": 900})
        await page.goto(f"{app}#replay")
        await page.wait_for_timeout(800)
        steps = int(await page.eval_on_selector("#replay-slider", "e => +e.max"))
        frames = []
        for i in range(steps + 1):
            await page.eval_on_selector("#replay-slider", f"e => {{ e.value = {i}; e.dispatchEvent(new Event('input')); }}")
            await page.wait_for_timeout(150)
            png = await page.locator("#view-replay .card").screenshot()
            frames.append(Image.open(io.BytesIO(png)).convert("RGB"))
        palette = frames[-1].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
        frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
        frames += [frames[-1]] * 2
        frames[0].save(ASSETS / "app-replay.gif", save_all=True, append_images=frames[1:], duration=900, loop=0, optimize=True)
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chromium", help="path to a Chromium/Chrome executable")
    parser.add_argument("--site", type=Path, default=ROOT / "site",
                        help="built site to photograph, e.g. build/site after `psychohistory site` (default: site/, demo data)")
    args = parser.parse_args()
    asyncio.run(shoot(args.chromium, args.site))
    print(f"Wrote app screenshots to {ASSETS}")


if __name__ == "__main__":
    main()
