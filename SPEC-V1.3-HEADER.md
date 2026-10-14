# SPEC v1.3 — Header pass: "back to now" button + card-language header

Context: Mille Lacs wave PWA, vanilla JS, no build step, bare Node tests (NO package.json — keep it that way, no npm deps). Production styling lives in `index.html` `<style>`; logic in `src/*.js`. The popup card (shipped v1.2) is the design language to match: quiet labels (#64748b-family, 11px, weight 600) + bold near-white values + one rounded pill family (`#card .pill` — find its exact radius/padding in index.html and reuse those values).

Work on a new branch `v1.3-header` off current main.

## Goal
1. **Merge "Now" into the existing refresh button.** `#refresh` currently calls `refreshWind()` (src/render.js ~line 1636) which refetches wind and — via applyWindData — already snaps the timeline to now. ADD: recenter/refit the map to the full-lake boot view (`fitLake()`, src/render.js ~line 658, already reserves header height) in the refresh success path, after applyWindData. Update aria-label/title to "Back to now — recenters map, refreshes data". Add a subtle press state on the button (`:active { transform: scale(.96); }` with a ~120ms transition) unless one already exists.
2. **Add lake-wide AVERAGE wave height to the verdict** (Reid's ask: human-readable "average wave height" like the card). Row 2 of the verdict becomes: `Avg <x.x> ft · Peak <y.y> ft · <place>`. Compute the average in the SAME place p10/max/roller are already gathered per frame (no second data pass). Format: one decimal + " ft", dash when not finite, same convention as existing values. Add a helper in src/ui.js (e.g. alongside the existing verdict/headline formatters) + one test pinning it in tests/ui.test.js.
3. **Card-language restyle of the header (CSS-first, index.html):**
   - `#comfort-chip`: from 3px-radius rectangle → 999px pill matching `#card .pill` geometry, same tier-* color classes it already uses.
   - Wind badges `#pill-lake` / `#pill-gust`: same 999px pill family; number bold white, unit/label quiet (#cbd5e1), consistent internal emphasis between both badges.
   - Verdict rows: quiet-label + bold-value treatment. Row 1 `Waves` label quiet, range value bold near-white (tabular-nums as now). Row 2: labels ("Avg", "Peak") quiet #94a3b8-style, values near-white, place name muted slate. RETIRE the amber color on the peak line (color now lives in chip + wind badges only).
   - Header band "fancier": bump the frosted glass (backdrop-filter ~blur(16px) saturate(1.3)), tidy padding rhythm (~10–12px), keep the existing 72px content height EXACTLY.

## Files allowed to touch
`index.html`, `src/render.js`, `src/ui.js`, `tests/ui.test.js`. Nothing else.

## Hard constraints
- Header height stays `var(--header-h)` = 72px content + notch inset. No layout shift when verdict text length changes (the map must never move).
- `src/wave-math.js`, `src/tables.js`, `src/wind.js` UNTOUCHED (math is byte-pinned by tests).
- Touch targets stay ≥44px. Text contrast on the glass: values ≥4.5:1, quiet labels ≥3:1.
- No new dependencies, no Leaflet changes, NO sw.js cache bump (that happens at ship time, not now).
- Keep the two-line verdict structure (design-locked); avg joins row 2, do not add a third row.

## Done-when (all verified, not assumed)
- `node tests/ui.test.js` green including the new avg-format test; also run `node tests/render.test.js`, `node tests/parity.test.js`, `node tests/weather.test.js`, `node tests/wind.test.js`.
- `python3 tools/qa/pwa_check.py` local pass (same ok/0-FAIL shape as before).
- `python3 tools/qa/lane_audit.py --url http://127.0.0.1:8788/` PASS.
- `python3 tools/qa/storm_sim.py --url http://127.0.0.1:8788/` PASS.
- Click #refresh in headless Chromium (viewport 390x844): map refits AND frame returns to the now-tick AND a refetch happens (assert via network request count or console hook).
- Commit on `v1.3-header`, message: `v1.3 WIP: header card-language + back-to-now merge`. Do NOT push, do NOT merge to main, do NOT bump sw.js.

## Out of scope
Map corner buttons (#horizon, wind/compass badge, zoom stack), timeline deck, popup card, performance work, deploy, domain, analytics.
