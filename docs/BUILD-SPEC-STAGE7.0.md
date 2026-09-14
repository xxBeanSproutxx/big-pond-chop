# BUILD-SPEC — STAGE 7.0: PWA installability (manifest + service worker + icons)

Owner: Reid · Orchestrator: Hermes · Implementer: OpenCode
Follow the ponytail ruleset (laziest correct implementation).

## Goal

Make https://xxbeansproutxx.github.io/big-pond-chop/ installable to a mobile home screen
(Chrome/Android WebAPK + iOS standalone), with a minimal service worker that precaches the
static shell, never caches weather/tile traffic, and never serves stale app code.

Wave physics, the timeline deck, and map interactions must not change in any way.

## D-1 (DEVIATION FROM REQUEST — read this first)

The request asked for `public/manifest.webmanifest` and `public/sw.js`. Those paths are
**broken on GitHub Pages branch-root hosting**, so they are placed at the **repo root**
next to `index.html` instead. Icons stay in `public/` exactly as requested.

Why the requested paths cannot work:
- The site is served at `https://<owner>.github.io/big-pond-chop/` from `main` branch root,
  so the app root is the repo root. `index.html` lives at the repo root.
- `start_url` and `scope` resolve **relative to the manifest's own URL**, not the page. A
  manifest at `public/manifest.webmanifest` resolves `"./"` to `/big-pond-chop/public/`,
  which is not the app → the installed app opens a 404 and the install criteria fail.
- A service worker's scope is capped at its own directory (GitHub Pages cannot send a
  `Service-Worker-Allowed` header). `public/sw.js` could therefore never control
  `/big-pond-chop/index.html` or serve the shell — the SW would be decorative.

Everything else in the request is honored verbatim, including `start_url: "./"`,
`scope: "./"`, and relative icon paths.

## Files allowed to touch

- NEW  `manifest.webmanifest`            (repo root)
- NEW  `sw.js`                           (repo root)
- NEW  `public/icon-192.png`             (generated, 192×192)
- NEW  `public/icon-512.png`             (generated, 512×512)
- NEW  `tools/make_pwa_icons.py`         (icon generator, re-runnable)
- NEW  `tools/qa/pwa_check.py`           (headless gate harness)
- EDIT `index.html`                      (HEAD additions + one inline registration script ONLY)
- NEW  `docs/STAGE-7.0-RECEIPTS.md`      (filled in from measured output)

## Out of scope (do not touch)

- `src/**` — wave physics, render, wind, ui. Zero edits. No refactors.
- Anything about the deck, tape, scrub, pan physics, fitLake, badges, ramp, attribution.
- `tools/qa/stage5_check.py`, `scrub_bench.py`, `live_smoke.py` — leave as-is (no new gate
  group; PWA gates live in the new harness so the 6.4 gates cannot regress).
- Do not add an install button / install UI / A2HS banner. Not requested.
- Do not add offline-first data caching, background sync, push, or a fetch-retry layer.

---

## 1. `manifest.webmanifest` (repo root)

Exact values:

```json
{
  "name": "Big Pond Chop",
  "short_name": "BigPondChop",
  "description": "Live wave and wind forecast for Mille Lacs Lake.",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#0f172a",
  "orientation": "portrait-primary",
  "prefer_related_applications": false,
  "icons": [
    { "src": "public/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },
    { "src": "public/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
```

`prefer_related_applications: false` is required for Chrome to consider a WebAPK.
Icon `src` is relative to the manifest's location (repo root) → `public/icon-192.png` is
exactly right from there. All icon URLs must resolve 200 under the subpath.

## 2. Icons — `tools/make_pwa_icons.py`

Generate both PNGs from the existing wave favicon asset `public/favicon.svg`
(cyan `#06b6d4` + amber `#f59e0b` waves on `#0d1b2a`), reusing that exact wave geometry.

- Compose one SVG at `viewBox="0 0 512 512"`: full-bleed background `#0f172a`, then the two
  favicon wave paths scaled/translated to sit **centered inside the 80 % safe zone** (maskable
  crop on Android clips the outer 10 % per edge — the glyph must not touch the edge).
- Render with `cairosvg` at 512 and 192 (no other size), write `public/icon-512.png` and
  `public/icon-192.png`. Script must be re-runnable and deterministic.
- Verify after writing: PNG dimensions exact, mode RGBA/RGB, and a pixel probe proving the
  wave strokes are present inside the safe zone and the corners are `#0f172a`.

## 3. `sw.js` (repo root) — lean + robust

```js
const CACHE_NAME = 'bpc-cache-v1';   // bump on every future deploy
```

**Precache at install** (`caches.open(CACHE_NAME).then(c => c.addAll(SHELL))`), all relative
URLs resolving against the SW's location (repo root = app root):

```
'./', './index.html',
'./src/tables.js', './src/wave-math.js', './src/wind.js', './src/ui.js', './src/render.js',
'./public/meta.v1.json', './public/mask.v1.json', './public/spots.v1.json',
'./public/warp.v1.json', './public/tables.v1.bin',
'./public/favicon.svg', './public/icon-192.png', './public/icon-512.png',
'./manifest.webmanifest'
```

E-1 (extension): the five `src/*.js` modules are the shell — `index.html` loads them via
`fetch()` at boot, so without them the installed app opens to "wind unavailable".

`cache.addAll` fails silently on a single 404 → every URL above must be proven 200 first.

