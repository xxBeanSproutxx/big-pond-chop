# STAGE 5I RECEIPTS — wind badge flow-vector flip + copy

Status: **SHIPPED** (2026-09-12). Merge `7407725` (`--no-ff`, `46d92cc..7407725`).
Rollback: `git revert -m 1 7407725` or tag `pre-stage5i` (`46d92cc`). Earlier rollback tags: `pre-stage5h` (`ed377a4`), `pre-stage5g` (`809d84d`), `pre-stage5f` (`be29ba2`), `pre-stage5` (`9ec0f97`).

## What changed (7 files, +472 / −37)

- `src/ui.js` — `compass()` now returns `fromDeg` (source bearing) and `arrowDeg = (deg + 180) % 360` (downwind flow vector); calm / non-finite → all-null fields.
- `src/render.js` — badge text `From <sector> <deg>°`; aria `Wind from <sector> at <from> degrees, blowing toward <arrow> degrees`.
- `index.html` — static placeholder `From NW 315°` + matching aria.
- `tests/ui.test.js` — block [7] rewritten to the `(normalizeDeg(b) + 180) % 360` contract (fromDeg in every expectation).
- `tools/qa/stage5_check.py` — `check_compass()` validates: text number = `round(grid + gamma)` (±0.5), arrow = `(grid + gamma + 180)` (±1.5°), new aria regex; detail label `(downwind)`.
- `tools/qa/wind_arrow_sweep.py` (**NEW**) — re-runnable 96-frame sweep over the 24 h horizon; `--url` points it at the deployed site; findings-style output, always exits 0.
- `docs/BUILD-SPEC-STAGE5I.md` (**NEW**) — dispatch spec.

## Why — audit evidence (`tmp/audit-wind-arrow/report.md`, run 2026-09-12T04:27:45Z)

Pre-change 96-frame sweep (headless Chromium, 390×844): the arrow **tracked the true bearing exactly** (max |Δ| 0.0000°), 38 distinct angles / 403° total travel — not stuck, not clamped, 0 plateaus while bearings moved; updated live during drag and playback. The only finding was **convention**: it pointed INTO the wind (at the source). γ −0.474° is applied in the physics path (wind→fetch blending); the badge is intentionally **TRUE**-referenced (screen-correct on a true-north-up Mercator map) — grid-referencing the arrow would make it 0.474° wrong, ≈0.07 px at the 18 px glyph. Copy probe: `From NW 315°` = 129.5 px vs 98.2 px before, fully inside the map and clear of the zoom control at 360 & 390 px.

## Gate receipts

- Node suites: parity **10 ok**, render **32 ok**, ui **27 ok**, wind **36 ok** → 105 ok; parity byte-identical (**physics untouched**).
- `git diff pre-stage5i -- src/wind.js src/wave-math.js public/` → **0 lines**.
- Harness `stage5_check.py` (idle run): **22 ok / 1 FAIL** —
  `[6] compass badge ok text='From NW 315°' from=315.00° arrow=135.00° expected=135.00° (downwind) delta=0.00 top-right=True clear-zoom=True`.
- `[14] live seam` FAIL is **pre-existing and live-data-driven**: `SEAM 2026-09-14 frame=288 dSpeed=1.40 dDir=10.00` — reproduced **identically** on a `pre-stage5i` worktree in the same session (both trees, same numbers). Not caused by 5I; candidate for its own look at the +48 h seam.
- `[17] scrub decoupling`: passed on the idle run (`long-max=50<=50`); one contended run measured 51 ms against the ≤50 gate — untouched code path, noted as marginal headroom (5H.1 open item).
- Local sweep: **96/96 ok, 0 FAIL**.
- Live sweep on the deployed site: **96/96 ok, 0 FAIL** (`--url https://xxbeansproutxx.github.io/big-pond-chop/`).

## Deployment

- Push `46d92cc..7407725`; Pages build ≈36 s; **deployed-asset verification by content fetch** (the Pages `builds/latest` record lags — content is the authority): `src/ui.js` serves `fromDeg` + `(deg + 180) % 360` + `DOWNWIND`; `index.html` serves `From NW 315°` and `blowing toward SE at 135 degrees`.
- Live smoke: **10 ok / 0 FAIL** — deck two-row, pill permanent, reticle centred, play pinned, tape wired, ribbon flush, day headers, 7 d live, back to 24 h, no page errors.
