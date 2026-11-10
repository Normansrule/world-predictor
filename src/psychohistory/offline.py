"""The offline copy: the whole app, with its data, in one HTML file.

Open it by double-clicking: no server, no internet, nothing to install. Every view works from the
forecasts it was built with (the date is shown in the app); only live headlines in the World terminal
need a connection. Your watchlist, your sealed calls and the theme are kept by the browser as usual.

GitHub Pages serves a fresh copy at ``world-predictor-offline.html`` after every forecast run, the app's
? sheet has a button to save it, and ``psychohistory offline`` (or ``psychohistory app``) makes one from
your own results.

This module uses only the standard library, so the Pages workflow can run it as a plain script:
``python3 src/psychohistory/offline.py <site folder> [<out file>]``.
"""

from __future__ import annotations

import base64
import datetime as _dt
import re
import sys
from pathlib import Path

PAGES_URL = "https://normansrule.github.io/world-predictor/"
FILE_NAME = "world-predictor-offline.html"


def _safe(code: str, tag: str) -> str:
    """Nothing inside an inlined block may close it early (a headline could contain "</script")."""
    return re.sub(rf"</{tag}", rf"<\\/{tag}", code, flags=re.IGNORECASE)


def bundle(site: Path, out: Path | None = None, built: str | None = None) -> Path:
    """Inline the app's stylesheet, scripts, data and icon into one file next to ``site``'s landing page."""
    app = Path(site) / "app"
    html = (app / "index.html").read_text(encoding="utf-8")
    out = Path(out) if out else Path(site) / FILE_NAME
    built = built or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def script(m: re.Match) -> str:
        src = m.group(1)
        if re.match(r"^(https?:)?//", src):
            return ""  # nothing from the network in the offline copy
        return "<script>" + _safe((app / src).read_text(encoding="utf-8"), "script") + "</script>"

    html = re.sub(r'<script src="([^"]+)"></script>', script, html)
    css = (app / "css" / "app.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="css/app.css">', "<style>" + _safe(css, "style") + "</style>")
    # Web fonts and the install manifest need the network; the app's font stacks fall back to system fonts.
    html = re.sub(r'\s*<link rel="(preconnect|manifest)"[^>]*>', "", html)
    html = re.sub(r'\s*<link rel="stylesheet" href="https://[^"]*">', "", html)
    icon = Path(site) / "assets" / "icon.svg"
    if icon.exists():
        uri = "data:image/svg+xml;base64," + base64.b64encode(icon.read_bytes()).decode()
        html = html.replace('href="../assets/icon.svg"', f'href="{uri}"')
    html = re.sub(r'(href|src)="\.\./([^"]*)"', lambda m: f'{m.group(1)}="{PAGES_URL}{m.group(2)}"', html)
    flag = f'<script>window.WP_OFFLINE = {{ built: "{built}", web: "{PAGES_URL}app/" }};</script>'
    html = html.replace("<head>", "<head>\n  " + flag, 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":  # used by the Pages workflow, which does not install the package
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: offline.py <site folder> [<out file>]")
    print(f"Offline copy written to {bundle(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else None)}")
