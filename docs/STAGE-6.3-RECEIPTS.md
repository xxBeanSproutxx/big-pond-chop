# STAGE 6.3 — RECEIPTS

Stage 6.3 polish: water-mask cleansing (item 1), map containment & rubber-band (item 2),
60 fps scrub (item 3), header gust trim (item 4). Spec: `docs/SPEC-stage-6.3-polish.md`
(APPROVED; bold defaults locked D1.1–D1.5, D2.1–D2.4, D3.1–D3.5, D4.1–D4.2).

- Base revision: `87a52cb` (6.2, tag `stage-6.2-polish`)
- Item-1 commit: `e68c90a` — water-mask cleansing
- Items 2–4 + gates commit: `7a0a149`; gate-rig corrections + this doc: tag
  **`stage-6.3-shipped`** (this tree)
- Production: https://xxbeansproutxx.github.io/big-pond-chop/ — post-deploy smoke
  appended in §4/§5 after the Pages rebuild.

## 0. What was built

| item | files | summary |
|---|---|---|
| 1 | `tools/export_tables.py`, `public/tables.v1.bin`, `public/meta.v1.json`, `public/mask.v1.json` | largest 4-connected water body kept (D1.1); satellites dropped; mask receipt written |
| 2 | `src/render.js` | `maxBoundsViscosity: 0.75`; `fitLake()` rework (`setMinZoom(0)`-before-measure guard); pan box `fitCenter ± half(paddedSpan)`; debounced refit on resize/orientation |
| 3 | `index.html`, `src/render.js` | permanent `will-change: transform` on `#track-tape` (D3.1); velocity-gated encode/swap (V_HI 0.25 / V_LO 0.08 / EMA α 0.3 / 1.2 s valve, D3.3); drag-time raster 512 device px (D3.4-A/D3.5), 780 restored on settle |
| 4 | `index.html`, `src/render.js` | gust badge `[24 Gust]` (`.unit` span removed); dynamic `aria-label="Gust {gust} mph"` |
| gates | `tests/render.test.js`, `tools/qa/stage5_check.py`, `tools/qa/live_smoke.py` | §4.2 closed list + new group `[20]` |

Items 2–4 + gates were delegated to OpenCode (Run A: two files; Run B: three gate files),
then re-verified in-house (diff review, `node --check`, probes). Three in-house fixes on top
of Run A (all single-file, `src/render.js`):

1. **`vEma` seeded at `V_HI`** at gesture start — an EMA seeded at 0 needs ~4 samples
   (~66 ms) to cross `V_HI`, letting one expensive paint through on every fast drag
   (measured: one 46–51 ms stall per flick).
2. **Sustained-gap EMA decay** — the EMA only sampled `pointermove`; when the finger stopped
   mid-drag it never decayed, so suspension never lifted and the map waited for the 1.2 s
   anti-freeze valve (blob at +1.26 s after motion stopped). Decay (delta 0, same α) fixes
   the catch-up paint.
3. **`animate:false` on the refit** — the resize path read `getZoom()` mid zoom-animation,
   yielding a stale floor after rotation.
4. **`target === cur` guard in the paint scheduler** — a clamped drag (or a drag returning to
   the shown frame) re-encoded the current frame under the drag raster class; the 6.2
   cache + overlay-dedupe made that a no-op, so the guard restores it explicitly (this is
   what keeps the clamped `hold` profile at zero encodes).

Two gate-rig corrections were approved at sign-off (2026-09-14, see §7):

- `[20.7]` gains a throwaway net-zero painting warm-up (`_s63_warmup`) — same convention as
  `[17]`/`scrub_bench`; G2 now reads steady state and the one-time cold first-drag cost is
  recorded in §3 (not gated). Bar tightened to `>33 ms == 0, p90 <= 20`.
- `tapeTx>=moves` → `tapeTx>=moves-1` in `stage5_check.py [17]` and `scrub_bench.py`
  (pre-down event writes nothing; mid-drag paint flushes are suspended by item 3).

## 1. Item 1 — water-mask cleansing

**Reproducibility baseline (proved before mutating):** re-running `python3 tools/export_tables.py`
on the 6.2 tree regenerated `public/tables.v1.bin` **bit-identical** to the shipped blob
sha256 `33aa6e521777360d16b00abf7d137b869674c60a4ac6ddd1f072080b1bc2a2e7` (613,320 B; 5.1 s).
The before/after deltas below are therefore mask-only effects.

**Mask receipt (`public/mask.v1.json`):**

| comp | cells | area km² | centroid (lat, lon) | depth ft (min/med/max) |
|---|---|---|---|---|
| keep | 52,738 | 527.38 | 46.2424, −93.6466 | 0.0 / 30.8 / 40.0 |
| drop | 345 | 3.45 | 46.3351, −93.8053 | 0.0 / 6.8 / 42.0 |
| drop | 322 | 3.22 | 46.2058, −93.8129 | 0.0 / 0.2 / 42.0 |
| drop | 317 | 3.17 | 46.3560, −93.7723 | 0.0 / 1.9 / 42.0 |
| drop | 169 | 1.69 | 46.1110, −93.7239 | 0.0 / 2.2 / 12.7 |
| drop | 104 | 1.04 | 46.3666, −93.8067 | 0.0 / 3.8 / 5.7 |

