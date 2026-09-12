# big-pond-chop — BUILD SPEC (stage 4C: final QA + receipts — **no src edits**)

Status: **APPROVED by Reid 2026-09-11.** Runs after 4B.1. Build **ONE commit**.

This stage is **QA only**. You may not modify `src/`, `index.html`, `public/`, or any test file. Your
job is to *prove* the Stage-4 contract from the outside and leave a repo-committed, re-runnable
receipt for it.

## Files allowed to touch

- `tools/qa/stage4_check.py` (new — the committed, re-runnable QA script)
- `docs/STAGE-4-RECEIPTS.md` (new — the printed receipt, pasted from a real run)
- `docs/BUILD-SPEC-STAGE4C.md` (this file — you may append a `## Notes` section)

**Frozen — do not edit:** everything else, especially `src/*.js`, `index.html`, `public/*`,
`tests/*.js`, `tools/bench_frames.js`, `tools/export_*.py`.

## Harness

`python3 -m http.server <port>` from the repo root + `/home/reid/.hermes/hermes-agent/venv/bin/python`
with playwright (chromium is preinstalled in `~/.cache/ms-playwright`). Viewport 390x844 (DPR 2) and
360x800 for the narrow pass. Prefer `http://127.0.0.1:<port>`; pick a free port.

## Required checks (all of them; each prints `ok`/`FAIL` and the number it saw)

1. **Boot:** `#boot` visible before the first frame and hidden after (first painted frame), overlay
   `img.src` starts with `blob:`, overlay `naturalWidth > 0`.
2. **Frame base:** `#scrub.max === '95'`, `data-step-min === '15'`, and during a play sample of >= 10
   ticks every sampled `data-hour` is distinct and every minute value is a multiple of 15 (report the
   series).
3. **Header layout:** `header.clientHeight === 72` **and** `header.scrollHeight <= 72`, at both 390
   and 360. Then the **no-truncation sweep**: for EVERY name in `public/spots.v1.json`
   (`features[].name`) plus the sector fallbacks `N Basin` and `SW Shore`, set
   `#verdict-peak.textContent = 'Peak: 3.9 ft · <name>'` and assert
   `scrollWidth <= clientWidth + 1`. Report the worst label and the widest natural width.
4. **Tier chip:** `#comfort-chip.className` must equal an independent re-derivation from the frame's
   own numbers (`data-hsFt`, `data-hmaxFt`, H/L scraped from `#frame-info`) using the LOCKED table
   (RED: max>=5.0 OR roller>=4.0 OR H/L>=0.055; AMBER: max>=3.5 OR roller>=2.5; YELLOW: max>=2.0 OR
   roller>=1.5; else GREEN — first match wins). The chip must always carry a text label.
5. **Clock:** `#hour-label` matches `^\d{1,2}:\d{2} (AM|PM) C[DS]T$` **and** equals a Python
   `zoneinfo('America/Chicago')` re-derivation of `data-hour` (12-hour, no leading zero).
6. **Compass badge:** text matches `^[NSEW]{1,2} \d{1,3}°$`; the arrow's computed `matrix(...)`
   rotation equals the bearing (mod 360, ±1.5°) — the locked convention is **INTO the wind**; the
   badge rect lies in the map's top-right quadrant and does not intersect
   `.leaflet-control-zoom`; aria-label present.
7. **Touch ergonomics:** `#refresh`, `#play`, `#card-close` (with the card open) >= 48x48; `#scrub`
   height >= 48; computed `touch-action` on `#controls` is `none`.
8. **Tap card:** a real mouse click mid-lake opens the card with all six fields
   (Spot/Coords/Depth/Hs/Hmax/H/L); the ✕ dismisses AND stays dismissed (pin element count returns to
   0); a land/nodata click dismisses and flashes `land — no wave data here`, reverting to the default
   hint after ~2 s.
