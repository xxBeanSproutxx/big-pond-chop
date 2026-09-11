# big-pond-chop — BUILD SPEC (stage 4B: UI/DOM — wind badge, condition tier, clock ergonomics, touch + loading polish)

Status: **APPROVED by Reid 2026-09-11.** Stages 1-3 and 4A are frozen. Build **ONE commit**.

Follow the **ponytail ruleset (laziest correct implementation)**. Report the ACTUAL shipped API back.
If any number in this spec conflicts with observed reality, **trust reality and say so**.

## Goal

Ship the four user-facing polish items on top of 4A's engine: the split wind metric + on-map compass
badge, the condition tier chip, 12-hour time ergonomics (clock label, now-snap, now-tick), and the
touch/loading/card polish. **Chrome and DOM glue only** — the render pipeline, physics, and data
contract are frozen.

## Files allowed to touch

- `index.html`
- `src/ui.js`
- `src/render.js` — **`mount()` DOM glue only** (node lookups, text/attribute updates, event wiring)
- `tests/ui.test.js` — **add new sections only; do not modify or delete ANY existing assertion**
- `docs/BUILD-SPEC-STAGE4B.md` (this file — you may append a `## Notes / shipped API` section)

**FROZEN — do not edit:** `src/wave-math.js`, `src/tables.js`, `public/*`, `tests/parity.test.js`,
`tests/render.test.js`, `tests/wind.test.js`, `tools/*`, and inside `src/render.js`: everything
except `mount()`'s DOM/UI wiring — specifically DO NOT change `computeFrame`, `frameFor`,
`createFrameCache`/`cacheKey`/`frameBytes`, `gatherRaster`, `landMaskRaster`, `smoothRaster`,
`targetWidth`, `paintRaster`, the rAF-coalescing mechanism (`requestFrame`), the regather debounce,
or any `body.dataset.*` value (including `data-hour` which stays full ISO like `2026-09-11T17:15`),
or `window.__bpcTap`.

## 0. Locked decisions from Reid (2026-09-11) — implement EXACTLY

1. **Condition tiers, evaluated strictly RED → AMBER → YELLOW → GREEN (first match wins):**
   - `red` — `Dangerous · Stay Home`: max ≥ 5.0 ft **OR** roller ≥ 4.0 ft **OR** H/L ≥ 0.055
   - `amber` — `Heavy Rollers`: max ≥ 3.5 ft **OR** roller ≥ 2.5 ft
   - `yellow` — `Walleye Chop`: max ≥ 2.0 ft **OR** roller ≥ 1.5 ft
   - `green` — `Fishable · Light Chop`: default (max < 2.0 ft AND roller < 1.5 ft)
2. **Compass arrow points INTO the wind (at the source), matching the text label** — for a 315°
   source the arrow aims toward 315° (up-left). Weather-vane / boater convention.
3. Scrub rendering is already rAF-coalesced (4A). Do not regress it.

## 1. Wind split + compass badge

**`src/ui.js` (pure, tested)**
- `windLine(speedMph, gustMph)` → `Wind: 14 mph · Gusts 26 mph` (0 decimals). Speed < 3 → `Wind: calm`.
  Missing/NaN gust → `Wind: 14 mph`. Never emit `NaN`, `undefined` or `Infinity`.
- `compass(bearingDeg)` → `{ sector, degText, arrowDeg }`:
  `sector` = the existing 8-way `SECTORS` name; `degText` = `` `${Math.round(normalize(b))}°` ``;
  `arrowDeg` = the normalized bearing (arrow points INTO the wind). Calm (< 3 mph) → `{ sector:'Calm',
  degText:'', arrowDeg:null }`.

**`index.html`**
- `#wind-info` keeps its id; its text becomes the `windLine()` output (bearing moves to the badge).
- New on-map badge, docked bottom-left of the Leaflet zoom control (do NOT overlap it):

```html
<div id="wind-badge" role="img" aria-label="Wind from NW at 315 degrees">
  <span id="wind-badge-disc">
    <svg id="wind-badge-arrow" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"
         fill="#ffd166"><path d="M12 2 L17.5 20.5 L12 16.2 L6.5 20.5 Z"></path></svg>
  </span>
  <span id="wind-badge-text">NW 315°</span>
</div>
```
  Arrow path pinned (a symmetric navigation arrow that points NORTH when unrotated). Rotate with
  `transform: rotate(<arrowDeg>deg)`. Calm → hide the arrow, text `Calm`.
  CSS: `position:absolute; left:10px; top:62px; z-index:500; display:flex; align-items:center;
  gap:6px; height:32px; border-radius:16px; background:rgba(16,38,58,.85);` disc 32×32 with the
  arrow centered; text 12px, tabular numbers, `white-space:nowrap`. Must stay inside `#map`.