**Install:** precache, then `self.skipWaiting()`.
**Activate:** delete every cache key !== `CACHE_NAME`, then `self.clients.claim()`.

**Fetch strategy matrix** (E-2 — this is the anti-stale contract):

| Request | Strategy |
|---|---|
| non-GET | passthrough (`return`, no `respondWith`) |
| navigation / `destination === 'document'` | network-first with `fetch(req, { cache: 'no-store' })`, fall back to cache (offline) |
| same-origin `src/*.js` | network-first with `{ cache: 'no-store' }` + `cache.put` on success, fall back to cache |
| same-origin versioned shell (`public/*.v1.*`, `tables.v1.bin`, icons, `favicon.svg`, `manifest.webmanifest`) | cache-first, fill cache on miss |
| `api.open-meteo.com` | **explicit passthrough — never cached**, always live network |
| any other cross-origin (unpkg Leaflet CSS/JS, `tile.openstreetmap.org`) | passthrough, never cached |

Rationale for the split: GitHub Pages serves HTML with `max-age=600`, so a network-first
document that honors the HTTP cache can serve stale pages for 10 minutes (`cache: 'no-store'`
is the proven fix). `src/*.js` has no version in its filename, so cache-first would ship
stale code forever — network-first keeps code and document in lockstep. The `*.v1.*` data
files are immutable per version, so cache-first is safe and saves ~650 KB per open.

Keep the file small and dependency-free. No workbox, no build step, no sw registration
framework.

## 4. `index.html` — HEAD + one script (only these edits)

HEAD adds (relative paths only — this must work under `/big-pond-chop/`):

```html
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0f172a">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BigPondChop">
<link rel="apple-touch-icon" href="public/icon-192.png">
```

`viewport-fit=cover` is already present — do not change the viewport meta.

Then a compact inline registration script, before `</body>` (after the existing app script):

```js
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('sw.js', { updateViaCache: 'none' }).catch(function () {});
  });
}
```

No console noise on failure (console errors are a gate). Do not touch any element, style,
script, or module path that already exists.

## 5. `tools/qa/pwa_check.py` — the gates

Servable harness, mirroring the existing harness style (prints `ok`/`FAIL` + measured
value per check, always runs to completion, exit 0, final `SUMMARY` line with `N ok / M FAIL`).

It must rehearse the **subpath** locally before touching production:
`mkdir -p /tmp/bpc-pages-root && ln -sfn <repo> /tmp/bpc-pages-root/big-pond-chop`, serve
`/tmp/bpc-pages-root` (custom `http.server` handler: `.webmanifest`/`.json` → `application/manifest+json`,
no-cache headers), and drive `http://127.0.0.1:PORT/big-pond-chop/index.html`.

Checks (numbered, all against the subpath origin unless noted):

1. Every precache URL returns 200 (list any non-200 with its code).
2. Manifest: HTTP 200, `Content-Type` contains `manifest+json`, body parses as JSON.
3. Manifest fields exactly equal the spec above (each field its own line/assert).
4. URL math: `urljoin(manifest_url, start_url)` **== the app root URL** (`/big-pond-chop/`)
   and `urljoin(manifest_url, scope)` == app root. Equality, not "didn't 404".
5. Every manifest icon URL resolves 200 with `image/png`; PNG header dimensions match the
   declared `sizes`.
6. Fresh page load of the subpath URL: zero `pageerror`, zero `console.error`, and the only
   permitted failed request is `/favicon.ico`.
7. SW registers and reaches `activated`; `registration.scope` == app root URL exactly.
8. After one reload, `navigator.serviceWorker.controller` is non-null (the SW really controls
   the page) and the app booted (existing app markers present, e.g. `#map` and the tape deck).
9. CDP: `Page.getAppManifest` returns the manifest with no parse errors, and
   `Page.getInstallabilityErrors` returns an empty list (Chromium would offer install).
   Print the raw error array when non-empty so it can be reported verbatim.
10. Offline smoke: with the SW controlling, set the context offline and reload → the shell
    still renders from cache (document title + `#map` present). Then restore the network.
11. Regression guard: `git status --porcelain src/` is empty (no app-code edits) and the
    four Node suites still pass.

Add `--live` to run checks 1-6 + 9 against
`https://xxbeansproutxx.github.io/big-pond-chop/` after the push, plus a cache-busted curl of
the deployed `manifest.webmanifest` and `sw.js` for a marker string that exists only in the
new revision (e.g. `bpc-cache-v1`).

## 6. Gate commands (run all, paste real output into receipts)

```bash
node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py     # must stay 27 ok / 0 FAIL
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py      # must stay 24/24 PASS
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/pwa_check.py        # new
```

## 7. `docs/STAGE-7.0-RECEIPTS.md`

Sections: §0 deviation + extensions (D-1, E-1, E-2), §1 files added/changed with line counts,
§2 the manifest/SW/icon facts, §3 the gate table with real measured numbers, §4 live deploy
evidence (HTTP codes, served Content-Type, CDP installability result), §5 residuals + open
items (device-side install still to be confirmed by Reid, future `CACHE_NAME` bump rule).

## Done-when

- `pwa_check.py` reports 0 FAIL on the local subpath rehearsal, all 11 checks present.
- Existing gates unchanged: stage5_check 27 ok / 0 FAIL, scrub_bench 24/24 PASS, 4/4 Node suites.
- `src/` untouched (`git status --porcelain src/` empty).
- Receipts written with real output only — no invented numbers.
