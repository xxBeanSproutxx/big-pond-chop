#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 5 re-runnable QA harness for big-pond-chop.

Usage (from anywhere):
    /home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py

Serves the repo root with `python -m http.server` and drives the app with
Playwright/Chromium at 390x844 (DPR 2) and 360x800. Every check prints
`ok`/`FAIL` with the measured number. It also prints a before/after upscale
table against a read-only worktree of the `pre-stage4` tag (the stage-1-3
baseline), the tails of the four Node suites, the live +48 h seam delta via
tools/qa/seam_check.js, saves screenshots to /tmp/bpc-s5-*.png, and ends with a
summary. Failures are *findings*: the harness always runs every check to
completion and exits 0 so it can be re-run without a one-off data snapshot.
"""

import json
import math
import re
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    print("playwright is required: run with /home/reid/.hermes/hermes-agent/venv/bin/python")
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[2]
PRE_TAG = "pre-stage4"
PRE_WT = Path("/tmp/bpc-pre4")
SHOTS = Path("/tmp")
CHICAGO = ZoneInfo("America/Chicago")
DEFAULT_HINT = "tap the lake for a local readout"
LAND_FLASH = "land — no wave data here"

RESULTS = []  # (num, name, ok, detail)

# Counter + map-capture instrumentation. add_init_script takes a *script body*.
INIT_SCRIPT = r"""
(function () {
  window.__bpcCreated = 0; window.__bpcRevoked = 0;
  try {
    var _c = URL.createObjectURL.bind(URL), _r = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = function (b) { window.__bpcCreated++; return _c(b); };
    URL.revokeObjectURL = function (u) { window.__bpcRevoked++; return _r(u); };
  } catch (e) {}
  try {
    var _L;
    Object.defineProperty(window, 'L', {
      configurable: true,
      get: function () { return _L; },
      set: function (v) {
        _L = v;
        if (v && v.map && !v.__bpcPatched) {
          v.__bpcPatched = true;
          var orig = v.map;
          v.map = function () { var m = orig.apply(this, arguments); window.__bpcMap = m; return m; };
        }
      }
    });
  } catch (e) {}
})();
"""

OVERLAY_OK = ("() => { var i = document.querySelector('.leaflet-image-layer'); "
              "return !!i && i.naturalWidth > 0; }")
BOOT_HIDDEN = ("() => { var b = document.getElementById('boot'); "
               "return !!b && b.classList.contains('hidden'); }")


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def record(num, name, ok, detail):
    RESULTS.append((num, name, bool(ok), detail))
    print("[%s] %-22s %s %s" % (num, name, "ok  " if ok else "FAIL", detail), flush=True)


def safe(num, name, fn, *args):
    """Run a check, turning any crash into a FAIL finding instead of aborting."""
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001 - a QA harness records, never aborts
        record(num, name, False, "EXCEPTION %s: %s" % (type(exc).__name__, exc))
        return None


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def serve(port, cwd):
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_http(url, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    return False


def new_page(pw, width=390, height=844):
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": width, "height": height},
                              device_scale_factor=2)
    ctx.add_init_script(INIT_SCRIPT)
    page = ctx.new_page()
    return browser, page


def load_app(page, url):
    page.goto(url, wait_until="domcontentloaded")


def ll_bounds(warp):
    return [[warp["corners"]["se"][1], warp["corners"]["nw"][0]],
            [warp["corners"]["nw"][1], warp["corners"]["se"][0]]]


def format_chicago(iso_local):
    dt = datetime.fromisoformat(iso_local).replace(tzinfo=CHICAGO)
    return dt.strftime("%-I:%M %p %Z")


def tier_of(max_hs, roller, hl):
    finite = lambda v: isinstance(v, float) and math.isfinite(v)
    at = lambda v, t: finite(float(v)) and float(v) >= t
    if at(max_hs, 5.0) or at(roller, 4.0) or at(hl, 0.055):
        return "red", "Dangerous · Stay Home"
    if at(max_hs, 3.5) or at(roller, 2.5):
        return "amber", "Heavy Rollers"
    if at(max_hs, 2.0) or at(roller, 1.5):
        return "yellow", "Walleye Chop"
    return "green", "Fishable · Light Chop"


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
def check_boot(page, port):
    load_app(page, "http://127.0.0.1:%d/index.html" % port)
    boot_before = page.is_visible("#boot")
    page.wait_for_function(BOOT_HIDDEN, timeout=90000)
    page.wait_for_function(OVERLAY_OK, timeout=90000)
    info = page.evaluate(
        "() => { var i = document.querySelector('.leaflet-image-layer');"
        " return { src: i.src || '', nw: i.naturalWidth, nh: i.naturalHeight }; }")
    ok = bool(boot_before) and info["src"].startswith("blob:") and info["nw"] > 0
    record(1, "boot", ok,
           "visible_before=%s hidden_after=True overlay_src=%s... naturalWidth=%dx%d"
           % (boot_before, info["src"][:12], info["nw"], info["nh"]))
    return info


def check_frame_base(page):
    max_v = page.get_attribute("#track", "aria-valuemax")
    step = page.evaluate("document.body.dataset.stepMin")
    page.click("#play")
    page.wait_for_timeout(120)  # let the play-width regather settle before sampling ticks
    page.evaluate(
        "() => { window.__s4hours = [];"
        " new MutationObserver(() => { var h = document.body.dataset.hour;"
        "   if (h) window.__s4hours.push(h); })"
        " .observe(document.body, { attributes: true, attributeFilter: ['data-hour'] }); }")
    page.wait_for_function("window.__s4hours.length >= 10", timeout=40000)
    hours = page.evaluate("window.__s4hours.slice()")
    page.click("#play")
    page.wait_for_timeout(250)
    distinct = len(hours) == len(set(hours))
    minutes_15 = all(int(h[14:16]) % 15 == 0 for h in hours)
    ok = max_v == "95" and step == "15" and distinct and minutes_15
    record(2, "frame base", ok,
           "track.aria-valuemax=%s data-step-min=%s ticks=%d distinct=%s minutes%%15=%s"
           % (max_v, step, len(hours), distinct, minutes_15))
    print("        series: %s" % hours)
    return hours


def check_horizon_ceiling(page):
    """5D: the frame ceiling tracks the horizon (24 h = 96 frames, 7 day = 672)."""
    page.click("#h-7d")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '671'",
        timeout=60000)
    max7 = page.get_attribute("#track", "aria-valuemax")
    p24_when7 = page.get_attribute("#h-24h", "aria-pressed")
    p7_when7 = page.get_attribute("#h-7d", "aria-pressed")
    page.click("#h-24h")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
        timeout=60000)
    max24 = page.get_attribute("#track", "aria-valuemax")
    p24_when24 = page.get_attribute("#h-24h", "aria-pressed")
    p7_when24 = page.get_attribute("#h-7d", "aria-pressed")
    ok = (max7 == "671" and max24 == "95" and
          p7_when7 == "true" and p24_when7 == "false" and
          p24_when24 == "true" and p7_when24 == "false")
    record("2b", "horizon ceiling", ok,
           "7d max=%s pressed 7d/24h=%s/%s | 24h max=%s pressed 24h/7d=%s/%s"
           % (max7, p7_when7, p24_when7, max24, p24_when24, p7_when24))


def check_lazy_7d(page):
    """5A/5D: widening to 7d must build frames on demand, not eagerly evaluate the series."""
    page.click("#h-7d")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '671' &&"
        " document.getElementById('track').getAttribute('aria-valuenow') !== null",
        timeout=60000)
    r1 = float(page.evaluate("parseFloat(document.body.dataset.precomputeMs)"))
    page.wait_for_timeout(2500)  # idle: paused, no interaction, no play tick
    r2 = float(page.evaluate("parseFloat(document.body.dataset.precomputeMs)"))
    delta = r2 - r1
    ok = delta <= 10.0 and r1 < 500.0
    record(13, "lazy 7d compute", ok,
           "precomputeMs first=%.1f idle=%.1f idle_delta=%.1f (gate <=10, first<500)"
           % (r1, r2, delta))
    page.click("#h-24h")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
        timeout=60000)


def _header_metrics(page):
    return page.evaluate(
        "() => { var h = document.querySelector('header');"
        " return { c: h.clientHeight, s: h.scrollHeight }; }")


def _sweep(page, names):
    return page.evaluate(
        """(names) => {
             var el = document.getElementById('verdict-peak');
             var orig = el.textContent, widest = 0, bad = [];
             var worst = { name: '', over: -999, sw: 0, cw: 0, nw: 0 };
             var range = document.createRange();
             for (var k = 0; k < names.length; k++) {
               el.textContent = 'Peak: 3.9 ft \\u00b7 ' + names[k];
               range.selectNodeContents(el);
               var nw = range.getBoundingClientRect().width;
               var sw = el.scrollWidth, cw = el.clientWidth, over = sw - cw;
               if (nw > widest) widest = nw;
               if (over > worst.over || (over === worst.over && nw > worst.nw)) {
                 worst = { name: names[k], over: over, sw: sw, cw: cw, nw: nw };
               }
               if (over > 1) bad.push(names[k] + ':+' + over);
             }
             el.textContent = orig;
             return { worst: worst, widest: widest, bad: bad };
           }""", names)


def check_header(page, names):
    rows = []
    sweeps = []
    for w, h in ((390, 844), (360, 800)):
        page.set_viewport_size({"width": w, "height": h})
        page.wait_for_timeout(500)
        m = _header_metrics(page)
        sw = _sweep(page, names)
        rows.append((w, m))
        sweeps.append((w, sw))
        page.screenshot(path=str(SHOTS / ("bpc-s5-%d.png" % w)))
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    ok = all(m["c"] == 72 and m["s"] <= 72 for _, m in rows) and \
        all(not sw["bad"] for _, sw in sweeps)
    detail = " | ".join("%d: %d/%d" % (w, m["c"], m["s"]) for w, m in rows)
    worst = max((sw["worst"] for _, sw in sweeps), key=lambda x: x["over"])
    widest = max(sw["widest"] for _, sw in sweeps)
    record(3, "header layout", ok,
           "%s | worst='Peak: 3.9 ft · %s' natural=%.0fpx scrollWidth=%d clientWidth=%d "
           "over=%d widest_natural=%dpx overflow=%s"
           % (detail, worst["name"], worst["nw"], worst["sw"], worst["cw"], worst["over"],
              widest, [b for _, sw in sweeps for b in sw["bad"]] or "none"))


def check_tier(page):
    v = page.evaluate(
        "() => ({ hs: parseFloat(document.body.dataset.hsFt),"
        " hm: parseFloat(document.body.dataset.hmaxFt),"
        " fi: document.getElementById('frame-info').textContent,"
        " cls: document.getElementById('comfort-chip').className,"
        " txt: document.getElementById('comfort-chip').textContent })")
    m = re.search(r"H/L\s+([0-9.]+)", v["fi"])
    hl = float(m.group(1)) if m else float("nan")
    key, label = tier_of(v["hs"], v["hm"], hl)
    ok = v["cls"] == "tier-" + key and v["txt"] == label and v["txt"].strip() != ""
    record(4, "tier chip", ok,
           "max=%s roller=%s H/L=%s => tier-%s '%s' | chip='%s' text='%s'"
           % (v["hs"], v["hm"], hl, key, label, v["cls"], v["txt"]))


def check_clock(page):
    v = page.evaluate(
        "() => ({ label: document.getElementById('hour-label').textContent,"
        " hour: document.body.dataset.hour })")
    expected = format_chicago(v["hour"])
    fmt_ok = bool(re.match(r"^\d{1,2}:\d{2} (AM|PM) C[DS]T$", v["label"]))
    ok = fmt_ok and v["label"] == expected
    record(5, "clock", ok,
           "hour-label='%s' zoneinfo='%s' data-hour=%s regex=%s"
           % (v["label"], expected, v["hour"], fmt_ok))


def check_compass(page, gamma):
    v = page.evaluate(
        """() => {
             var a = document.getElementById('wind-badge-arrow');
             var badge = document.getElementById('wind-badge').getBoundingClientRect();
             var map = document.getElementById('map').getBoundingClientRect();
             var z = document.querySelector('.leaflet-control-zoom');
             var zr = z ? z.getBoundingClientRect() : null;
             return {
               text: document.getElementById('wind-badge-text').textContent,
               transform: getComputedStyle(a).transform,
               speed: parseFloat(document.body.dataset.windMph),
               grid: parseFloat(document.body.dataset.bearingGrid),
               badge: {x: badge.x, y: badge.y, w: badge.width, h: badge.height},
               map: {x: map.x, y: map.y, w: map.width, h: map.height},
               zoom: zr ? {x: zr.x, y: zr.y, w: zr.width, h: zr.height} : null,
               aria: document.getElementById('wind-badge').getAttribute('aria-label')
             };
           }""")
    if v["speed"] < 3:
        ok = v["text"] == "Calm" and bool(v["aria"])
        record(6, "compass badge", ok,
               "calm wind speed=%s text='%s' aria='%s'" % (v["speed"], v["text"], v["aria"]))
        return
    text_ok = bool(re.match(r"^[NSEW]{1,2} \d{1,3}°$", v["text"]))
    m = re.match(r"matrix\(([^)]+)\)", v["transform"])
    angle = None
    if m:
        parts = [float(x) for x in m.group(1).split(",")]
        angle = (math.degrees(math.atan2(parts[1], parts[0]))) % 360
    expected = (v["grid"] + gamma) % 360
    delta = min(abs(angle - expected), 360 - abs(angle - expected)) if angle is not None else 999
    b, mp = v["badge"], v["map"]
    bcx, bcy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    in_quadrant = (bcx > mp["x"] + mp["w"] / 2 and bcy < mp["y"] + mp["h"] / 2 and
                   b["x"] >= mp["x"] and b["y"] >= mp["y"] and
                   b["x"] + b["w"] <= mp["x"] + mp["w"] and
                   b["y"] + b["h"] <= mp["y"] + mp["h"])
    clear_zoom = True
    if v["zoom"]:
        z = v["zoom"]
        clear_zoom = not (b["x"] < z["x"] + z["w"] and z["x"] < b["x"] + b["w"] and
                          b["y"] < z["y"] + z["h"] and z["y"] < b["y"] + b["h"])
    aria_ok = bool(v["aria"]) and re.match(r"^Wind from [NSEW]{1,2} at \d+ degrees$", v["aria"]) is not None
    ok = text_ok and angle is not None and delta <= 1.5 and in_quadrant and clear_zoom and aria_ok
    record(6, "compass badge", ok,
           "text='%s' arrow=%.2f° expected=%.2f° delta=%.2f (into-wind) "
           "top-right=%s clear-zoom=%s aria='%s'"
           % (v["text"], angle if angle is not None else float("nan"), expected, delta,
              in_quadrant, clear_zoom, v["aria"]))


def check_ramp_location(page):
    # Stage 5B: the legend strip is replaced by the Hs ramp row, which must live inside
    # #deck (and NOT inside #map). (No pre-existing legend check was present in this
    # harness; this is the authorised legend-location replacement.)
    v = page.evaluate(
        """() => {
             var bar = document.getElementById('ramp-bar');
             var deck = document.getElementById('deck');
             var map = document.getElementById('map');
             var ticks = document.getElementById('ramp-ticks');
             return {
               exists: !!bar,
               inDeck: !!(bar && deck && deck.contains(bar)),
               inMap: !!(bar && map && map.contains(bar)),
               legend: !!document.getElementById('legend'),
               stops: ticks ? Array.from(ticks.children).map(function (s) { return s.textContent; }) : [],
               gradient: bar ? getComputedStyle(bar).backgroundImage : '',
             };
           }""")
    grad_ok = all(c in v["gradient"] for c in (
        "rgb(30, 64, 175)", "rgb(6, 182, 212)", "rgb(245, 158, 11)",
        "rgb(234, 88, 12)", "rgb(220, 38, 38)", "rgb(190, 24, 93)"))
    stops_ok = v["stops"] == ["0", "1", "2", "3.5", "4.5", "6+"]
    ok = v["exists"] and v["inDeck"] and not v["inMap"] and stops_ok and grad_ok
    record("7a", "ramp location", ok,
           "ramp in-deck=%s in-map=%s legend-present=%s stops=%s gradient-six=%s"
           % (v["inDeck"], v["inMap"], v["legend"], v["stops"], grad_ok))


def check_card_and_touch(page, warp):
    ll = ll_bounds(warp)
    page.evaluate("(ll) => window.__bpcMap.fitBounds(ll, {padding:[12,12], maxZoom:12})", ll)
    page.wait_for_timeout(900)
    mr = page.evaluate(
        "() => { var r = document.getElementById('map').getBoundingClientRect();"
        " return {x:r.x, y:r.y, w:r.width, h:r.height}; }")
    page.mouse.click(mr["x"] + mr["w"] / 2, mr["y"] + mr["h"] / 2)
    page.wait_for_timeout(600)
    card = page.evaluate(
        """() => {
             var c = document.getElementById('card');
             return { hidden: c.hidden,
               fields: Array.from(document.querySelectorAll('#card .card-line .v'))
                         .map(function (e) { return e.textContent; }),
               pin: document.querySelectorAll('#map .leaflet-overlay-pane path').length };
           }""")
    six = len(card["fields"]) == 6 and all(f.strip() not in ("", "—") for f in card["fields"])
    page.screenshot(path=str(SHOTS / "bpc-s5-card.png"))

    page.click("#card-close")
    page.wait_for_timeout(400)
    a = page.evaluate(
        "() => ({ hidden: document.getElementById('card').hidden,"
        " pin: document.querySelectorAll('#map .leaflet-overlay-pane path').length })")
    page.wait_for_timeout(400)
    b = page.evaluate(
        "() => ({ hidden: document.getElementById('card').hidden,"
        " pin: document.querySelectorAll('#map .leaflet-overlay-pane path').length })")
    stayed = a["hidden"] and a["pin"] == 0 and b["hidden"] and b["pin"] == 0

    # land / nodata click, a few px west of the fitted bbox (off-grid -> nodata)
    north = warp["corners"]["nw"][1]
    south = warp["corners"]["se"][1]
    west = warp["corners"]["nw"][0]
    lat_c = (north + south) / 2
    lon_land = west - 0.004
    lp = page.evaluate(
        "(ll) => { var p = window.__bpcMap.latLngToContainerPoint(ll);"
        " return {x: p.x, y: p.y}; }", [lat_c, lon_land])
    x = max(2, min(mr["w"] - 2, mr["x"] + lp["x"]))
    y = max(mr["y"] + 2, min(mr["y"] + mr["h"] - 2, mr["y"] + lp["y"]))
    tag = page.evaluate(
        "(p) => { var e = document.elementFromPoint(p[0], p[1]);"
        " return e ? e.tagName + '|' + (e.className || '') : 'none'; }", [x, y])
    page.mouse.click(x, y)
    page.wait_for_timeout(350)
    flash = page.evaluate("document.getElementById('readout').textContent")
    page.wait_for_timeout(2200)
    revert = page.evaluate("document.getElementById('readout').textContent")
    ok = six and not card["hidden"] and stayed and flash == LAND_FLASH and revert == DEFAULT_HINT
    record(8, "tap card", ok,
           "fields=%s opened=%s dismissed-pin=0=%s land-flash='%s' revert='%s' land-hit=%s"
           % (card["fields"], not card["hidden"], stayed, flash, revert, tag))


def check_touch_ergonomics(page):
    """5C/5E: a real mouse drag on #deck seeks through vertical wander (pointer capture),
    the pill lingers then hides, buttons are not swallowed by the scrub surface, and the
    pill stays clamped inside the track at BOTH ends. A second drift presses inside the
    deck-main row itself (non-interactive centre) to prove capture is deck-wide."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    g = page.evaluate(
        """() => {
             var rail = document.getElementById('track-rail').getBoundingClientRect();
             var track = document.getElementById('track').getBoundingClientRect();
             var deck = document.getElementById('deck').getBoundingClientRect();
             var play = document.getElementById('play').getBoundingClientRect();
             return {
               rail: {x: rail.x, y: rail.y, w: rail.width, h: rail.height},
               track: {x: track.x, y: track.y, w: track.width, h: track.height},
               deck: {x: deck.x, y: deck.y, w: deck.width, h: deck.height},
               n: parseInt(document.getElementById('track').getAttribute('aria-valuemax'), 10) + 1,
               play: {w: play.width, h: play.height},
             };
           }""")
    rail, track, deck, n = g["rail"], g["track"], g["deck"], g["n"]
    y = track["y"] + 2  # inside .deck-track, clear of the deck-main buttons
    x20 = rail["x"] + 0.20 * rail["w"]
    x70 = rail["x"] + 0.70 * rail["w"]
    half_up = lambda v: int(math.floor(v + 0.5))
    start_idx = half_up(0.20 * (n - 1))
    expected = half_up(0.70 * (n - 1))

    # (a)/(b) press at 20%, wander +/-80px vertically, land at 70%, release.
    page.mouse.move(x20, y)
    page.mouse.down()
    page.mouse.move(x20, y - 80, steps=4)                      # wander up onto the map
    page.mouse.move(x20 + 0.25 * rail["w"], y + 80, steps=4)   # wander down across the deck
    page.mouse.move(x70, y, steps=6)                           # land on target
    page.wait_for_timeout(80)
    during = page.evaluate(
        "() => ({ hidden: document.getElementById('time-pill').hidden,"
        " text: document.getElementById('time-pill').textContent,"
        " idx: parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10) })")
    page.mouse.up()
    page.wait_for_timeout(200)
    landed = int(page.evaluate("parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10)"))
    page.wait_for_timeout(1200)  # >1.2 s after release
    pill_after = page.evaluate("document.getElementById('time-pill').hidden")
    a_ok = abs(landed - expected) <= 1 and landed != start_idx
    b_ok = (during["hidden"] is False and bool(during["text"]) and pill_after is True)
    # (c) clicking #play is ignored by the scrub surface (index does not jump)
    idx_before = int(page.evaluate("parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10)"))
    page.click("#play")
    page.wait_for_timeout(80)  # < PLAY_INTERVAL_MS, before the first tick
    idx_after = int(page.evaluate("parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10)"))
    page.click("#play")        # back to paused
    page.wait_for_timeout(150)
    c_ok = idx_before == idx_after
    # (d) play button still meets the 44px touch target
    d_ok = g["play"]["w"] >= 44 and g["play"]["h"] >= 44

    # focused drift helper: press in the track row, drag to target_x, keep the pill
    # inside the track. Returns the raw pill/track rects + the landed index.
    def pill_clamp(target_x):
        page.mouse.move(x20, y)
        page.mouse.down()
        page.mouse.move(target_x, y, steps=6)
        page.wait_for_timeout(80)
        r = page.evaluate(
            """() => { var p = document.getElementById('time-pill').getBoundingClientRect();
                 var t = document.getElementById('track').getBoundingClientRect();
                 return { px: p.x, pw: p.width, tx: t.x, tw: t.width,
                          idx: parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10) }; }""")
        page.mouse.up()
        page.wait_for_timeout(1200)
        inside = (r["px"] >= r["tx"] - 0.5 and
                  r["px"] + r["pw"] <= r["tx"] + r["tw"] + 0.5)
        return r, inside

    # pill clamp at BOTH ends: far right -> last frame, far left -> frame 0.
    right, right_inside = pill_clamp(rail["x"] + rail["w"] - 0.5)
    right_ok = right["idx"] == n - 1 and right_inside
    left, left_inside = pill_clamp(rail["x"] + 0.5)
    left_ok = left["idx"] == 0 and left_inside

    # second drift: press INSIDE the deck-main row (non-interactive centre), wander
    # +/-80 px, land at 70% of the rail. Deck-wide pointer capture makes the drag seek.
    dcx = deck["x"] + deck["w"] / 2
    dcy = deck["y"] + 24
    hit = page.evaluate(
        "(p) => { var e = document.elementFromPoint(p[0], p[1]);"
        " return { tag: e ? e.tagName : 'none', cls: e ? (e.className || '') : '',"
        "   interactive: !!(e && e.closest && e.closest('button, [role=button], a, input')) }; }",
        [dcx, dcy])
    page.mouse.move(dcx, dcy)
    page.mouse.down()
    page.mouse.move(dcx, dcy - 80, steps=4)
    page.mouse.move(x20, dcy + 80, steps=4)
    page.mouse.move(x70, y, steps=6)
    page.wait_for_timeout(80)
    during2 = page.evaluate(
        "() => ({ hidden: document.getElementById('time-pill').hidden,"
        " idx: parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10) })")
    page.mouse.up()
    page.wait_for_timeout(200)
    landed2 = int(page.evaluate("parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10)"))
    page.wait_for_timeout(1200)
    pill_after2 = page.evaluate("document.getElementById('time-pill').hidden")
    e_ok = (not hit["interactive"] and abs(landed2 - expected) <= 1 and
            during2["hidden"] is False and pill_after2 is True)

    ok = a_ok and b_ok and c_ok and d_ok and right_ok and left_ok and e_ok
    print("        drift: start=%d landed=%d expected=%d (+/-1) during-pill=%s text='%s' "
          "after-pill-hidden=%s" % (start_idx, landed, expected, not during["hidden"],
                                    during["text"], pill_after))
    print("        play-click: before=%d after=%d unchanged=%s play=%dx%d"
          % (idx_before, idx_after, c_ok, round(g["play"]["w"]), round(g["play"]["h"])))
    print("        pill right: idx=%d/%d pill=[%.1f,%.1f] track=[%.1f,%.1f] inside=%s"
          % (right["idx"], n - 1, right["px"], right["px"] + right["pw"],
             right["tx"], right["tx"] + right["tw"], right_inside))
    print("        pill left:  idx=%d/0 pill=[%.1f,%.1f] track=[%.1f,%.1f] inside=%s"
          % (left["idx"], left["px"], left["px"] + left["pw"],
             left["tx"], left["tx"] + left["tw"], left_inside))
    print("        deck-main drift: press=(%.1f,%.1f) target=%s.%s interactive=%s "
          "landed=%d expected=%d (+/-1) pill-during=%s hidden-after=%s"
          % (dcx, dcy, hit["tag"], hit["cls"], hit["interactive"], landed2, expected,
             not during2["hidden"], pill_after2))
    record("7b", "touch ergonomics", ok,
           "wander±80 landed=%d/%d pill-during=%s hidden-after=%s play-unchanged=%s "
           "play=%dx%d right=%d/%d inside=%s left=%d/0 inside=%s "
           "deck-press=%s.%s noninteractive=%s deck-landed=%d/%d"
           % (landed, expected, not during["hidden"], pill_after, c_ok,
              round(g["play"]["w"]), round(g["play"]["h"]), right["idx"], n - 1, right_inside,
              left["idx"], left_inside, hit["tag"], hit["cls"], not hit["interactive"],
              landed2, expected))