- Header restructure, keeping the 72 px fixed height and every existing id:
  - `#verdict-range` + the new `#comfort-chip` on row 1, `#refresh` on the right, `#verdict-peak`
    full-width on row 2, `#secondary` (wind + H/L) as today.
  - **The header must measure exactly 72 px tall after your change** — measure it in the DOM check
    below. If content does not fit at 360 px width, shrink the chip/badge text, never grow the header.

**`src/render.js` (`showFrame` wiring only):** update `#wind-info` (from `windLine`), `#wind-badge-text`
and the arrow rotation (from `compass`), and the badge `aria-label`.

**Tests (`tests/ui.test.js`, new section):** `windLine` (normal / calm / missing gust), `compass` at
0/45/90/180/315/359°, wrap-around, `arrowDeg === normalize(bearing)`, calm → null.

## 2. Condition tier chip

**`src/ui.js`:** `comfortTier({ maxHsFt, rollerFt, hlMax })` → `{ key, label }` implementing the
locked table in §0.1 verbatim (first match wins, `≥` semantics). Labels exactly:
`Dangerous · Stay Home` / `Heavy Rollers` / `Walleye Chop` / `Fishable · Light Chop`.
Missing/NaN inputs → treat that condition as not-triggering (never throw, never return undefined).

**`index.html`:** `<span id="comfort-chip" class="tier-green">Fishable · Light Chop</span>` inside the
header, 11 px bold, 3 px radius, `white-space:nowrap`. Tier colors (text always present — never
color-alone): green `#15803d`/`#fff`, yellow `#facc15`/`#0d1b2a`, amber `#ea580c`/`#fff`,
red `#dc2626`/`#fff`. Update the class + text in `showFrame` from the frame stats
(`s.maxHs`, `s.rollerFt`, `s.hlMax`).

**Tests (new section):** exact boundaries (roller 4.0 → red; 3.9 with max 3.4 → amber; max 3.5 → amber;
max 2.0 → yellow; roller 1.5 → yellow; 1.49 with max 1.99 → green; H/L 0.055 → red even with tiny
waves), label strings exact, and a monotonicity property scan (raising max or roller never yields a
less-severe tier).

## 3. Time ergonomics

**`src/ui.js`:** `formatClockLocal(isoLocal)` → `5:15 PM CDT` / `5:00 PM CDT` (12-hour, no leading
zero, `America/Chicago`, DST-safe via Intl — a 2-pass offset resolve is fine; never string-slice the
hour). Tests: `2026-09-11T00:00` → `12:00 AM CDT`; `12:00` → `12:00 PM CDT`; `17:15` → `5:15 PM CDT`;
a January date → `CST`; the 2026-11-01 DST-transition day must not throw.

**`index.html`:** wrap the slider — `<div id="scrub-wrap">` containing `#now-tick` (2 px wide,
`#ffd166`, `pointer-events:none`, absolutely positioned) and `#scrub` (ids unchanged).

**`src/render.js`:** `#hour-label` shows `formatClockLocal(e.time)`. `body.dataset.hour` keeps the
ISO string (unchanged). Position `#now-tick` at `left: (nowIndex / (frames.length - 1)) * 100%` once
frames are built — and NOT when `?hour=`/`?frame=` overrides are present (the tick marks "now", the
snap may point elsewhere). Snap-to-now is already the existing behaviour — keep it.

## 4. Touch ergonomics, loading states, tap-card polish

- **Touch targets ≥ 48×48**: `#refresh`, `#play`, `#card-close` (44 → 48), and `#scrub`
  (`height:48px` with a 28 px visual thumb via `::-webkit-slider-thumb` + `::-moz-range-thumb`).
  `#controls { touch-action: none; }`, buttons `touch-action: manipulation`.
  KEEP `#refresh` `aria-label`/`title` and the `#play` label + `aria-pressed` behaviour.
- **Loading skeleton `#boot`** inside `#map`: dark panel + `#boot-bar` progress + `#boot-text`
  ("Loading wave map…"). Fetch `public/tables.v1.bin` with a **streaming reader** (`response.body
  .getReader()`) to drive a real percentage from `Content-Length`; indeterminate if the header is
  missing. The wind payload gets an indeterminate state ("Loading wind…"). Hide on first painted
  frame. It must not prevent the map from appearing once ready.
