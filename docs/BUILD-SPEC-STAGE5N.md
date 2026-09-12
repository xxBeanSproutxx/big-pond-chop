# BUILD SPEC — Stage 5N: wider 7-day tape (330 px/day) + cyan calm floor

Repo: /home/reid/projects/big-pond-chop (branch `stage5n`, off `stage5m` @ 672a233)

Reid's brief (2026-09-12), after reviewing the 5M screenshots:

> 1. In 7d mode, the 190px/day density squashes hour and wind ticks so tightly that values collide
> (e.g. 14 and 20 merge into "1420"). Increase 7-day density from 190px/day to ~330px/day (~41px per
> 3-hour interval). Verify that all 8 hour ticks and their corresponding mph wind speeds have clean
> horizontal padding and zero text overlapping. Keep 24h mode locked at ~550px/day.
> 2. In render.js, update the 0.0 ft calm color stop. Replace the dark slate blue with a vibrant,
> luminous cyan/aqua (#06b6d4 or #0891b2) at ~0.65-0.68 layer opacity. Calm water (< 0.5 ft / calm
> winds) must register visually as bright, clean turquoise rather than gloomy slate, while preserving
> label legibility underneath.

**Measured confirmation of the collision (orchestrator, current tree, text-run boxes via
`Range.getClientRects()`, not span boxes):** at 190 px/day the 7d wind row's minimum text gap is
**−0.7 px** (real overlap, first pair) and the tick row's is **0.5 px**; 24h is clean at **44.3 px**.
The 5M verifier missed this because it compared label *centres* (0.00 px) — span boxes are a fixed
1.5 em and hide ink collisions. §1's gate must therefore measure ink boxes.

## 1. 7-day density 190 → 330 px/day

- `pxPerDay('7d', …)` → **330** (7 × 330 = 2,310 px tape; 41.25 px per 3-hour interval).
  **`24h` stays `max(550, window)`** — do not touch it.
- Update the density comment in `src/render.js` beside `pxPerDay`.
- **Add a real gate (this is the durable fix for the miss):** in `tools/qa/stage5_check.py` group
  `[18]`, measure each row's *text runs* with `Range.getClientRects()` for the tick row and the wind
  row — for the 24h tape's first block **and** every 7d block:
  - no pair of consecutive runs may overlap (`gap >= 0`), and
  - the minimum gap must be **>= 6 px**,
  and print the 24h and 7d minimum gaps verbatim (`5n gaps 24h=…px 7d=…px`). Keep the existing
    centre-alignment assertion (worst tick-vs-wind delta <= 1.5 px) and the count/numeric assertions.

### Authorised constant sites (the ONLY places 190 is pinned — update all of them consistently)

| file | what |
| --- | --- |
| `src/render.js` | `pxPerDay('7d')` → 330 + comment |
| `tools/qa/stage5_check.py` | the three `190.0 if horizon == "7d"` sites (`pxf` computations) → 330.0 |
| `tools/qa/stage5_check.py` `[16]` | `ok_tape7 = 1100 <= m7["tapeW"] <= 1400` → **2280 <= tapeW <= 2340** |
| `tests/render.test.js` | `pxPerDay('7d', 374) === 190` → 330; `pxPerFrame('7d', 374) === 190/96` → `330/96`; the drag-math test's `const pxf = 190/96` → `330/96` (keep the assertions meaningful, do not delete them) |

**Never weaken a gate to make it pass.** The `[16]` range change is a deliberate constant change, not
a loosening — keep the band tight (±30 px). If a drag-sweep helper assumes the old 1,330 px tape and
can no longer reach an index clamp, extend the sweep (more pointer moves) rather than relaxing the
clamp assertion. Report anything that legitimately fails verbatim.

## 2. Cyan calm floor

- `HS_STOPS[0]` → **`[0.0, 0x06, 0xb6, 0xd4]`** (vibrant cyan, Reid's first choice) and
  `CALM_RGBA` → **`[0x06, 0xb6, 0xd4, 255]`** (they must stay equal — single source of truth).
- `OVERLAY_OPACITY` **stays 0.68**. Update the palette comments: the predicted calm composite is
  `0.68 × rgb(6,182,212) + 0.32 × rgb(205,207,207)` ≈ **`rgb(70, 190, 210)`** — bright, clean
  turquoise; bay/lake labels stay legible through it.
- **Known consequence to record in a code comment (do not "fix" it):** the 1.0 ft stop was already
  `#06b6d4`, so the 0–1 ft band is now a single flat cyan (its legend segment shows no gradient).
  Note it in the `HS_STOPS` comment; the orchestrator will report the alternative (`#0891b2` floor)
  to Reid.
- Update every pinned colour expectation:
  - `tests/ui.test.js`: `HS_STOPS[0]` → `[0.0, 0x06, 0xb6, 0xd4]`; `CALM_RGBA` → `[6, 182, 212, 255]`
    (both the literal and the equality-with-stop-0 check); the ramp-gradient test's `0%` entry →
    `rgb(6, 182, 212)` — and assert the duplicate explicitly (0 % and 16.7 % are both cyan) so a
    future reader does not mistake it for a bug.
  - `tools/qa/stage5_check.py` `[7a]`: the expected gradient colour list — `"rgb(3, 105, 161)"` →
    `"rgb(6, 182, 212)"` (the other five colours stay).
  - `tests/render.test.js` `paintRaster` calm case → the new RGBA values.
- Land stays exactly transparent; `colorForHs(0)` stays `[0,0,0,0]` (calm is painted via `CALM_RGBA`).

## Files allowed to touch

`src/render.js`, `src/ui.js`, `tests/render.test.js`, `tests/ui.test.js`, `tools/qa/stage5_check.py`,
and `index.html` **only** if a colour reference/comment there needs it (no structural changes).

## Done-when (command output is the proof)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js` → all exit 0.
2. `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → **0 lines**.
3. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py` → all groups ok except the tolerated pre-existing `[14] live seam` (quote it verbatim if it appears).
4. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/live_smoke.py --url http://127.0.0.1:8791/index.html` → all ok (server already on 8791 — do not kill it).
5. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py --url http://127.0.0.1:8791/index.html` → verdict PASS, quote the three modal latencies and the long-task maxima.
6. Evidence to print in your summary: (a) `[16]` line verbatim (7d tapeW + pxf); (b) `[18]` line verbatim **including the new gap numbers for 24h and 7d**; (c) `[7a]` line verbatim; (d) `[17]` line verbatim; (e) the 7d wind list of block 0 and its tick list; (f) `node tests/render.test.js` confirming `pxPerDay('7d', 374)=330` and `pxPerFrame=3.4375`.

## Procedure

- Ponytail ruleset. Current branch (`stage5n`); commits prefixed `stage5n:`; **do NOT merge, tag, or
  push** — the orchestrator handles the preview push and the screenshots.
- Do not touch the 5H decoupled scrub path (`scrubUiTo` / `scheduleMapPaint` / `endScrub`).
- Re-run the harness after editing; leave the tree clean.