def check_playback(page, warp):
    page.evaluate("window.__bpcMap.setZoom(13)")
    page.wait_for_timeout(1300)
    page.click("#play")
    page.wait_for_timeout(120)  # let the play-width regather settle before sampling ticks
    page.evaluate(
        "() => { window.__s4h = []; window.__s4f = [];"
        " new MutationObserver(() => { var h = document.body.dataset.hour;"
        "   if (h) window.__s4h.push(h);"
        "   var f = document.body.dataset.frameMs;"
        "   if (f) window.__s4f.push(parseFloat(f)); })"
        " .observe(document.body, { attributes: true, attributeFilter: ['data-hour'] }); }")
    page.wait_for_function("window.__s4h.length >= 10", timeout=45000)
    snap = page.evaluate(
        "() => ({ cw: document.getElementById('field').width,"
        " hours: window.__s4h.slice(), fms: window.__s4f.slice(),"
        " encode: document.body.dataset.encodeMs })")
    page.screenshot(path=str(SHOTS / "bpc-s5-play.png"))
    page.click("#play")
    page.wait_for_timeout(1000)
    post = page.evaluate(
        "() => ({ cw: document.getElementById('field').width,"
        " created: window.__bpcCreated, revoked: window.__bpcRevoked })")
    canvas_during = snap["cw"]
    fms = snap["fms"] or [0.0]
    avg = sum(fms) / len(fms)
    mx = max(fms)
    ok = (canvas_during <= 780 and post["cw"] > 1000 and avg <= 60 and mx <= 60 and
          post["created"] > 0 and 0 < post["revoked"] <= post["created"])
    record(9, "playback perf", ok,
           "canvas_during=%d ticks=%d frameMs avg=%.1f max=%.1f encodeMs=%s "
           "canvas_paused=%d created=%d revoked=%d"
           % (canvas_during, len(snap["hours"]), avg, mx, snap["encode"],
              post["cw"], post["created"], post["revoked"]))
    print("        frameMs: %s" % [round(x, 1) for x in fms])
    print("        hours:   %s" % snap["hours"])


