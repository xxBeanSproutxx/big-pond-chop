# BUILD SPEC — Stage 6C: verification + receipts (QA stage, src-free)

Repo: `/home/reid/projects/big-pond-chop`, branch `stage6` (HEAD `cbeba15`; 6A `a829ee0`, 6B `10327b2`).
**This stage must not edit the code it proves.** `src/**`, `index.html` and `tests/**` are OUT OF SCOPE —
if you find a defect there, STOP and report it; it becomes its own lettered stage.

## Files allowed to touch

`tools/qa/stage5_check.py`, `tools/qa/live_smoke.py`, `docs/STAGE-6-RECEIPTS.md`, and new scratch files
under `tmp/` (screenshots included). Nothing else. Do NOT edit the mockups under `docs/mockups/`.

## What shipped in 6A/6B (verified by the orchestrator; do not re-derive)

- `src/wind.js`: ONE batched GET for lake + shore (`buildDualUrl`, `parseTwoLocations`, `SHORE_POINT`),
  `ingest()` → `{ day (lake, unchanged), shoreDay (nullable) }`. Physics untouched; `day` byte-identical to
  the pre-stage code (verified by running both trees against the same API).
- `index.html` + `src/ui.js` + `src/render.js`: floating 72 px frosted header (`position: fixed`,
  `z-index: 1001`, `backdrop-filter: blur(8px)`, `rgba(15,23,42,.85)`), three-pill row
  `#three > #pill-shore(#shore,#shore-u) · #arrow(SVG) · #pill-lake(#lake,#lake-u) · #dot · #pill-gust(#gust,#gust-u) · #mph`,
  `#help` (44×44) + sibling `#help-pop` explainer, `#wind-info`/`#frame-info`/`.sep`/`ui.windLine` deleted,
  lake pill tinted from `WIND_HEAT`, all pill ink white, `fitLake` padding `paddingTopLeft: [12, 84]`.
  `ui.windPills(lakeMph, shoreMph, gustMph)` → `{lake, shore, gust, lakeTint, lakeBorder}`.

## Task 1 — repair the stale probe

`tools/qa/stage5_check.py:324` still reads `document.getElementById('frame-info').textContent` (that id is
deleted → would throw). Re-point it at the shipped row (`#three` text) and make it null-safe. Report the
before/after lines.

## Task 2 — new harness group `[19] 6 marine header`

Add it after `[18]`, registered in the same table as the other groups. Drive deterministic value states by
**route-intercepting `api.open-meteo.com`** and returning a crafted **array of 2 location objects** (a
single-object response silently yields `shoreDay = null` — that trap cost the last leaf time). Assert and
PRINT, at **360×800 and 390×844**:

1. header rect height **exactly 72.00**; `scrollHeight == clientHeight`.
2. `#three` `scrollWidth <= clientWidth`; **`#mph` width ≥ 19 px** (the crush detector).
3. row ink ≤ available width in states normal (8/17/24), **wide (12/27/38)**, calm (3/4/6) — quote ink,
   available, slack for each.
4. pills fully inside the header box; `#help` ≥ 44×44 and exactly ≥8 px from `#refresh`.
5. computed typography: numerals `13px/700/tabular-nums`, labels `10px`, avionics font stack.
6. **contrast** (computed from rendered colours, both viewports): numerals vs their own pill fill;
   **`#lake-u` and the other labels vs their own backgrounds — every pair ≥ 4.5:1**; quote the minimum.
   (The lake label was moved to `#f8fafc` in 6B.1 because `#cbd5e1` measured 3.58:1 on the amber tier.)
7. **jitter**: scrub 24 frames; the lake pill's width delta ≤ 0.5 px for equal digit counts, and the row's
   right edge never crosses `#refresh`'s left edge.
8. **network**: exactly ONE request to `api.open-meteo.com` during boot, its URL containing BOTH latitudes;
   no new host contacted.
9. **identity**: rendered `#lake` == `day[idx].speedMph` and `#shore` == `shoreDay[idx].speedMph`
   (read the app's own frame data; both pairs must match).
10. **popover**: tap opens (sibling of `<header>`, not sliced by the header clip, `bottom > 72`), Escape
    closes, outside tap closes, focus returns to `#help`, `aria-expanded` flips — driven with REAL clicks —
    and **no map pin is created and no card dismissed** by taps on `#help` or inside `#help-pop`.
11. **shore-missing**: with the route stub returning a single location, `#shore` renders `—`, `#lake` is
    normal, height still 72.00, zero console errors.
12. **overlay/blur**: `backdropFilter == 'blur(8px)'`, `zIndex >= 1001`, the header rect overlaps `#map`;
    `src/render.js` contains `paddingTopLeft: [12, 84]`; `#horizon`/`#wind-badge` keep ≥12 px clearance.

## Task 3 — live smoke additions

Extend `tools/qa/live_smoke.py` with assertions that the DEPLOYED bytes carry: the avionics font stack,
`rgba(15, 23, 42, 0.85)`, and the shipped row ids (`three`, `pill-shore`, `pill-lake`, `pill-gust`,
`help-pop`). Keep the existing 10 assertions working. Print `SUMMARY: N ok, M FAIL`.

## Task 4 — perf + receipts

- Run `tools/qa/scrub_bench.py` on the local server: quote the three medians and the long-task maxima
  against the 5P baseline **16.72 / 16.71 / 18.01 ms, 0 long tasks**. The overlay + blur is the risk being
  priced here; if a median regresses by >15 % or any long task appears, report it verbatim as a finding
  (do NOT fix it in this stage).
- Run the four node suites and quote each tail.
- Screenshots into `tmp/s6-shots/`: header at 360 and 390, the row in the wide state at 360, and the
  popover open at 360.
- Write `docs/STAGE-6-RECEIPTS.md`: what shipped (ids + behaviours), every gate with its raw numbers,
  the deliberate gate deltas (the `[3]` extension, the new `[19]`, the live-smoke additions, the retired
  `windLine` test), the 6B.1 fix with its numbers, and any open item you could not close.

## Done-when (print verbatim)

1. `node tests/{parity,wind,render,ui}.test.js` → four exit 0 + tails.
2. `tools/qa/stage5_check.py` → final `SUMMARY: N ok, M FAIL` — **no FAIL** except a pre-existing,
   data-dependent `[14] live seam` (quote it if it appears, say so if it passed).
3. `tools/qa/live_smoke.py --url http://127.0.0.1:<port>/index.html` → `SUMMARY: N ok, 0 FAIL`.
4. `tools/qa/scrub_bench.py` → the three medians + long-task maxima, side by side with the 5P baseline.
5. The `[19] …` lines verbatim, including ink/slack per state, the minimum contrast, the network count,
   the identity pairs, and the popover results.
6. `git status --porcelain` → clean; `git log --oneline -3`; commit `stage6c: verify the marine header —
   harness group [19], live-smoke assertions, receipts`. **No merge, no tag, no push.**

## Procedure

- **You MUST edit the listed files** — a run that only reads and exits is a failure (this happened once in
  this repo; the orchestrator checks for diffs).
- **Do not read or write outside this repository** (`~/.gstack/`, `~/.hermes/` are auto-rejected).
- Playwright + Chromium are available via `/home/reid/.hermes/hermes-agent/venv/bin/python` (system python3
  has none).
- **Never weaken a gate to make it pass.** A legitimate failure is reported, not relaxed; if you must adjust
  a pre-existing assertion, it goes in the receipts as a numbered, justified delta.