6 components in, 5 dropped (1,257 cells / 12.57 km² = 2.33 % of water cells). Keep-assertion
(≥ 50,000 cells) held. 4-connectivity (D1.1); identical result under 8-connectivity.
Naming (D1.5): centroids + areas + townships recorded (Hazelton / Roosevelt / Kathio);
no names asserted (web-verify deliberately skipped per D1.5 = cosmetic only).

**Byte-level diff (`tmp/s63_verify_after.py`, section-by-section):**

| section | changed | bytes |
|---|---|---|
| depth | 1,257 cells water→LAND | 2,514 |
| fetch | 2,594 u16 entries → LAND_U16 | 5,188 |
| path | 2,024 u8 entries → 0 | 2,024 |
| **total** | | **9,726 B (1.59 %)** |
| **file size** | | **613,320 B (0 delta — assertion holds)** |

**Deviation vs §1.3's prediction (2,242 / 1,786, ≈ 8,784 B):** the prediction charged only the
144 sampling points *inside* the bodies. Measured 182 fetch points: **144** start inside a
dropped body + **38** start on land whose ray ran *into* the then-water body (a ray's start
cell is never bounds-checked, only its first step). All 38 sit exactly 1 cell (Chebyshev)
from a dropped cell. **Kept-lake points changed: 0** — the §1.3 invariance claim holds, so
the Mille Lacs wave field is bit-identical (P2).

**meta.v1.json:** `depth_ft` [0.0, 42.0] → **[0.0, 40.0]**; `fetchEff_decam` [2, 2335] and
`pathEff_ft` [0, 34] unchanged.

**Golden fixtures:** worst |Δ| vs `golden.json` = 4.8e-5, identical before/after. §6.3:
fixtures are DEM point queries inside Mille Lacs — none embeds satellite cells →
**no regeneration** (recorded per §6.3).

**Runtime (P4/P5; crafted 25/12/38 series, `?frame=40`):** `p10Ft` 1.069 → **1.129** (up);
`hsFt` 2.871 = 2.871; peak card identical. 5 satellite centroids: tap `true`→**`false`**,
raster alpha 255→**0**, flash `land — no wave data here`.

## 2. Item 2 — map containment & rubber-band

Harness group `[20.3]–[20.6]` (authoritative, both viewports):

- **C1** `minZoom == zoom` at fit: **10.4** @390×844, **10.3** @360×800; box contains lakeBounds;
  viscosity 0.75.
- **C2** lake north edge y = **244.0 → 244.0 px** @390 (234.0 → 234.0 @360) across a synthetic
  vertical drag — the 29 px header-clearance contract holds (≥ 96 px bar).
- **C3** max mid-drag rubber-band overshoot 164.2 px → settles to **0.42 px** past the clamp
  (≤ 0.5 px, ≤ 5 px bars) within 120 ms of release.
- **C4** `zoomOut()` ×3 stops at exactly the fit floor **10.4**; lake width ratio 1.000 (≥ 0.95).
- **C5** `[19]` full group green (see §5) — 72 px header ceiling, corners, continuous scrub.

## 3. Item 3 — 60 fps scrub

**Direct probe (`tmp/s63_dragraster_probe.py`):** rest 780 → tap 780 (no flip) → slow drag
**512** → settle **780**; encodes: slow drag 7 (throttled), fast flick **0 during the
gesture**, 1 settle encode.

**Profiles (`[20.7]`, 390×844 DSF2, crafted series, sequential flick→slow→hold on one page;
slow pacing set to the §3.1 achieved velocity ≈ 0.13 px/ms):**

| gate | bar | 6.2 baseline (s63_attrib) | 6.3 measured | verdict |
|---|---|---|---|---|
| G1 flick | >33 ms == 0, p90 ≤ 20 | 7 / p90 41.4 | **0 / p90 16.8–16.9, max 16.9** | ✅ |
| G2 slow (warmed) | >33 ms == 0, p90 ≤ 20 | 22 / p90 46.1 | **0 / p90 16.9, max 24.1**, 8 encodes | ✅ |
| G3 hold | p90 ≤ 17, max ≤ 20 | p90 16.8 | **p90 16.8–16.9, max 16.9–17.1, 0 encodes** | ✅ |
| G4 tape advance | ≥ 0.95 advancing, matrix form | — | **1.000 / true** | ✅ |

**Cold first-drag profile (expected one-time startup cost, recorded per sign-off §7-A):**
on a cold session the first drag pays ~143 ms once (first 512-class build: one-time land-frac
gather + JIT) + two ~40 ms frames (JIT warm-up); encodes 4+ of that same drag are ≤ 33 ms
(timeline probe `tmp/s63_profile_timeline.py`). After the rig's warm-up pass, the measured
slow drag is **0 frames > 33 ms, p90 16.9, max 24.1** (8 throttled encodes) — the steady
state from the second drag onward. Flagged for on-device confirmation (O2).

