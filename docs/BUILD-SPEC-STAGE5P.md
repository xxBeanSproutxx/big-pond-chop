# BUILD SPEC — Stage 5P: wind speeds embedded inside the heat ribbon (3-tier deck, ~62 px)

Repo: /home/reid/projects/big-pond-chop (branch `stage5p`, off `stage5o` @ `d167026`)

Reid's brief (2026-09-12) — the final UI refinement before merging to `main`:

> 1. Merge Wind Numbers and Heat Ribbon into a Single Unified Bar: eliminate the separate floating
> wind speed row above the 6 px sliver; expand the colored ribbon to **~18-20 px**, flush along the
> bottom of the day blocks, and place the wind speed numbers **directly inside the ribbon**, centered
> vertically + horizontally beneath each hour tick.
> 2. Text Contrast: numbers must stay crisp on every tier colour — bold white `#ffffff`, weight 700,
> with `text-shadow: 0 1px 2px rgba(0, 0, 0, 0.65)` (or dynamic contrast logic).
> 3. Deck height: standardize the day block into **3 vertical tiers** — header (sticky/centered),
> hour ticks (muted), ~18 px ribbon with embedded speeds — and lock `#deck` to **~60-64 px**.
> 4. Preserve: alternating `#23272e` / `#1b1d22` blocks, midnight dividers, sticky day headers,
> the `#0891b2` calm lake floor, and the 16.4 ms decoupled scrub performance.

## Layout (exact)

`--deck-h: 62px` (Reid's 60-64 band); `#track` / `#timeline` become **62 px** tall.

| tier | element | spec |
| --- | --- | --- |
| 1 | `.day-head` | `top: 3px`, `600 12px/1`, `#e8f0f7` — sticky/centred behaviour unchanged |
| 2 | `.day-sub` | `top: 20px`, `11px/1`, `#94a3b8` (edge ticks stay `#e8f0f7`) |
| 3 | `.day-heat` | `left: 3px; right: 3px; bottom: 2px; height: 20px; border-radius: 3px`, gradient unchanged (24 hourly stops, tier palette) |
| 3b | `.day-wind` (numbers) | **inside the ribbon**: `top: 40px; height: 20px; line-height: 20px` → vertically centred in the 40-60 px band; `font: 700 12px/1`; `color: #ffffff`; `text-shadow: 0 1px 2px rgba(0,0,0,.65)`; `width: 20px; text-align: center; font-variant-numeric: tabular-nums` |

- The numbers keep the **existing `tickWinds()` data + anchor rules** (h=0 left-anchored at 3 px, all
  others `left: clamp(6, w-6, (h/24)*w)` with `translateX(-50%)`) so each number sits exactly under
  its hour tick and over its own gradient sample. Keep the class name `.day-wind`.
- The ribbon is painted **behind** the numbers (numbers later in DOM order / no z-index games).
- No new pure helpers are required — `windHeatColor` / `windHeatGradient` / `tickWinds` stay as they
  are, and their node tests must keep passing untouched.

## Gate contract updates (authorised; these are the ONLY ones)

- `[15] deck geometry`: the tape-row height assertion `68` → **62** (±1) — rename the internal flag and
  the printed label accordingly; `deckH <= 72` still holds (61-63 passes); `stripAbsent`,
  `play-inside` (48 px button in a 62 px row), `timeline-fills` unchanged.
- `[18]` — replace the `5o rows` sub-block with `5p ribbon`:
  - ribbon height **20 px** (±1) — replaces the 6 px assertion;
  - **numbers live inside the ribbon**: for every block, each `.day-wind` rect must be vertically
    contained in its `.day-heat` rect (`num.top >= ribbon.top - 1` and `num.bottom <= ribbon.bottom + 1`);
  - computed style of a number: `700 12px`, colour `rgb(255, 255, 255)`, `textShadow != 'none'`;
  - keep every existing wind assertion — 8 numeric values per block, boundary `12` has none,
    tick-vs-wind centre alignment ≤ 1.5 px, ink gaps ≥ 6 px with no overlap (the ink-gap gate now
    measures the white numbers over the ribbon; quote the new 24h/7d minima);
  - keep the gradient assertions (24 stops, ≥ 2 tiers tape-wide, all stops from the palette).
- `[7b]`, `[16]` (`tape=2310`, band 2280-2340), live smoke and the scrub bench need **no** constant
  changes — verify and report if any turns out otherwise.

**Preserve everything else:** alternating tones exactly `rgb(35,39,46)` / `rgb(27,29,34)`, the
`#4a5568` midnight divider, sticky header behaviour (`STICKY_INSET = 56`, x 201 → 64), the calm floor
`#0891b2` @ 0.68 (untouched), and the 5H decoupled scrub path (`scrubUiTo` / `scheduleMapPaint` /
`endScrub` / `shouldPaintMap` — **zero** changed lines).

**Never weaken a gate to make it pass.** Report any legitimate failure verbatim.

## Files allowed to touch

`index.html`, `src/render.js`, `src/ui.js` (only if a comment needs the new band), `tests/ui.test.js`,
`tests/render.test.js`, `tools/qa/stage5_check.py`. (`tools/qa/live_smoke.py` only if a pinned value
breaks — say so explicitly.)

## Done-when (output is the proof)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js` → all exit 0.
2. `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → **0 lines**.
3. `stage5_check.py` → all groups ok except the tolerated pre-existing `[14] live seam` (quote verbatim if it appears).
4. `live_smoke.py --url http://127.0.0.1:8791/index.html` → all ok (server already on 8791).
5. `scrub_bench.py --url http://127.0.0.1:8791/index.html` → PASS; quote the three medians + long-task maxima.
6. Evidence: (a) `[15]` line verbatim (deckH + tape row); (b) the `5p ribbon` line verbatim incl. the
   ink-gap minima; (c) one number's computed style (size/weight/colour/shadow); (d) the containment
   result per block (numbers inside the ribbon); (e) `[18]`'s wind list + tick list; (f) `[17]` verbatim;
   (g) `[16]` verbatim.

## Procedure

- Ponytail ruleset. Current branch (`stage5p`); commits prefixed `stage5p:`; **do NOT merge, tag, or
  push** — the orchestrator handles the preview push, screenshots and the brain update.
- Re-run the harness after editing; leave the tree clean.