def _upscale(page):
    return page.evaluate(
        "() => { var i = document.querySelector('.leaflet-image-layer');"
        " var r = i.getBoundingClientRect();"
        " return { u: r.width / i.naturalWidth, nw: i.naturalWidth, w: r.width }; }")


def measure_upscales(page, warp, prefix):
    ll = ll_bounds(warp)
    out = {}
    page.evaluate("(ll) => window.__bpcMap.fitBounds(ll, {padding:[12,12], maxZoom:12})", ll)
    page.wait_for_timeout(1100)
    page.wait_for_function(OVERLAY_OK, timeout=30000)
    out["fit"] = _upscale(page)
    page.screenshot(path=str(SHOTS / ("bpc-s5-%s-fit.png" % prefix)))
    for z in (13, 14):
        page.evaluate("(z) => window.__bpcMap.setZoom(z)", z)
        page.wait_for_timeout(1400)
        page.wait_for_function(OVERLAY_OK, timeout=30000)
        out[str(z)] = _upscale(page)
        page.screenshot(path=str(SHOTS / ("bpc-s5-%s-z%d.png" % (prefix, z))))
    return out


def _sample_alpha(page, bounds, pts):
    "bounds: {west,east,north,south}; pts: [[lat,lon], ...] -> [alpha, ...]"
    return page.evaluate(
        """(args) => {
             var b = args.bounds, pts = args.pts;
             var i = document.querySelector('.leaflet-image-layer');
             var c = document.createElement('canvas');
             c.width = i.naturalWidth; c.height = i.naturalHeight;
             var x = c.getContext('2d');
             x.drawImage(i, 0, 0);
             var d = x.getImageData(0, 0, c.width, c.height).data;
             return pts.map(function (p) {
               var px = Math.round((p[1] - b.west) / (b.east - b.west) * c.width);
               var py = Math.round((b.north - p[0]) / (b.north - b.south) * c.height);
               px = Math.max(0, Math.min(c.width - 1, px));
               py = Math.max(0, Math.min(c.height - 1, py));
               return d[(py * c.width + px) * 4 + 3];
             });
           }""", {"bounds": bounds, "pts": pts})


