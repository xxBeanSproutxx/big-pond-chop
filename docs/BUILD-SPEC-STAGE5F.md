# Stage 5F — Windy-paradigm deck refactor (index.html / CSS / DOM only)

Work in THIS worktree only (branch `stage5f`). Do not touch /home/reid/projects/big-pond-chop (main checkout) or the sibling worktrees.

> **If any number in this spec conflicts with observed reality, trust reality and proceed; record the conflict in your report.**
> Follow the ponytail ruleset (laziest correct implementation). No test deletions; no weakened assertions — the assertion CHANGES listed under "Pre-authorised assertion changes" ARE this stage's documented contract change, nothing else.
> The code-review-graph may be stale in this worktree — use grep/read if graph results look wrong.
> **Deploy is OUT OF SCOPE: do NOT push, do NOT tag, do NOT touch the remote.** The orchestrator runs the production step after your commit is verified.

## Why

Stage 5's backend/data engine is good; the DOM/CSS missed the Windy visual paradigm. A frame-by-frame
review of the native Windy playback bar (recording: `tmp/recording-2026-09-11.mp4`, 1080x402, 22 s;
frames in `tmp/frames/`) fixed the reference:

- The play/pause control is **embedded in the far-left edge of the timeline track** — same dark surface,
  no button chrome, icon only.
- The timeline is a **solid, full-width bar partitioned into calendar-day blocks** with alternating
  charcoal shades and a divider at midnight; the day name ("Saturday 12") is **centred inside its block**,
  with a **sub-row of 3-hour numbers** (`03 06 09 12 03 06 09`) beneath it.
- The time indicator is an **amber badge with a downward triangular stem** — it sits permanently over the
  track (Windy shows `7 PM`; never hides).
- The **colour ribbon is flush against the bottom edge**, thinner than the track.
- There is no thin blue rail and no circular knob.

## Goal

Rebuild `#deck` to that paradigm. **Three docked things become TWO**: timeline track + ribbon.

### 1. Two-row compact deck

- **Delete the `.deck-main` row completely**: the separate clock (`#hour-label`), the `#deck-day` status
  text, the `#play-label` text, and the two big `#horizon` buttons all leave the deck.
- `#deck` children are exactly two rows:
  1. `#track` — the timeline track, **48 px** tall.
  2. the ribbon row (`.deck-ramp`: `#ramp-bar` + `#ramp-ticks`, ~20 px total, unchanged content).
- `--deck-h` becomes **68px** (48 + 20). `#deck` must measure **≤ 72 px** excluding
  `env(safe-area-inset-bottom)`. Delete every CSS rule for the removed rows/elements.
- The map must keep working after the height change: do not add new observers or resize plumbing; the
  existing `map.invalidateSize()` path on window resize stays as-is (verify it still fires; if the deck
  height is now static there is nothing new to do).
- The horizon toggle is **retained** as a discreet micro-pill in a **map corner** (not the deck), e.g.
  top-left under the header: small (≈28 px tall), 11 px text, `24 h` / `7 day`, same two buttons with
  **the same ids `#h-24h` / `#h-7d`**, `aria-pressed` semantics and `localStorage` + `?h=` persistence
  unchanged. It MUST remain a real, visible, clickable button (Playwright `page.click("#h-7d")` and
  `page.click("#h-24h")` must work, and `aria-pressed` must be readable) — the QA harness drives it.
  Keep it clear of the compass badge (top-right) and of Leaflet's zoom controls.

### 2. The amber pill cursor IS the playhead — permanently visible

- **Delete `#playhead`** (element, CSS, and every JS reference). No circular knob exists anywhere.
- `#time-pill` keeps its id, is **never hidden**: no `hidden` attribute, no fade, no timers, no
  interaction-gated visibility. Delete `pillHideTimer` and every code path that hides it, including the
  `hidden` attribute in the markup.
- Format: **bold 12-hour clock with AM/PM**, minutes shown only when non-zero:
  `10 AM`, `12 PM`, `1:15 AM` (minutes zero-padded to 2 digits; no leading zero on the hour; `12` not `0`
  at midnight/noon). Glyph `—` only before wind data lands, then never again.
