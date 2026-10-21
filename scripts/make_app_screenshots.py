"""Screenshots of the landing page and web app for the README (docs/assets/landing*.png, app-*.png including app-studio*.png, app-lab.gif, app-replay.gif and app-trace.gif).

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
VIEWS = {"desk": 1340, "outlook": 1000, "replay": 860, "crowd": 860, "vault": 720}


async def theme(page, scheme: str) -> None:
    """The app follows its own theme switch (light unless chosen otherwise), so set it before loading."""
    await page.add_init_script(f"try {{ localStorage.setItem('wp-theme', '{scheme}') }} catch (e) {{}}")


async def shoot(chromium: str | None, site: Path) -> None:
    from playwright.async_api import async_playwright

    app = (site / "app" / "index.html").resolve().as_uri()
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chromium) if chromium else await p.chromium.launch()
        for scheme in ("light", "dark"):
            page = await browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme=scheme, device_scale_factor=1)
            await theme(page, scheme)
            for view, height in VIEWS.items():
                if scheme == "dark" and view != "desk":
                    continue
                await page.goto(f"{app}#{view}")
                await page.wait_for_timeout(2400)  # let the charts finish drawing in
                png = await page.screenshot(clip={"x": 0, "y": 0, "width": 1280, "height": height}, full_page=True)
                suffix = "" if scheme == "light" else "-dark"
                Image.open(io.BytesIO(png)).convert("RGB").save(ASSETS / f"app-{view}{suffix}.png", optimize=True)
                if scheme == "dark" and view == "desk":  # the landing page's tilt-in preview
                    shot = Image.open(io.BytesIO(png)).convert("RGB").crop((0, 0, 1280, 800))
                    shot.save(ROOT / "site" / "assets" / "app-preview.png", optimize=True)
            await page.close()
        # "Follow one result": one still per theme at the sealed forecast, and the walkthrough as a GIF.
        for scheme in ("light", "dark"):
            page = await browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme=scheme, device_scale_factor=1)
            await theme(page, scheme)
            await page.goto(f"{app}#trace/sp500")
            await page.wait_for_timeout(800)
            frames = []
            for step in range(8):
                await page.wait_for_timeout(1700 if step == 4 else 500)
                top = await page.locator("#view-trace .trace-bar").bounding_box()
                grid = await page.locator("#view-trace .trace-grid").bounding_box()
                clip = {"x": 0, "y": top["y"] - 16, "width": 1280, "height": grid["y"] + grid["height"] - top["y"] + 32}
                shot = Image.open(io.BytesIO(await page.screenshot(clip=clip, full_page=True))).convert("RGB")
                if step == 4:
                    shot.save(ASSETS / f"app-trace{'' if scheme == 'light' else '-dark'}.png", optimize=True)
                frames.append(shot.resize((shot.width * 3 // 4, shot.height * 3 // 4), Image.LANCZOS))
                await page.keyboard.press("ArrowRight")
            if scheme == "dark":
                palette = frames[4].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
                frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
                frames[0].save(ASSETS / "app-trace.gif", save_all=True, append_images=frames[1:], duration=1600, loop=0, optimize=True)
            await page.close()
        # The Lab: one round played through, as stills per theme and a GIF of the whole round.
        for scheme in ("light", "dark"):
            page = await browser.new_page(viewport={"width": 1280, "height": 1500}, color_scheme=scheme, device_scale_factor=1)
            await theme(page, scheme)
            await page.goto(f"{app}#lab/sp500")
            await page.add_style_tag(content=".status, .cmd { position: static !important; }")  # keep the bars off the card
            await page.wait_for_timeout(900)
            card = page.locator("#view-lab .lab-card")
            frames = []

            async def grab(hold=1):
                shot = Image.open(io.BytesIO(await card.screenshot())).convert("RGB")
                frames.extend([shot.resize((shot.width * 3 // 4, shot.height * 3 // 4), Image.LANCZOS)] * hold)
                return shot

            async def drag(selector, dy):
                box = await page.locator(selector).bounding_box()
                x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                await page.mouse.move(x, y); await page.mouse.down()
                for k in range(1, 5):
                    await page.mouse.move(x, y + dy * k / 4); await page.wait_for_timeout(60)
                    await grab()
                await page.mouse.up()

            async def hold():
                button = page.locator(".seal-btn"); await button.scroll_into_view_if_needed()
                box = await button.bounding_box()
                await page.mouse.move(box["x"] + 24, box["y"] + box["height"] / 2); await page.mouse.down()
                await page.wait_for_timeout(260); await grab(); await page.wait_for_timeout(300); await page.mouse.up()

            await page.evaluate("scrollTo(0, 0)")
            await grab(2)
            await drag(".lab-stage .handle.end .dot", -60)
            await drag(".lab-stage .handle.range .dot", 24)
            await hold(); await page.wait_for_timeout(450); await grab(3)
            await hold()
            for _ in range(5):
                await page.wait_for_timeout(330); await grab()
            await page.wait_for_timeout(900)
            final = await grab(6)
            final.save(ASSETS / f"app-lab{'' if scheme == 'light' else '-dark'}.png", optimize=True)
            if scheme == "dark":
                palette = final.resize((final.width * 3 // 4, final.height * 3 // 4)).quantize(colors=255, method=Image.Quantize.MEDIANCUT)
                frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
                frames[0].save(ASSETS / "app-lab.gif", save_all=True, append_images=frames[1:], duration=220, loop=0, optimize=True)
            await page.close()
        # Forecast Studio: a question about gold and a call sealed beside the models', per theme.
        for scheme in ("light", "dark"):
            page = await browser.new_page(viewport={"width": 1280, "height": 1300}, color_scheme=scheme, device_scale_factor=1)
            await theme(page, scheme)
            await page.goto(f"{app}#studio/gold")
            await page.add_style_tag(content=".status, .cmd { position: static !important; }")
            await page.wait_for_timeout(900)
            await page.click("#st-presets button[data-k='0.05']")
            await page.fill("#st-you", "4300")
            button = page.locator("#st-seal"); await button.scroll_into_view_if_needed()
            box = await button.bounding_box()
            await page.mouse.move(box["x"] + 24, box["y"] + box["height"] / 2); await page.mouse.down()
            await page.wait_for_timeout(700); await page.mouse.up(); await page.wait_for_timeout(1700)
            png = await page.locator("#view-studio").screenshot()
            Image.open(io.BytesIO(png)).convert("RGB").save(ASSETS / f"app-studio{'' if scheme == 'light' else '-dark'}.png", optimize=True)
            await page.close()
        # The landing page's first screen, once per theme, after the headline has settled.
        for scheme in ("light", "dark"):
            page = await browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme=scheme, device_scale_factor=1)
            await theme(page, scheme)
            await page.goto((site / "index.html").resolve().as_uri())
            await page.wait_for_timeout(2400)
            png = await page.screenshot()
            Image.open(io.BytesIO(png)).convert("RGB").save(ASSETS / f"landing{'' if scheme == 'light' else '-dark'}.png", optimize=True)
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
