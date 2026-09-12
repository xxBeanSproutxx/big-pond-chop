# STAGE 5K — RECEIPTS (UI revision: ribbon re-docked, translucent calm water, one day header, strip deleted)

Branch `stage5k` (off the rejected `stage5j` tip; `main` untouched). **Not merged, not tagged, not pushed.**

Trigger — Reid rejected 5J's visual direction (2026-09-12):

> "Revert the Floating Legend Card & Bottom Text Strip … Restore the wave height color scale ribbon
> docked flush to the base of #deck. Do NOT float it inside the map canvas where it covers bays and
> collides with attribution. Remove the bottom text row … Fix Calm Lake Transparency: do NOT render
> calm water as an opaque dark block … Fix the 24h Day Header Stutter: remove the 6-hour repeating
> day label hack … Keep the 16.4ms decoupled scrub performance from 5H intact."

Spec `docs/BUILD-SPEC-STAGE5K.md`. Worker: OpenCode. Gates + visual verification re-run by the
orchestrator on the final tree.

## What changed

1. **Ribbon re-docked to the deck base (5G layout).** `#ramp-bar` + `#ramp-ticks` are back inside
   `#deck` as `.deck-ramp`; the 5J `#legend-card` (element + CSS) and the `#wind-strip` row
   (element, CSS, `role=status`/`aria-live`, the `ui.windStrip()` helper and its write inside
   `updateScrubUi()`) are **deleted**. `src/render.js` paints `#ramp-bar` from `ui.rampGradient()`
   (single writer; the old `index.html` inline snippet stays gone). Deck is **68 px** again
   (48 track + 20 ribbon) and the ribbon is flush at the deck base: measured delta **0.0 px**.
2. **Calm water is translucent, not an opaque block.** `HS_STOPS[0]` `#0f2744` → **`#2a5885`** and
   `CALM_RGBA` → **`[42, 88, 133, 115]`** (alpha 0.45). Land stays exactly transparent (the land
   fraction still separates land from calm water); the ramp above 0 ft stays opaque.
   **Measured readability** (forced-calm run, phone viewport, overlay on vs off on the same frame):
   lake median `rgb(205,207,207)` → **`rgb(152,168,183)`**, mean per-channel |Δ| **38.5**,
   contrast (luminance σ) retained **68 %**, **structure correlation 1.00** — the basin texture,
   depth cues and the OSM names (`Mille Lacs Lake`, `Mille Lacs Reservation`, bay labels) all read
   through the tint.
3. **24h day header stutter removed.** The 6-hour repeat loop is deleted. Exactly **one**
   `.day-head` per day block: on the wide 24h block it is **pinned at the day start**
   (`left:6px`, no transform — measured left offset **6.0 px**), and the tape carries a single
   `Saturday 12`. 7d is unchanged (one centred header per 190 px block). Ticks keep the 5J
   improvements: h=0 left-anchored `12`, the 3-hourly set, and the **last block's** right-anchored
   `12` over the date seam — 9 ticks in 24h (`12,03,06,09,12,03,06,09,12`), 8 per 7d block, none clipped.
4. **5H scrub path untouched.** `scrubUiTo()`, `scheduleMapPaint()`, `shouldPaintMap()`, `endScrub()`
   and the `paintGen`/`inFlightEncode` guards are byte-identical; the only edit on that path is the
   removal of the wind-strip write (one fewer write per frame).

## Gate receipts (orchestrator re-run on the final tree)

- Node suites: `parity / wind / render / ui` → **4 × exit 0**.
- `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → **0 lines**.
- `tools/qa/stage5_check.py` → **`SUMMARY: 23 ok, 1 FAIL`**; the only FAIL is the **pre-existing**
  `[14] live seam` (`dSpeed 1.80 dDir 7.00`, unrelated to 5K). Key lines:
  - `[7a] ramp location ok ramp in-deck=True in-map=False legend-card-present=False stops=['0','1','2','3.5','4.5','6+'] gradient-six=True`
  - `[15] deck geometry ok deck-ramp-bottom=844.0 deck-bottom=844.0` (delta 0.0), `deckH=68.0`
  - `[16] tape architecture ok 24h tape=550.0/window=374.0 runway=176.0 | 7d blocks=7 subs=[8×7]`
  - `[17] scrub decoupling ok moves=31 tx>=moves=True swaps=11<=12=True long-max=0<=50=True idx=42 expected=42=True`
  - `[18] timeline labels (5K) ok one-head=True pinned=True no-repeat=True ticks=9=True all-inside=True | 7d counts=[8×7] min-12-gap=85.6>=20=True`
  - `[10.1] land bleed ok land_alpha=[0,0,0,0] mid_lake_alpha=[255,255]`
- `tools/qa/live_smoke.py --url http://127.0.0.1:8791/index.html` → **10 ok / 0 FAIL**.
- `tools/qa/scrub_bench.py` (the 16.4 ms ask):

  ```
  stage5k  390x844@2  mouse      lat med/max = 16.47 / 63.00   longtasks=[]
  stage5k  360x800@2  mouse      lat med/max = 16.59 / 53.62   longtasks=[]
  stage5k  360x800@2  cdp-touch  lat med/max = 17.72 / 66.79   longtasks=[]
  VERDICT: 24/24 PASS
  ```
- Independent orchestrator verifier (phone viewport, calm data injected at the network layer,
  readability measured against the same frame with the overlay hidden): **12 ok / 0 FAIL**.

## Visual receipts

`tmp/5k-shots/5k-{calm,calm-baseline,24h-start,24h-evening,7d}.png` (gitignored; delivered in chat).

## Honest notes

- **Alpha math:** the spec's 0.45 is baked per-pixel, and the Leaflet overlay adds
  `OVERLAY_OPACITY 0.72`, so the calm tint lands at ≈**0.32 effective** over the basemap. That is
  why the basemap dominates and everything under it stays readable — if a stronger tint is wanted,
  the one-line knob is `CALM_RGBA` alpha 115 → ~160 (a true 0.45 on screen).
- **One-day-header consequence:** with a single header pinned at the day's start, scrubbing the
  evening (after ~idx 40) shows ticks but no date — the midnight `12` at the tape's right edge
  carries the boundary. A sticky header that stays on screen is a one-line-per-frame change
  (no perf cost) if Reid wants it.
- **0 ft floor edge:** at exactly 0 ft the calm tint is translucent; at 0.01 ft the ramp is opaque
  `#2a5885` onward, so there is a small alpha step right at the floor (hue is continuous).
- `docs/STAGE-5J-RECEIPTS.md` is kept as history with a superseded banner — the 5J branch is not
  merged and its visual direction is dead.

## Status

- Branch `stage5k` (3 commits: spec, product, gates). `main` still at 5I; nothing deployed.
- Waiting on Reid's screenshot review before any merge/Pages push.