- Look: amber (`#d69e0b` family) rounded badge, **white bold text** (Windy reference), ~68 x 20 px,
  plus a centred **downward-pointing triangle stem** (`::after`, ~8-9 px) whose tip marks the exact time
  position. It must glide smoothly while playing or scrubbing (keep a short `left` transition; keep it
  disabled under `body.reduced-motion`).
- The pill is clamped inside the timeline region at both ends (`clampPillX` stays — adapt its width
  constant to the new pill width). It must never overlap the play button.

### 3. Solid segmented day blocks + 3-hour sub-ticks (in the timeline region)

`#track` becomes a flex row: **`#play` (48 x 48, embedded, far-left) + `#timeline` (flex: 1,
`position: relative`, 48 px)**. Everything that used to be positioned inside `#track` moves into the NEW
`#timeline` container, and **all x-geometry helpers (`idxFromX`, `clampPillX`, the now-tick and pill
placement) must map into the `#timeline` rect** — not the `#track` rect, which now includes the play
button.

- **Delete `#track-rail` and `#track-progress`** (elements, CSS, JS references).
- The timeline is a **solid bar**: full height of the row, partitioned into calendar-day blocks built from
  the existing `dayPartitions()` result (`#track-days` stays the container, still absolutely positioned
  inside `#timeline`):
  - alternating background shades per block: `#262930` / `#1e2025`;
  - a clean **1 px vertical divider** (`#3a3f4a`) at each midnight boundary;
  - a **bold, high-contrast day header** per block, horizontally **centred**, e.g. `Friday 11`,
    `Saturday 12` — falling back to an abbreviated form (`Fri 11`) when the block is too narrow, and to the
    day number alone when even that does not fit. Never clip or overlap between blocks.
- **3-hour sub-row** beneath the day header: `03  06  09  12  03  06  09  12 …` — zero-padded 2-digit
  12-hour numbers, positioned at their true fraction of the day block. Thin them out when they would
  collide: pick the smallest step from {3 h, 6 h, 12 h, 24 h} whose rendered spacing stays ≥ 12 px.
  (At 390 px / 7 days a per-3 h label set cannot fit — that is expected and must degrade, not overlap.)
- **Keep the now marker**: the thin, high-contrast yellow vertical hairline (`#now-tick`) at the real
  "now" position, hidden only under the existing `?hour=` / `?frame=` override.
- Keep `#track` as the slider surface: `role="slider"`, `tabindex="0"`, `aria-label`, and
  `aria-valuemin` / `aria-valuemax` / `aria-valuenow` / `aria-valuetext` written exactly as today
  (`aria-valuemax` = 95 for `24h`, 671 for `7d`). Deck-wide pointer capture, keyboard seek
  (Arrow/Home/End behaviour), play-step and prefetch must all keep working unchanged.

### 4. Seamless transport

- `#play` is embedded inside the far-left of `#track`: **no button chrome** (no background fill, no
  border, no radius), icon-only — `▶` when paused, `⏸` when playing, clean white (`#e8f0f7`), ~20 px,
  48 x 48 hit area. Delete `#play-label`.
- Tapping `#play` toggles playback; touching/dragging anywhere else on `#track` scrubs (the play button
  must not be swallowed by the scrub surface, and dragging from inside `#play` must not scrub).
- Keep `aria-pressed` and the `data-state` icon swap working.

## Files allowed to touch

`index.html`, `src/render.js`, `src/ui.js`, `tests/render.test.js`, `tests/ui.test.js`,
`tools/qa/stage5_check.py`, `docs/STAGE-5F-RECEIPTS.md` (new).

## Out of scope

Everything else — explicitly: `src/wave-math.js`, `src/wind.js`, `src/tables.js`, `public/*`, the
physics engine, the LRU cache, the vector interpolation, `tools/export_tables.py`, the header, the tap
card, the OG image, `docs/STAGE-*.md` (except the new 5F receipts), any git remote operation.