**G5 scrub_bench:** all checks PASS on all three cases (mouse ×2, cdp-touch): median **16.6 ms**
(≤ 25 ✓), p90 16.8–17.0 (≤ 30 ✓), max 17.1–33.4 (≤ 100 ✓), swaps **0** (≤ 12 ✓), long ≤ 50 ✓,
`index_exact` ✓ (idx 42 → 42, pill 10:30 AM), `runway_24h` 176/206 ✓, `tapeTx>=moves-1`
30/31 and 30/30 ✓ (1:1 tracking; see §7-B).

**G6 settle correctness:** `[19]` continuous-scrub + Home-settle gates green; released frame ==
the throttled target index (`expectedIdx`) — harness `[16]/[17] final` lines: idx 42 == 42.

## 4. Item 4 — header gust trim

- Markup `index.html:288`: `<span id="pill-gust" … aria-label="Gust 24 mph"><span id="gust">24</span><span id="gust-u">Gust</span></span>`
  — `#pill-gust .unit` gone; `#lake`/`#mph` untouched (tier tint + white unit kept).
- `src/render.js:1202`: `pillGustEl.setAttribute('aria-label', 'Gust ' + pills.gust + ' mph')`.
- §4.2 closed list applied: `tests/render.test.js` (negative: `#pill-gust` must not contain
  `class="unit"`, inner spans exactly `['gust','gust-u']`, `[24 Gust]` labels), `stage5_check.py`
  ([19.4]/[19.5] gust clauses), `live_smoke.py` (DOM absence + deployed-bytes absence + row text).
- **H1** header 72.00 px, ink ≤ available at all four viewport/viewport-profile combos —
  `[19.1]–[19.3]` green (slack 168.8–213.3 px). **H2** `[17 mph]` badge unchanged — `[19.5]/[19.6]`
  (lake unit white, contrast ≥ 5.11:1). **H3** rendered `[24 Gust]` — `[19.4]`, plus live-smoke
  run post-deploy.

## 5. Verification matrix (§6.2)

| suite | result |
|---|---|
| `node tests/*.test.js` (4 files) | **4/4 ALL TESTS PASSED** (harness `[12]`) |
| `stage5_check.py` `[19]` (6.2 regression) | **ok — all gates ok=True** |
| `[20]` | **all gates ok=True** — `[20.1]`–`[20.6]` ✅, `[20.7a]` 0 / p90 16.8 ✅, `[20.7b]` 0 / p90 16.9 / max 24.1 ✅ (warmed), `[20.7c]` 0 / 17.1 ✅, `[20.7d]` advance 1.000 ✅ |
| `stage5_check.py` full | **26 ok, 0 FAIL** — `[17]` ✅, `[19]` ✅, suites 4/4, page errors 0 (`tmp/s63-harness-ship.log`) |
| `scrub_bench.py` | **all PASS** ×3 — median 16.6, swaps 0, `tapeTx>=moves-1` ✓ |
| `live_smoke.py` | pending deploy (run post-push) |

`[9]` playback perf ok (canvas 780, frameMs avg 44.2 — path untouched by 6.3);
`[10]/[11]` radar smoothing unchanged; `[13]` lazy 7d ok; `[14]` live seam pass.

## 6. Rollback

- Item 1: `git checkout 87a52cb -- public/tables.v1.bin public/meta.v1.json` (+ delete
  `public/mask.v1.json`), or re-run the exporter from the old tree.
- Items 2–4: revert the items 2–4 commit (map init/fit; CSS + scheduler; markup + aria) —
  each item is separately reversible (§0).
- Full: reset to `87a52cb`.

## 7. Sign-off decisions (resolved 2026-09-14)

**A. `[20.7b]` G2 — ✅ rig warm-up (option 1).** `[20.7]` runs a throwaway net-zero painting
warm-up (`_s63_warmup`: paced 6 px steps forward and back, returning to the exact start index,
so the flick→slow→hold state chain is unchanged). G2's bar is tightened to **>33 ms == 0,
p90 ≤ 20** (matching G1/G3). Measured: **0 / p90 16.9 / max 24.1**, 8 encodes. The 72 ms drag
throttle stays locked (no D3.4-B). Cold first-drag cost recorded in §3 as an expected one-time
startup profile (on-device confirmation pending, O2).

**B. `[17]` + `scrub_bench.tapeTx>=moves` — ✅ instrument correction applied.** Both files now
read `tx >= moves - 1` with in-file comments: the mouse driver's pre-down positioning move
never writes (cdp-touch, moves=30, is 30/30 exactly); the old bar only passed via mid-drag
paint-flush writes (6.2: 30 + 11 = 41; Run B tree: 30 + 1), which item 3 suspends by design
(G1 = 0 encodes on fast drags). The tape still tracks every drag step 1:1; a starving tape
(~1 write per rAF) still fails loudly. Re-run: `[17]` ok, bench all PASS.

**C. Ship:** tag `stage-6.3-shipped` + Pages deploy + live smoke (this commit).