9. **Playback performance:** zoom to ~13 first, then play: canvas width <= 780 px during play,
   main-thread `data-frameMs` **avg and max <= 60 ms** over >= 10 ticks, `data-encodeMs` reported;
   pause (+900 ms) restores canvas width > 1000 px. Instrument `URL.createObjectURL` /
   `revokeObjectURL` with `add_init_script` (a *script body*, not a function expression) and assert
   `created > 0`, `0 < revoked <= created`.
10. **Radar smoothing (the two display bugs):** at fit and at zoom 13 and 14, record the overlay
    `img` upscale factor (`getBoundingClientRect().width / naturalWidth`) — must be **<= 1.15** at
    every level. Then the **land-bleed check**: draw the overlay blob into an offscreen canvas and
    sample alpha at 4-6 pixel positions computed from KNOWN-LAND lat/lng corners of
    `public/meta.v1.json` → `wgs84_corners` (mapped through the bbox as equirectangular px =
    `(lon-west)/(east-west)*W`, `py = (north-lat)/(north-south)*H`) — every land sample must be
    **alpha 0**; also sample 2 known mid-lake points and require `alpha > 0` (proof the raster is
    actually painted there).
11. **Before/after receipt:** create a read-only worktree of tag `pre-stage4`
    (`git worktree add /tmp/bpc-pre4 pre-stage4`), serve it on a second port, and record the SAME
    upscale factors at fit/13/14 — then print a before/after table (stages 1-3 vs now) and remove the
    worktree afterwards.
12. **Suites:** run `node tests/parity.test.js`, `wind`, `render`, `ui` and print each tail line.

## Done when

1. `tools/qa/stage4_check.py` runs green end-to-end on the current HEAD and is **re-runnable**
   (no hard-coded one-off values that only work once).
2. `docs/STAGE-4-RECEIPTS.md` contains the REAL printed output of that run (every check with its
   measured number, the play series, the before/after upscale table, the land-bleed results, the
   suite tails) — no invented numbers.
3. Screenshots saved to `/tmp/bpc-s4-*.png` (fit, zoomed at 13/14, mid-play, tap card, 360 px pass).
4. `git diff --stat` for your commit touches ONLY the three allowed files — **not a single byte of
   `src/`, `index.html`, `public/`, or `tests/`**.
5. **ONE git commit**: `Stage 4C: re-runnable QA harness + Stage-4 receipts`
   — with a body summarizing any check that FAILED (a failing check is a finding, not a blocker to
   commit; report it plainly rather than tuning the check until it passes).

## Receipts to include in your final message

(a) the pass/fail line for every check group with its numbers; (b) the before/after upscale table;
(c) the land-bleed sample results; (d) the suite tails; (e) `git show --stat`; (f) anything that
failed or could not be measured, stated plainly.

## Notes (2026-09-12)

Shipped `tools/qa/stage4_check.py` (re-runnable, no one-off values) and
`docs/STAGE-4-RECEIPTS.md` (verbatim stdout of the run). **15 ok, 1 FAIL.**
The only failing check is **10 — radar overlay upscale**: 1.408 at zoom 13 and
2.817 at zoom 14 against the `<= 1.15` gate (fit is 0.456). This is a real
display measurement, not a harness artifact — the raster is clamped to 1536 px
while the zoom-13/14 bbox projects to ~2163/~4327 CSS px. It is a large
improvement over stages 1-3 (5.633 -> 1.408 and 11.268 -> 2.817) but the 4C
gate is not met at high zoom. Land-bleed passes at all four `wgs84_corners`
(alpha 0) with both mid-lake samples painted (alpha 255).

Harness notes: it exits 0 after running every check so failures are findings,
not aborts; checks 2/9 sample ticks only after the play-width regather settles;
check 3 measures intrinsic label width with a DOM `Range`; check 6 derives the
expected arrow angle from `data-bearing-grid + gamma`. The before/after worktree
is created and removed inside the run.
