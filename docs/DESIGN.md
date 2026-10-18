# Design

World Predictor's look and motion were shaped by fifty sites, repositories and write-ups, listed below
with the one idea taken from each. **No code was copied from any of them**: every effect is written
from scratch in plain HTML, CSS and JavaScript, with no chart or animation library. The design basis
for the product itself (one static site served by GitHub Pages and shipped as a download) is
[World Monitor](https://github.com/koala73/worldmonitor) by Elie Habib and its fork
[Terra Atlas](https://github.com/Normansrule/worldmonitor), whose level of polish this aims to match.
They are AGPL-3.0; only ideas were borrowed.

## The look: "the vault"

The palette is the night archive of the Foundation's Encyclopedia: deep ink (`#070b14`), brass gold
for forecasts (`#f2b54a`), cool cyan for what really happened (`#6fd3e6`), and green for a hit. Light
mode is the printed page (`#f5f2ea`). Headings are set in [Fraunces](https://fonts.google.com/specimen/Fraunces),
a literary serif in the spirit of Stripe Press; text in [Inter](https://rsms.me/inter/); dates and
numbers in [JetBrains Mono](https://www.jetbrains.com/lp/mono/). All three are SIL Open Font Licence
fonts, and every page falls back to system fonts offline.

## What was built from these references

| Effect | Where | Inspired by |
|---|---|---|
| Six-layer exploded forecast engine that comes apart and reassembles as you scroll | Landing page (`#engine`), README | Apple product pages, IYO, Ciechanowski, Teenage Engineering (1–10) |
| Scroll-driven animation in CSS alone (`animation-timeline: view()`), with a 20-line fallback | `site/assets/site.css`, `site.js` | Bramus, Josh W. Comeau, MDN, GSAP ScrollTrigger, Scrollama (33–39) |
| Headline words rise in turn; slow drifting glow behind the hero | Landing hero | Stripe, Lusion, Codrops (11, 17, 22) |
| Primary button with a light travelling round its edge | Landing hero | Linear, Vercel (13, 14) |
| The live forecast in the hero draws itself, the future is hatched | Landing hero, every app chart | Reuters Graphics, Windy (24, 32) |
| Number strip that counts up as it enters view | Landing page | Vercel, Motion (14, 40) |
| Scoreboard bars that grow from zero | Landing `#results`, app overview | uv's single benchmark chart (46) |
| App screenshot that tilts flat as you scroll to it | Landing `#app` | Linear (13) |
| Card light that follows the pointer | Landing and app | Linear, Vercel (13, 14) |
| Morphing between app views | App tabs | MDN View Transition API (36) |
| Prediction cards with big odds and a sparkline | App outlook | Polymarket, Metaculus (29, 30) |
| Light and dark images, Mermaid, folded tables | README | tldraw, Supabase, GitHub Docs (43, 45, 50) |

Everything stops under `prefers-reduced-motion`, only `transform` and `opacity` are animated, and the
exploded engine becomes a static diagram (the same artwork as the README's) for readers who prefer less motion.

## The fifty references

## A. Exploded-view and scroll-assembled product pages (the effect Alek asked for)

| # | Reference | What it does well | What to take |
|---|---|---|---|
| 1 | [Apple AirPods Pro](https://www.apple.com/airpods-pro/) | The product sits still, then splits into its internal parts as you scroll, with a caption for each part. Scroll position, not time, drives every frame. | The core pattern: a pinned "stage" and scroll progress mapped to each part's offset. |
| 2 | [Awwwards: AirPods Pro scroll-triggered animation](https://www.awwwards.com/inspiration/product-scroll-triggered-animation-apple-airpods-pro) | Breakdown of Apple's frame-sequence approach. | Proof the effect reads well at small sizes; we use vector layers instead of image frames, which is far lighter. |
| 3 | [Apple MacBook Pro](https://www.apple.com/macbook-pro/) | Chip and chassis "lift off" in layers; big type and numbers fade in beside each layer. | Pair each separated layer with one large stat (e.g. "1,000 weekly forecasts sealed"). |
| 4 | [Apple Vision Pro](https://www.apple.com/apple-vision-pro/) | Very slow, deliberate pacing; one idea per screen height. | Give each exploded layer roughly one viewport of scroll. |
| 5 | [Awwwards: Interactive WebGL exploded view (IYO)](https://www.awwwards.com/inspiration/interactive-webgl-exploded-view-iyo) | A device bursts into dozens of parts along their real axes, then reassembles. | Explode along one axis (vertical) with a slight isometric tilt so layers stay legible. |
| 6 | [Awwwards: Farm Minerals product scroll](https://www.awwwards.com/inspiration/interactive-product-scroll-animation-for-agricultural-website-farm-minerals) | Exploded view applied to something that is not a gadget. | Shows the effect works for an abstract "engine", which is what our pipeline is. |
| 7 | [Bartosz Ciechanowski: Mechanical Watch](https://ciechanow.ski/mechanical-watch/) | The best explorable explainer on the web: a watch is taken apart piece by piece, each part with its own small live diagram. | Explain TimesFM the same way: patches, context window, quantile heads, one small live SVG each. |
| 8 | [Framework Laptop](https://frame.work/) | The product's modularity is the story; parts are shown separated and labelled. | Our "modules" are the three areas (news, markets, technology) slotting into one engine. |
| 9 | [Nothing](https://nothing.tech/) | Transparent hardware and dot-matrix type; a strong, cheap-to-reproduce visual identity. | A dot-matrix accent for big numbers (hit rate, days ahead) is distinctive and pure CSS. |
| 10 | [Teenage Engineering](https://teenage.engineering/) | Product drawings as clean technical line art, grid layouts, tiny monospace labels. | Draw the exploded layers as thin-stroke technical illustrations with callout lines. |

## B. Award-winning motion and polish

| # | Reference | What it does well | What to take |
|---|---|---|---|
| 11 | [Stripe](https://stripe.com/) | Animated mesh gradient behind crisp type; diagonal section cuts. | A slow, low-contrast gradient behind the hero fan chart (CSS only, paused for reduced motion). |
| 12 | [Stripe Press](https://press.stripe.com/) | Bookish, literary feel with tactile 3D objects. | Fits the *Foundation* theme: serif display type for the Seldon quotes. |
| 13 | [Linear](https://linear.app/) | Dark UI, glow borders, product screenshots that tilt in on scroll. | The app preview should tilt from perspective to flat as it enters the viewport. |
| 14 | [Vercel](https://vercel.com/) | Grid backgrounds, precise hairlines, numbers that count up. | Hairline grid behind the scoreboard; count-up on hit rates. |
| 15 | [GitHub: How we built the GitHub globe](https://github.blog/engineering/user-experience/how-we-built-the-github-globe/) | Engineering write-up of a performant hero globe showing live activity arcs. | A world view of where tracked news events come from, with performance lessons (pause off-screen, cap pixel ratio). |
| 16 | [Raycast](https://www.raycast.com/) | Keyboard-first product shown through crisp, looping UI animations. | Short looping SVG of the app's "seal a prediction" flow. |
| 17 | [Lusion](https://lusion.co/) | Studio site with physics-based 3D and buttery transitions. | Benchmark for easing quality; use custom cubic-beziers, never linear. |
| 18 | [Igloo Inc](https://www.igloo.inc/) | Awwwards Site of the Year 2024; one continuous scroll journey through 3D scenes. | The whole landing page as one story: past data, sealing, waiting, scoring. |
| 19 | [Bruno Simon](https://bruno-simon.com/) | A portfolio you drive through; playful and memorable. | One playful moment (e.g. drag the "now" line to see what the model knew then). |
| 20 | [Rive](https://rive.app/) | State-machine animations that react to input. | Animate states of a prediction card (sealed, waiting, hit, miss) with CSS transitions. |
| 21 | [Spline](https://spline.design/) | Approachable 3D in the browser. | Only as an idea source; we stay in SVG for weight. |
| 22 | [Codrops](https://tympanus.net/codrops/) | Years of open demos of scroll and hover effects with source. | Reference recipes for staggered reveals and text splits. |

## C. Data visualization and scrollytelling (closest to what we are)

| # | Reference | What it does well | What to take |
|---|---|---|---|
| 23 | [The Pudding](https://pudding.cool/) | Visual essays where the chart changes as the text scrolls past. | A "how good is the oracle?" scrollytelling section on the landing page. |
| 24 | [Reuters Graphics](https://www.reuters.com/graphics/) | Restrained colour, annotated charts, clear sourcing under every graphic. | Annotate charts directly ("model missed this shock") and put a source line under each. |
| 25 | [Our World in Data](https://ourworldindata.org/) | Charts that explain themselves; a consistent chart frame with tabs (chart, table, sources). | Give every app chart the same frame with Chart / Data / Source tabs. |
| 26 | [OWID Grapher (repo)](https://github.com/owid/owid-grapher) | Open-source chart engine behind OWID. | Study how they handle time sliders and responsive SVG. |
| 27 | [Distill](https://distill.pub/) | Interactive ML explanations with beautiful margin notes. | Margin notes and hover footnotes in the methods page. |
| 28 | [Observable Plot](https://observablehq.github.io/plot/) | Concise, honest chart defaults. | Copy its defaults in our own SVG: no chartjunk, direct labels, light gridlines. |
| 29 | [Metaculus](https://www.metaculus.com/) | Forecasts with track records, calibration plots, community vs. resolved outcomes. | A calibration chart ("when we said 80%, it happened 74% of the time"). |
| 30 | [Polymarket](https://polymarket.com/) | Probability shown as big numbers and live sparklines on cards. | Card layout for each sealed prediction: big probability, sparkline, countdown. |
| 31 | [earth.nullschool.net](https://earth.nullschool.net/) | Animated flow on a globe; gorgeous with almost no UI. | Minimal chrome over a full-bleed visual for the hero. |
| 32 | [Windy](https://www.windy.com/) | Forecast timelines you scrub; the future is visibly "forecast" styled. | Scrubbable timeline where the forecast region is hatched or tinted differently from the past. |

## D. Animation techniques and tools (lightweight, no-build friendly)

| # | Reference | What it does well | What to take |
|---|---|---|---|
| 33 | [Scroll-driven Animations demos (Bramus)](https://scroll-driven-animations.style/) | Dozens of CSS-only scroll effects, including reveal-on-enter and progress bars. | The exploded view can run with zero JS in Chromium via `animation-timeline`. |
| 34 | [Josh W. Comeau: Scroll-Driven Animations](https://joshwcomeau.com/animation/scroll-driven-animations) | Clear explanation of `scroll()` vs `view()` timelines and ranges. | Use `view()` with `animation-range: contain` for the pinned stage. |
| 35 | [MDN: `view()` timeline](https://developer.mozilla.org/en-US/docs/Web/CSS/animation-timeline/view) | Spec reference and browser support. | Feature-detect with `@supports (animation-timeline: view())`. |
| 36 | [MDN: View Transition API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API) | Native morphing between page states. | Smooth switching between the three areas in the app with one `startViewTransition` call. |
| 37 | [GSAP ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/) | The industry-standard pin-and-scrub model. | Borrow its mental model (pin, scrub, start/end markers) in our tiny vanilla fallback, without adding the library. |
| 38 | [Lenis (repo)](https://github.com/darkroomengineering/lenis) | Smooth scrolling used by many award sites. | Skip it: native scroll is lighter and accessible. Listed so the choice is deliberate. |
| 39 | [Scrollama (repo)](https://github.com/russellsamora/scrollama) | Tiny IntersectionObserver-based scrollytelling helper. | Its step-trigger pattern, rewritten in ~20 lines, powers the JS fallback. |
| 40 | [Motion](https://motion.dev/) | Spring physics and scroll timelines on top of Web Animations. | Use the Web Animations API directly for count-ups and springs. |
| 41 | [COBE (repo)](https://github.com/shuding/cobe) | A 5 kB WebGL globe with markers. | If a globe is ever wanted, this is the only one light enough; optional, not default. |

## E. Standout GitHub READMEs and README tooling

| # | Reference | What it does well | What to take |
|---|---|---|---|
| 42 | [awesome-readme](https://github.com/matiassingers/awesome-readme) | Curated list of excellent READMEs. | Source for further inspiration; credit it. |
| 43 | [Supabase](https://github.com/supabase/supabase) | Centered logo, one-line pitch, product screenshots, architecture diagram. | Our README already follows this; add an architecture diagram. |
| 44 | [Excalidraw](https://github.com/excalidraw/excalidraw) | Hand-drawn hero image that instantly shows the product. | A hero image that is the app itself, not a logo. |
| 45 | [tldraw](https://github.com/tldraw/tldraw) | Light and dark hero images via `<picture>`. | Keep the existing dark/light banner pair and extend it to every README image. |
| 46 | [uv (Astral)](https://github.com/astral-sh/uv) | One benchmark bar chart above the fold that sells the project. | Put the scoreboard (TimesFM vs. naive baseline) as one bold chart near the top. |
| 47 | [Rich (Textualize)](https://github.com/Textualize/rich) | Screenshots and GIFs of every feature inline. | One short GIF per area (news, markets, technology). |
| 48 | [VHS (Charm)](https://github.com/charmbracelet/vhs) | Scripted, reproducible terminal GIFs. | Record the CLI quick start with a `.tape` file so the GIF never goes stale. |
| 49 | [capsule-render](https://github.com/kyechan99/capsule-render) and [readme-typing-svg](https://github.com/DenverCoder1/readme-typing-svg) | Animated SVG headers and typing text that render in GitHub. | Animated SVG works in READMEs; we self-host ours (SMIL/CSS in an SVG file) instead of calling these services. |
| 50 | [GitHub Docs: theme-aware images and formatting](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax) , [light and dark images in Markdown](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/) and [Mermaid diagrams in Markdown](https://github.blog/developer-skills/github/include-diagrams-markdown-files-mermaid/) | Official support for `<picture>` light/dark images, collapsible sections and Mermaid. | Mermaid for the pipeline diagram; `<details>` to fold long tables. |

Also worth a look (not counted): [Shields.io](https://shields.io/) for badges (already used), [Platane/snk](https://github.com/Platane/snk) and [lowlighter/metrics](https://github.com/lowlighter/metrics) for Action-generated README art, which is exactly how our progress SVGs are made.

Also worth a look: [Shields.io](https://shields.io/) for badges, and [Platane/snk](https://github.com/Platane/snk)
and [lowlighter/metrics](https://github.com/lowlighter/metrics) for README art drawn by GitHub Actions,
which is how the progress bars here are made.

Links were checked on 18 October 2026. Reuters Graphics could not be loaded from the checking
environment and is listed as its long-standing address.