- **Retry toast**: `#note` keeps its id and gains a `<button id="note-retry">Retry</button>`.
  Distinct messages: `map data failed — retry` vs `wind unavailable — retry`. Retry re-runs ONLY the
  failed step (already-decoded tables must not be refetched).
- **Card**: keep `#card-close` (now 48×48). A tap on land / nodata must **dismiss the card** and show
  `land — no wave data here` in `#readout` for ~2 s, then revert to the default hint. Water taps
  behave exactly as today (pin + full card, playback pause).

## Done when

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js`
   — all four print `ALL TESTS PASSED`, and the FIRST THREE are byte-identical to their pre-4B output.
2. New `tests/ui.test.js` sections pass (§1, §2, §3 above); no existing assertion modified.
3. **Browser check (attempt it; report honestly if the harness won't start):** serve the repo
   (`python3 -m http.server 8766` from the repo root) and drive it with
   `/home/reid/.hermes/hermes-agent/venv/bin/python` + playwright (chromium is already installed in
   `~/.cache/ms-playwright`). Assert, at 390×844: header height === 72; `#comfort-chip` text matches
   the tier for the shown frame; `#wind-badge-text` shows `<sector> <deg>°`; `#hour-label` matches
   `h:mm AM/PM CDT`; `#now-tick` exists; `#refresh`/`#play`/`#card-close` bounding boxes ≥ 48×48;
   a land tap dismisses the card and shows the hint; **zero console/page errors**. Save screenshots to
   `/tmp/bpc-4b-*.png` at 360 and 390 px widths. If the browser cannot be started after ~2 attempts,
   say so plainly and stop trying — the orchestrator owns 4C.
4. **ONE git commit**: `Stage 4B: wind split + compass badge, condition tier chip, 12-h clock + now tick, 48px touch targets, loading skeleton + retry, land-tap dismiss`
   — diff limited to the allowed files.

## Out of scope (do not touch)

The render pipeline and cache (4A.2 owns the async-encode / playback-resolution work), the physics,
the bundle format, `data-*` semantics, the palette, the legend, the OG/social card, deployment.

## Receipts to include in your final message

(a) the four suite tails; (b) the browser-check results (or why it could not run); (c) `git show --stat`;
(d) the shipped API of the new `src/ui.js` helpers (exact signatures); (e) anything you could not do.

## Notes / shipped API

Shipped `src/ui.js` exports (in addition to the existing ones):

- `normalizeDeg(deg) -> number` — bearing wrapped into `[0, 360)`.
- `windLine(speedMph, gustMph) -> string` — `Wind: 14 mph · Gusts 26 mph`; speed < 3 (or non-finite)
  → `Wind: calm`; missing/NaN gust → `Wind: 14 mph`.
- `compass(bearingDeg, speedMph) -> { sector, degText, arrowDeg }` — 8-way sector, `${round(normalize)}°`,
  normalized `arrowDeg` (points into the wind). Calm (`speedMph < 3`, or non-finite) → `{ sector:'Calm',
  degText:'', arrowDeg:null }`.
- `comfortTier({ maxHsFt, rollerFt, hlMax }) -> { key, label }` — strict red→amber→yellow→green.
- `formatClockLocal(isoLocal) -> string` — `5:15 PM CDT` (12-hour, America/Chicago, two-pass DST resolve).
- constants `CALM_MPH` (3), `CHICAGO_TZ`, `TIERS`.

### Deviations from the spec text (reality wins)

1. **`compass` takes a second optional arg `speedMph`.** Calm is defined by a wind *speed*, so a single
   bearing cannot decide it. `compass(bearing)` still works (finite bearing → non-calm); `compass(b, s)`
   returns the calm shape when `s < 3`. The spec's `compass(bearingDeg)` signature cannot express the
   required "calm → null" test.
2. **Header row 2 is shared by `#verdict-peak` and `#secondary`** (wrapped in `#subrow`). The split
   `windLine` ("Wind: 14 mph · Gusts 26 mph") is far longer than the old line; range + chip + secondary +
   refresh cannot fit one row at 360/390 px, and a third row overflows the locked 72 px. Both rows keep
   every existing id; measured `header.clientHeight === scrollHeight === 72` at 360 and 390 (no clipping).
3. **Badge `top: 74px`, not `62px`.** Leaflet's touch zoom control is 30 px/button, so it ends 146 px
   absolute; `top:62` overlapped it by 12 px. At 74 px the badge top exactly meets the control bottom
   (146 == 146), satisfying "do not overlap".
4. `windLine` treats a non-finite speed as calm (spec only named `< 3`; this keeps the "never NaN"
   guarantee).
