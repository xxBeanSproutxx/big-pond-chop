# SPEC v1.3b — Port approved "Instrument Hero" header (sketch 009) into the real app

Context: branch `v1.3-header` already carries the v1.3 WIP (commits 8a8e866, b8fb82a): back-to-now refresh (`scheduleRefit()` in refreshWind, aria label, :active press), `ui.mean()` avg-waves computed per frame (`avgHsFt` in the stats gather), and quiet-label verdict spans. THIS spec replaces the header's visual anatomy with the approved sketch. **`sketches/009-bars-baseline/index.html` is the approved design source of truth — port its anatomy exactly.** (History: 001→009 workshop, Reid approved 009 verbatim with "Looks great.")

## Goal
Rebuild the production `<header>` (index.html + render wiring) to match sketch 009:
1. **Header = 80px content height.** Bump `--header-h` from `calc(72px + env(safe-area-inset-top))` to `calc(80px + ...)`. Verify `.leaflet-top` offset (which uses the same var) follows, and fitLake's reservation is live-height-based (it is: `headerBand()` reads the DOM). Frosted glass unchanged (blur(16px) saturate(1.3), same fill/hairline).
2. **Hero block** (left): tiny caps label `AVG WAVES` (10px, #94a3b8, letter-spacing .14em) → number row → sub line. Number: 38px/800, tabular-nums, tier-tinted color, `0.7<small>ft</small>` (small = 14px/600 #cbd5e1). Sub: `Peak <b>1.8 ft</b> · Sunset Bay` (11.5px #94a3b8, bold value #e2e8f0).
3. **Wave-scale gauge INSIDE the number row**: `.numrow { display:flex; align-items:flex-end; gap:7px }`, meter after the number. 8 bars (5px wide, 2.5px gap, heights 5→22px per the sketch's nth-child ladder, radius 2px 2px 0 0, unfilled rgba(148,163,184,.22)). Filled bars: `background: var(--tier-c); box-shadow: 0 0 6px var(--tier-g)`. Bars bottom lift: `.meter { padding-bottom: 7px }` (the approved baseline fix). Mapping: `filled = ceil(avgFt / 6 * 8)` over the app's 0–6 ft ramp; 0/NaN → 0 bars. Add `ui.barsForAvg(avgFt)` helper in src/ui.js + pin it in tests/ui.test.js (0→0, 0.7→1, 1.4→2, 2.6→4, 4.2→6, 6→8, NaN→0).
4. **Tier wiring**: the existing comfort-tier logic (tier.key used by #comfort-chip) ALSO drives a class on `<header>` (`t-green|t-yellow|t-amber|t-red`). CSS custom props per class: `--tier-c` / `--tier-g` exactly as sketch 009 (green #22c55e / rgba(34,197,94,.45); yellow #facc15 / rgba(250,204,21,.45); amber #f97316 / rgba(249,115,22,.5); red #ef4444 / rgba(239,68,68,.55)). Consumers: the 3px glow `.accent` bar (absolute bottom:-1px, full width), the hero number color, and the gauge bars. Chip keeps its EXISTING production tier-* fills (green #15803d etc. — do not change chip colors; the sketch chip is just the production chip at 999px radius).
5. **Keep from the v1.3 WIP untouched**: #refresh = back-to-now (scheduleRefit + aria "Back to now — recenters map, refreshes data" + :active scale(.96) + 120ms transition); the avg computation (ui.mean / avgHsFt); wind pills row (existing production anatomy — in 009 they sit in `.side` with the chip above them: `row1 = chip`, `row2 = wind pill · gust pill · now button`, right-aligned, 7px column gap). Chip = 999px pill (already done in WIP).
6. **A11y**: the old `<h1>Mille Lacs wind waves</h1>` disappears visually — keep it as a visually-hidden (sr-only) h1. Gauge gets aria-hidden (decorative duplicate of the avg number) and the number gets an aria-label like "Average waves 0.7 feet".

## Files allowed to touch
`index.html`, `src/render.js`, `src/ui.js`, `tests/ui.test.js`, `tests/render.test.js`. Nothing else.

## Hard constraints
- Header height is var-driven and live-read; the map must NEVER shift when text/tier changes. No layout shift on tier flips (number width varies 0.0–9.9 — reserve via tabular-nums + min-width on the number so the gauge doesn't jump).
- `src/wave-math.js`, `src/tables.js`, `src/wind.js` UNTOUCHED.
- NO sw.js cache bump (ship-time), no push, no merge to main.
- `scheduleRefit` is the ONLY way to refit from outside setupMap (fitLake is setupMap-scoped — do not re-break this).
- Touch targets ≥44px, values contrast ≥4.5:1 on the glass, tier-tint number ≥3:1 on the glass (sketch colors pass; verify).

## Done-when (verify, don't assume)
- All 6 node test files green (incl. new `ui.barsForAvg` pins + updated render.test header pins).
- `pwa_check.py` (hermes venv python) 11 ok / 0 FAIL — fresh load console.error=0 (watch for scope errors like the fitLake incident).
- `lane_audit.py --url http://127.0.0.1:8788/` PASS, `storm_sim.py --url http://127.0.0.1:8788/` PASS.
- Headless check: header height == 80px content; tapping #refresh refetches + refits (open-meteo request count +1); bars count changes when frame changes (scrub to a different hour → different fill).
- Commit on `v1.3-header`: `v1.3: port approved hero header (sketch 009) — avg number + wave-scale gauge + tier glow`.

## Out of scope
sketches/ cleanup, timeline deck, popup card, deploy, SW bump, performance work, domain.
