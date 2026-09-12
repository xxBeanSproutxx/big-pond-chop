# big-pond-chop — BUILD SPEC (stage 4B.1: compass relocation + header row 2 breathing room)

Status: **APPROVED by Reid 2026-09-11** (runs after 4A.2, before 4C). Build **ONE commit**.
Follow the **ponytail ruleset (laziest correct implementation)**. Report the ACTUAL shipped values back.

## Goal

Two quick UI adjustments on the 4B chrome: move the compass badge to the map's top-right, and stop the
peak/location line from truncating on a 390 px (or 360 px) phone.

## Files allowed to touch

- `index.html`
- `src/ui.js` (formatting helpers only — `windLine`, `formatHeadline` output strings)
- `tests/ui.test.js` — add/update ONLY the assertions for the strings you change; do not delete tests
- `docs/BUILD-SPEC-STAGE4B1.md` (this file — you may append a `## Notes / shipped API` section)

**FROZEN:** `src/render.js` (stage 4A.2 owns it), `src/wave-math.js`, `src/tables.js`, `public/*`,
`tests/parity.test.js`, `tests/render.test.js`, `tests/wind.test.js`, `tools/*`, every element id, the
tier table, the clock format, the arrow convention (into the wind), the 72 px header height, and all
`data-*` semantics.

## 1. Compass badge → map top-right (Reid's decision)

`#wind-badge` moves from `left:10px; top:74px` to **`top:12px; right:12px`** (keep the pill: 32 px
arrow disc + text, `z-index:500`, `.85` background, tabular numerals). It must not overlap the
Leaflet zoom control (top-left) or the attribution strip (bottom-right), and it must stay inside
`#map` at 360 px width. The element keeps its id, its aria-label pattern, and the arrow rotation rule
(rotation == bearing, INTO the wind).

## 2. Row 2 must never truncate the location — measured budget

Measured today at 390 px (subrow 370 px): `#secondary` takes **204 px**, leaving the peak line **158 px**;
`Peak: 3.9 ft · Upper and Lower Twin Island` needs **251 px** → clipped. At 360 px it is worse
(128 px available). Required: **the full location label always renders, for every name in
`public/spots.v1.json` (longest: `Upper and Lower Twin Island` = 251 px), at both 360 and 390 px.**

**Approach (do this):** stop making the peak line share its row with the two-line secondary column.
Keep the header at exactly 72 px with three stacked rows:

- row 1: `#verdict-range` + `#comfort-chip` + `#refresh` (unchanged)
- row 2: `#verdict-peak` — **full width**, `white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  min-width:0` (ellipsis stays as the last-resort fallback, but it must never trigger for the 21 names)
- row 3: `#wind-info` + `#frame-info` on one full-width line (`Wind: … · Gusts … · H/L …`)

Mild text tightening is allowed and expected (Reid's note): the gust unit may drop (`Gusts 27`), the
`Wind:`/`H/L` prefixes stay. **Do not abbreviate location names, ever.** If a name still clips at
360 px, shorten labels before touching the location: ranked fallbacks — (1) drop the second `mph`,
(2) `H/L 0.043` → `H/L .043`, (3) `Peak:` → `Pk:`, (4) chip font 11 → 10 px. Report which, if any,
you needed.

Hard requirements: `header.clientHeight === 72` **and** `header.scrollHeight <= 72` at 360 and 390 px
(no clipping, no growth), all existing element ids present, and the tier chip / clock / wind-line /
badge behaviour unchanged otherwise. `formatHeadline`'s outputs stay a range + a peak line with the
location; only whitespace/prefix tweaks are in scope.

## Done when

1. Four suites green; `tests/parity.test.js`, `tests/wind.test.js`, `tests/render.test.js` outputs
   byte-identical to before this stage; `tests/ui.test.js` updated only for strings you changed.
2. **Browser check** (same recipe: `python3 -m http.server` from the repo root +
   `/home/reid/.hermes/hermes-agent/venv/bin/python` + playwright, chromium in `~/.cache/ms-playwright`):
   for **every** feature name in `public/spots.v1.json` (and the sector fallbacks `N Basin` / `SW Shore`),
   set the peak line and assert `#verdict-peak.scrollWidth <= clientWidth + 1` at **both 360 and 390 px**;
   assert the badge's bounding rect is within the top-right quadrant of `#map` and does not intersect the
   zoom control rect; assert header 72 px + `scrollHeight <= 72` at both widths; zero console/page errors;
   screenshots to `/tmp/bpc-4b1-390.png` and `/tmp/bpc-4b1-360.png`.
3. **ONE git commit**: `Stage 4B.1: compass badge top-right + row-2 no-truncate header layout`
   — diff limited to the allowed files.

## Out of scope

`src/render.js` (4A.2), the encode path, the tier thresholds, the clock, the tap card, the legend,
deployment, the QA script (4C is strictly QA + receipts).

## Receipts to include in your final message

(a) four suite tails; (b) the per-name truncation table at 360/390 (max scrollWidth vs clientWidth);
(c) the badge rect + zoom-control rect; (d) `git show --stat`; (e) which fallback shortenings you used,
if any; (f) anything you could not do.

## Notes / shipped API (2026-09-12)

Shipped values:

- Badge: `#wind-badge` now `top:12px; right:12px` (was `left:10px; top:74px`). Rect 86x32 at
  x=262..348 / x=292..378 on 360/390 px; inside `#map` top-right quadrant, clear of the top-left
  zoom control and the bottom-right attribution. id / aria-label pattern / arrow rotation untouched.
- Header: 72 px, three stacked text rows in a `.head-text` column beside the 48 px `#refresh`:
  row 1 `#verdict-range` + `#comfort-chip`, row 2 `#verdict-peak` (own full-column row,
  `min-width:0` + ellipsis fallback), row 3 `#wind-info` + `#frame-info`. `#subrow` wraps;
  `#secondary` is left-aligned full-column. All ids preserved.
- No label shortenings needed: no fallback from the ranked list was used. `windLine` and
  `formatHeadline` are unchanged, so `src/ui.js` and `tests/ui.test.js` are byte-identical.
- Longest peak line `Peak: 3.9 ft · Upper and Lower Twin Island` = 251 px intrinsic at the 12 px
  mobile font vs 284 px available at 360 px (33 px headroom); all 21 feature names + 16 sector
  labels fit with 0 px overflow. Typical row 3 (`Wind: 29 mph · Gusts 47 mph` + `H/L 0.043`) =
  205 px vs 284 px.
- `header.clientHeight === header.scrollHeight === 72` at both 360 and 390 px; zero console/page
  errors. Screenshots `/tmp/bpc-4b1-390.png`, `/tmp/bpc-4b1-360.png`.
- `tests/parity.test.js` / `tests/wind.test.js` are unchanged except their non-deterministic
  ms-benchmark lines (1.187 -> 1.204 ms/hour; 1.688 -> 1.712 ms/frame); all assertions pass.
  `tests/render.test.js` output is byte-identical.
