# BUILD SPEC — Stage 6B: marine instrument header (three-pill dual wind row + `?` explainer)

Repo: `/home/reid/projects/big-pond-chop`, branch `stage6` (6A landed at `a829ee0`; rollback tag `pre-stage6`).
Stage 6 sign-off decisions D1–D14 are LOCKED. **This leaf is the header chrome + wiring.** No wave-math,
no tables, no QA tools (6C owns those).

## Contract from 6A (shipped, verified)

- `wind.ingest()` now returns `{ day, shoreDay, … }`: **`day` = mid-lake (physics input, unchanged)**,
  **`shoreDay` = shore (new, same shape/length, `null` when the payload is malformed)**.
  `SHORE_POINT`, `buildDualUrl(lakePoint, shorePoint, horizon)`, `parseTwoLocations(json)` are exported.
  Verify by reading `src/wind.js` — do not re-derive, do not change it.

## The row (measured, pinned — this is the approved layout after the 360 px fit fix)

```html
<div id="three">                       <!-- replaces #wind-info inside #secondary -->
  <span id="pill-shore" class="pill"><span id="shore">8</span><span id="shore-u">Shore</span></span>
  <span id="arrow" aria-hidden="true"><svg viewBox="0 0 16 12" width="16" height="12">…</svg></span>
  <span id="pill-lake" class="pill"><span id="lake">17</span><span id="lake-u">Lake</span></span>
  <span id="dot" aria-hidden="true">·</span>
  <span id="pill-gust" class="pill"><span id="gust">24</span><span id="gust-u">Gust</span></span>
  <span id="mph">mph</span>
</div>
```

- **There is NO `Wind:` prefix.** Measured: the row's natural ink is 251.36 px (normal) / **258.59 px (wide
  12/27/38)** against **232.00 px available at 360×800** — it overflows, hard-clips, and crushes `#mph` to
  0 px. Dropping the prefix saves exactly **29.56 px**; trimming the pill's horizontal padding from 9 px to
  **6 px** per side saves a further 18 px → ~211 px in the widest state, ≈21 px of slack. The three pill
  labels carry the meaning; the prefix was redundant.
- `#arrow` is an **inline SVG** (16×12), never a `➔`/`➜`/`→` font glyph. `#dot` is the shipped `·` separator.
- **`#help`**: `<button id="help" type="button" aria-expanded="false" aria-controls="help-pop"
  aria-label="What do Shore, Lake and Gust mean?">?</button>` — a **44×44 CSS px hit box** (glyph ~16 px
  inside), sitting **≥8 px from `#refresh`**, last element of the row group. Measured in the mock: 44.00×44.00,
  exactly 8.00 px gap, header still exactly 72.00 px tall.
- **`#help-pop` is a SIBLING of `<header>`** (append it to `<body>`, anchored below the band). As a child of
  `overflow:hidden` it is sliced at 72 px — that was measured in round 1. Copy (exact):
  `• Shore: Inland forecast accounting for terrain friction (matches phone apps).`
  `• Lake: 10m open-water wind driving wave growth (typically 20–60% higher; median +33% in our data).`
  `• Gust: Peak 3-5s open-water bursts indicating squall risk.`
- **Delete (named)**: `#wind-info`, `#frame-info`, and any now-unused `.sep` in `#secondary`;
  `ui.windLine` (replaced by the new model helper). H/L stays available in the tap card (`data-field="hl"`).
- **Keep unchanged**: `#verdict-range` (15 px / ≤400 px: 14 px), `#comfort-chip` + `.tier-*`, `#verdict-peak`,
  `#subrow`, `#secondary`, `h1`, `#refresh` (48×48, aria-label), every `body` `data-*` key, and every
  deck/tape/map id the harness drives.

## Tokens (locked; the ink rule was CORRECTED by measurement)

| element | spec |
| --- | --- |
| numerals (`#shore`, `#lake`, `#gust`) | **13 px / 700 / `#f8fafc`**, `font-variant-numeric: tabular-nums` |
| pill labels (`#shore-u`, `#lake-u`, `#gust-u`) | **10 px / 500 / `#cbd5e1`** (no opacity — an 0.82 opacity measured 4.06:1, FAIL) |
| row label / muted text (`#mph`) | 10 px / `#cbd5e1`; any remaining muted label `#94a3b8` |
| header container | `background: rgba(15,23,42,.85)`; `backdrop-filter: blur(8px)`; `border-bottom: 1px solid rgba(255,255,255,.1)`; `height/min-height/max-height: 72px`; `overflow: hidden` **only on the header, never on the popover** |
| font stack | `-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif` (no webfont) |
| shore + gust pill fill | `rgba(148,163,184,.18)` → composites `#273144`; white ink = 12.47:1 |
| lake pill fill | the tape's **`WIND_HEAT` tier colour of the displayed lake speed** at **`.55` alpha** over the glass |
| **pill ink** | **white `#f8fafc` on EVERY tier.** Measured: at `.55` alpha even the amber tier composites **dark**
  (`#8d6219`) → white = **5.15:1**, whereas the "dark ink on light tints" rule measured **3.31:1 (FAIL)**
  (crimson: white 7.88:1 vs dark 2.18:1). Do **not** implement per-tier dark ink. |