def check_smoothing(page, meta, warp):
    now = measure_upscales(page, warp, "now")
    # GATE OVERRIDE (Reid, 2026-09-12): the raster ceiling stays at targetWidth(.., hi=1536).
    # At z13/z14 the lake bbox projects to ~2163/~4327 CSS px, so the overlay is upscaled
    # ~1.4x/~2.8x — accepted as design reality: a soft weather gradient at deep zoom is
    # physically appropriate, and 1536 px avoids mobile-Safari canvas memory crashes.
    # Pre-stage4 was 5.633x / 11.268x; the <=3.0x gate pins that improvement, not perfection.
    MAX_UPSCALE = 3.0
    up_ok = all(now[k]["u"] <= MAX_UPSCALE for k in ("fit", "13", "14"))
    record(10, "radar smoothing", up_ok,
           "upscale fit=%.3f z13=%.3f z14=%.3f (gate <=%.1f, 1536px ceiling accepted)" %
           (now["fit"]["u"], now["13"]["u"], now["14"]["u"], MAX_UPSCALE))

    # land-bleed: sample known-land meta corners + 2 mid-lake points on the fit raster
    west = warp["corners"]["nw"][0]
    east = warp["corners"]["se"][0]
    north = warp["corners"]["nw"][1]
    south = warp["corners"]["se"][1]
    bounds = {"west": west, "east": east, "north": north, "south": south}
    land = [[meta["wgs84_corners"]["nw"][1], meta["wgs84_corners"]["nw"][0]],
            [meta["wgs84_corners"]["ne"][1], meta["wgs84_corners"]["ne"][0]],
            [meta["wgs84_corners"]["se"][1], meta["wgs84_corners"]["se"][0]],
            [meta["wgs84_corners"]["sw"][1], meta["wgs84_corners"]["sw"][0]]]
    mid = [[46.23846, -93.64229], [46.20, -93.61]]
    page.evaluate("(ll) => window.__bpcMap.fitBounds(ll, {padding:[12,12], maxZoom:12})",
                  ll_bounds(warp))
    page.wait_for_timeout(1100)
    page.wait_for_function(OVERLAY_OK, timeout=30000)
    alphas = _sample_alpha(page, bounds, land + mid)
    land_a = alphas[:len(land)]
    mid_a = alphas[len(land):]
    bleed_ok = all(a == 0 for a in land_a) and all(a > 0 for a in mid_a)
    record(10.1, "land bleed", bleed_ok,
           "land_alpha=%s mid_lake_alpha=%s (land must be 0, mid >0)" % (land_a, mid_a))
    return now