Do not change: `ui.rampGradient()`'s six Hs stops, `#ramp-ticks`' stop list, the `#boot` overlay
contract (skeleton hides whenever a frame paints, `bootHidden` reset inside `boot()`), tier logic, the
verdict text, or any engine test.

## Pre-authorised assertion changes (the ONLY permitted test edits)

1. **`tests/render.test.js` id list** (≈ line 123): replace the required-id set with the new DOM —
   `play`, `track`, `timeline`, `track-days`, `track-ticks`, `track-label`, `now-tick`, `time-pill`,
   `h-24h`, `h-7d`, `ramp-bar`, `ramp-ticks` — and keep asserting the REMOVED ids are absent
   (`playhead`, `track-rail`, `track-progress`, `deck-day`, `hour-label`, `play-label`, `deck-main`).
2. **`tests/render.test.js` `clampPillX` test** (≈ line 287): update the pill width constant to the new
   width; the both-ends-clamped behaviour is unchanged.
3. **`tools/qa/stage5_check.py` geometry sources**: anywhere a check reads `#track-rail` (notably the
   `[7b] touch ergonomics` drift/clamp helper) read the `#timeline` rect instead.
4. **`tools/qa/stage5_check.py` `[7b]` pill-visibility assertions**: the pill no longer hides after a
   scrub. Invert those assertions — assert `#time-pill` is **visible and un-hidden during AND after**
   the drift (both the first drift and the deck-wide drift), and that its text is a non-empty timestamp.
   The landed-index (±1), play-not-toggled, and both-ends clamp assertions stay.
5. **`tools/qa/stage5_check.py` `[7b]` second drift**: it currently presses inside `.deck-main`; the deck
   is now two rows, so press inside the **`.deck-ramp` row** (still required to be non-interactive) and
   keep the wander-±80 / land ≈70 % proof.
6. **`tools/qa/stage5_check.py` NEW group `[15] deck geometry (5F)`** — assert, on the 390x844 page at
   the default (24 h) horizon:
   - `#deck` height ≤ 72 px (getBoundingClientRect, safe-area excluded);
   - `.deck-main`, `#playhead`, `#track-rail`, `#track-progress` are ABSENT from the DOM;
   - `#time-pill` is visible with a non-zero rect **immediately after boot, before any interaction**,
     and `#time-pill` has no `hidden` attribute;
   - `#play`'s rect is inside `#track`'s rect (embedded, left edge);
   - `#timeline` rect is inside `#track` and starts at/after the play button's right edge;
   - at least one day block exists in `#track-days` and adjacent blocks differ in background colour;
   - the ribbon row's bottom is flush with `#deck`'s bottom (±2 px).

Print the measured numbers in the check's detail line (heights, rects) — the receipts need them.

## Done when

1. `tools/qa/stage5_check.py` prints **`SUMMARY: N ok, 0 FAIL` with N ≥ 21** (20 existing groups + the new
   `[15]`), reproducing verbatim into `docs/STAGE-5F-RECEIPTS.md`.
2. All four Node suites pass (`tests/parity.test.js`, `tests/wind.test.js`, `tests/render.test.js`,
   `tests/ui.test.js`) — no test deleted, no assertion weakened outside the six items above.
3. The harness writes screenshots to `tmp/s5f-shots/`: `24h.png`, `7d.png`, `scrub.png` at 390x844
   (DPR 2) and `24h-360.png` at 360x800 — phone viewport, deck visible at the bottom of the frame.
4. `docs/STAGE-5F-RECEIPTS.md` contains: the verbatim harness run, the four suite tails, the measured
   deck/pill/ribbon numbers, a table of every test/assertion you changed with a one-line justification,
   and the screenshot paths.
5. One commit on `stage5f`, message `Stage 5F: Windy-paradigm deck rebuild (2-row deck, permanent amber pill, segmented day blocks)`.
   Report back with: files changed, `git diff --stat`, the harness summary line, and any conflict between
   this spec and observed reality.