| pills | `border-radius` as the mock, `padding: 2px 6px`, `display:inline-flex; gap:3px; align-items:baseline` |

`@supports not (backdrop-filter: blur(1px))` → solid `#0f172a`.

## Overlay (D8, approved)

- Header **floats over the map**: `position: absolute/fixed` at the top, `z-index ≥ 1001` (Leaflet's
  controls are 1000, `#horizon` 1000, `#wind-badge` 500). `#map` must extend under it.
- `fitLake()` (`src/render.js:571-574`) → `paddingTopLeft: [12, 84]` so the whole lake stays visible.
- `#horizon` / `#wind-badge` must keep their current 12 px clearance below the band (verified no collision).
- `#boot` (inset:0) may slide under the header — its bar must stay centred in the VISIBLE map area.
- Deck background (D9) → the same slate `#0f172a` so the chrome reads as one family (one declaration).

## Wiring (`src/render.js`, readout region ~985-1035)

- Per frame (`showFrame`): `#lake` = `day[idx].speedMph`, `#shore` = `shoreDay[idx].speedMph`,
  `#gust` = **`day[idx].gustMph`** (the lake gust — the tooltip calls it open-water), all rounded to integers
  as today. `#pill-lake`'s tier class/colour follows the lake speed via the existing `WIND_HEAT` helper.
- Shore unavailable (`shoreDay === null`, or `shoreDay[idx]` missing): `#shore` renders `—`, everything else
  renders normally, header stays exactly 72 px, no console error.
- Values update per frame exactly like today (the tape/scrub path is untouched).

## Files allowed to touch

`index.html`, `src/ui.js`, `src/render.js`, `tests/ui.test.js`, `tests/render.test.js`.
**Nothing else.** Do NOT edit `src/wind.js`, `tools/qa/**`, or the design docs.

## Done-when (print every line)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js`
   → all exit 0 (print the tails).
2. `git diff --stat main -- src/wave-math.js src/tables.js public/` → **0 lines**.
3. Geometry, measured in headless Chromium at **360×800 and 390×844** (use
   `/home/reid/.hermes/hermes-agent/venv/bin/python`, Playwright is installed there; write your measuring
   script under `tmp/`): header `getBoundingClientRect().height === 72.00`; `#three`'s
   `scrollWidth ≤ clientWidth`; **`#mph`'s width ≥ 19 px (not crushed)**; the row's ink ≤ its available width
   in the states normal (8/17/24), **wide (12/27/38)**, calm (3/4/6); every pill fully inside the header box;
   `#help` rect ≥44×44 and ≥8 px from `#refresh`; quote all numbers.
4. Contrast, computed from rendered colours: numerals vs their own pill fill, labels/units vs the header
   composite → every pair **≥4.5:1**; quote the minimum.
5. `#help-pop`: opens on tap, is a sibling of `<header>`, is not sliced by the header clip, Escape closes it,
   a tap outside closes it, focus returns to `#help`, `aria-expanded` flips; and a tap on `#help` or inside
   `#help-pop` **creates no map pin and dismisses no card** (Leaflet-bubbling guard — drive real clicks).
6. `getComputedStyle(header).backdropFilter === 'blur(8px)'`, `zIndex ≥ 1001`, and the header overlaps `#map`
   (print both rects).
7. Identity: the rendered `#lake` equals `day[idx].speedMph` and `#shore` equals `shoreDay[idx].speedMph`
   for the current frame (print both pairs from the page + from `wind.ingest`, they must match).
8. Shore-missing path: force `shoreDay = null` (a `?` test hook or a stubbed response) → `#shore` shows `—`,
   header still 72.00 px, no console error.
9. `grep -n "wind-info\|frame-info\|windLine" tools/qa/*.py tools/qa/*.js tests/*.js src/*.js index.html` →
   print every hit (report only: **do not edit QA tools**, 6C fixes them).
10. `git status --porcelain` → clean; `git log --oneline -3`; commit as
    `stage6b: three-pill marine header row + \`?\` explainer, floating frosted glass`.

## Procedure

- **You MUST edit the files.** A run that only reads and exits is a failure — the orchestrator checks diffs.
- **Do not read files outside this repository** (`~/.gstack/`, `~/.hermes/`, `/tmp/` are auto-rejected).
  Reference material that matters is copied into this spec.
- Ponytail ruleset: laziest correct implementation; no config, no options, no abstractions.
- Reference artifact (read-only, outside the repo paths above, so copy what you need): the approved mockup
  lives at `docs/mockups/stage6-header/mock.html` in THIS repo, and its measured receipt at
  `/tmp/l3b-receipt.json` — do not depend on the latter, but the mock is the visual reference.
- **Do NOT merge, tag or push.** If a spec number conflicts with observed reality, trust reality and report it.