def check_before_after(pw, now_ups, warp):
    subprocess.run(["git", "worktree", "remove", "--force", str(PRE_WT)],
                   cwd=ROOT, capture_output=True)
    subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True)
    add = subprocess.run(["git", "worktree", "add", "--detach", str(PRE_WT), PRE_TAG],
                         cwd=ROOT, capture_output=True, text=True)
    if add.returncode != 0:
        record(11, "before/after", False, "worktree add failed: %s" % add.stderr.strip())
        return
    port2 = free_port()
    srv2 = serve(port2, PRE_WT)
    browser2 = None
    try:
        if not wait_http("http://127.0.0.1:%d/index.html" % port2):
            record(11, "before/after", False, "pre-stage4 server did not start")
            return
        browser2, page2 = new_page(pw)
        load_app(page2, "http://127.0.0.1:%d/index.html" % port2)
        page2.wait_for_function(
            "() => { var i = document.querySelector('.leaflet-image-layer');"
            " return !!i && i.naturalWidth > 0; }", timeout=90000)
        before = measure_upscales(page2, warp, "pre4")
    finally:
        if browser2:
            browser2.close()
        srv2.terminate()
        subprocess.run(["git", "worktree", "remove", "--force", str(PRE_WT)],
                       cwd=ROOT, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True)
    print("        level   pre-stage4 (stages 1-3)   stage-4 (now)")
    for key in ("fit", "13", "14"):
        print("        %-6s  %-23.3f  %.3f"
              % (key, before[key]["u"], now_ups[key]["u"]))
    record(11, "before/after", True,
           "fit %.3f->%.3f  z13 %.3f->%.3f  z14 %.3f->%.3f"
           % (before["fit"]["u"], now_ups["fit"]["u"],
              before["13"]["u"], now_ups["13"]["u"],
              before["14"]["u"], now_ups["14"]["u"]))


def check_suites():
    all_ok = True
    for name in ("parity", "wind", "render", "ui"):
        r = subprocess.run(["node", "tests/%s.test.js" % name],
                           cwd=ROOT, capture_output=True, text=True)
        lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
        tail = lines[-1] if lines else "(no output)"
        all_ok = all_ok and r.returncode == 0
        record(12, "suite %s" % name, r.returncode == 0,
               "exit=%d tail: %s" % (r.returncode, tail))
    return all_ok


def check_seam():
    """5A: the live +48 h handoff from native minutely_15 to vector-blended hourly
    frames is continuous. Runs tools/qa/seam_check.js (live network) and parses its
    one-line SEAM summary."""
    r = subprocess.run(["node", "tools/qa/seam_check.js"], cwd=ROOT,
                       capture_output=True, text=True)
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    for ln in lines:
        print("        seam: %s" % ln)
    summary = next((ln for ln in lines if ln.startswith("SEAM ")), "")
    m = re.search(r"dSpeed=([0-9.]+)\s+dDir=([0-9.]+)", summary)
    if r.stderr.strip():
        print("        seam stderr: %s" % r.stderr.strip().splitlines()[-1])
    detail = "exit=%d %s" % (r.returncode, summary or "(no SEAM line)")
    if m:
        detail = "exit=%d dSpeed=%s dDir=%s | %s" % (
            r.returncode, m.group(1), m.group(2), summary)
    record(14, "live seam", r.returncode == 0 and m is not None, detail)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    for stale in SHOTS.glob("bpc-s5-*.png"):
        stale.unlink()
    meta = json.loads((ROOT / "public/meta.v1.json").read_text())
    warp = json.loads((ROOT / "public/warp.v1.json").read_text())
    spots = json.loads((ROOT / "public/spots.v1.json").read_text())
    names = [f["name"] for f in spots["features"]] + ["N Basin", "SW Shore"]
    gamma = meta["gamma_deg"]
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    subject = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()

    port = free_port()
    srv = serve(port, ROOT)
    if not wait_http("http://127.0.0.1:%d/index.html" % port):
        print("server did not start on port %d" % port)
        srv.terminate()
        return 1

    print("STAGE 5 RECEIPTS — big-pond-chop")
    print("generated: %s" % datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"))
    print("HEAD: %s %s" % (head, subject))
    print("harness: 390x844 DPR2 + 360x800, http://127.0.0.1:%d" % port)
    print("-" * 78)

    with sync_playwright() as pw:
        browser, page = new_page(pw)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        now_ups = None
        try:
            safe(1, "boot", check_boot, page, port)
            safe(2, "frame base", check_frame_base, page)
            safe(3, "header layout", check_header, page, names)
            safe(4, "tier chip", check_tier, page)
            safe(5, "clock", check_clock, page)
            safe(6, "compass badge", check_compass, page, gamma)
            safe("7a", "ramp location", check_ramp_location, page)
            safe(7, "touch", check_card_and_touch, page, warp)
            safe("7b", "touch ergonomics", check_touch_ergonomics, page)
            safe(9, "playback perf", check_playback, page, warp)
            now_ups = safe(10, "radar smoothing", check_smoothing, page, meta, warp)
            if now_ups:
                safe(11, "before/after", check_before_after, pw, now_ups, warp)
            # Stage-5 browser gates run LAST: a widen leaves the app's boot skeleton
            # visible (observed 5D defect, render.js:835/1009 — out of scope here), so
            # running them after the pre-existing interaction groups keeps those groups
            # byte-identical to stage 4. See docs/STAGE-5-RECEIPTS.md.
            safe("2b", "horizon ceiling", check_horizon_ceiling, page)
            safe(13, "lazy 7d compute", check_lazy_7d, page)
        finally:
            print("page errors: %d %s" % (len(errors), errors[:3]))
            browser.close()
        safe(12, "suites", check_suites)
        safe(14, "live seam", check_seam)
    srv.terminate()

    okc = sum(1 for _, _, ok, _ in RESULTS if ok)
    failc = len(RESULTS) - okc
    print("-" * 78)
    print("SUMMARY: %d ok, %d FAIL" % (okc, failc))
    for num, name, ok, _ in RESULTS:
        if not ok:
            print("  FAIL [%s] %s" % (num, name))
    print("screenshots: %s" % ", ".join(sorted(p.name for p in SHOTS.glob("bpc-s5-*.png"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
