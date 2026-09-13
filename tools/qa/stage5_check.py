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
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    print("playwright is required: run with /home/reid/.hermes/hermes-agent/venv/bin/python")
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[2]
PRE_TAG = "pre-stage4"
PRE_WT = Path("/tmp/bpc-pre4")
SHOTS = ROOT / "tmp" / "s5g-shots"
SHOTS.mkdir(parents=True, exist_ok=True)
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


def format_chicago_pill(iso_local):
    """5F pill format: 12-hour, no TZ suffix, minutes only when non-zero."""
    dt = datetime.fromisoformat(iso_local).replace(tzinfo=CHICAGO)
    return dt.strftime("%-I:%M %p").replace(":00 ", " ")


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


def _wait_boot_hidden(page, timeout=5000):
    """5D.2: a skeleton shown by a transition must hide again on the next painted frame."""
    try:
        page.wait_for_function(
            "() => document.getElementById('boot').classList.contains('hidden')",
            timeout=timeout)
        return True
    except Exception:
        return False


def check_horizon_ceiling(page):
    """5D/5E: the frame ceiling tracks the horizon (24 h = 96 frames, 7 day = 672) and
    each transition's first paint hides the boot skeleton again (5D.2 fix)."""
    page.click("#h-7d")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '671'",
        timeout=60000)
    max7 = page.get_attribute("#track", "aria-valuemax")
    p24_when7 = page.get_attribute("#h-24h", "aria-pressed")
    p7_when7 = page.get_attribute("#h-7d", "aria-pressed")
    boot7 = _wait_boot_hidden(page)
    page.click("#h-24h")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
        timeout=60000)
    max24 = page.get_attribute("#track", "aria-valuemax")
    p24_when24 = page.get_attribute("#h-24h", "aria-pressed")
    p7_when24 = page.get_attribute("#h-7d", "aria-pressed")
    boot24 = _wait_boot_hidden(page, 1000)
    ok = (max7 == "671" and max24 == "95" and
          p7_when7 == "true" and p24_when7 == "false" and
          p24_when24 == "true" and p7_when24 == "false" and boot7 and boot24)
    record("2b", "horizon ceiling", ok,
           "7d max=%s pressed 7d/24h=%s/%s boot-hidden=%s | "
           "24h max=%s pressed 24h/7d=%s/%s boot-hidden=%s"
           % (max7, p7_when7, p24_when7, boot7, max24, p24_when24, p7_when24, boot24))


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
        " return { c: h.clientHeight, s: h.scrollHeight, o: h.offsetHeight }; }")


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
    # 6C delta 1: 6B gave the header a 1 px hairline border-bottom (approved design),
    # so clientHeight is 71 (content-box) while the BAND is still 72 px. Assert the
    # border-box height (offsetHeight == 72) — same intent, correct box model.
    ok = all(m["o"] == 72 and m["s"] <= 72 for _, m in rows) and \
        all(not sw["bad"] for _, sw in sweeps)
    detail = " | ".join("%d: box=%d content=%d scroll=%d" % (w, m["o"], m["c"], m["s"]) for w, m in rows)
    worst = max((sw["worst"] for _, sw in sweeps), key=lambda x: x["over"])
    widest = max(sw["widest"] for _, sw in sweeps)
    record(3, "header layout", ok,
           "%s | worst='Peak: 3.9 ft · %s' natural=%.0fpx scrollWidth=%d clientWidth=%d "
           "over=%d widest_natural=%dpx overflow=%s"
           % (detail, worst["name"], worst["nw"], worst["sw"], worst["cw"], worst["over"],
              widest, [b for _, sw in sweeps for b in sw["bad"]] or "none"))


def check_tier(page):
    # Stage 6C repair: #frame-info was deleted in 6B (the H/L readout left the
    # header).  Re-point the probe at the shipped #three row — null-safe, so a
    # missing id reads '' instead of throwing.  #three carries no H/L anymore, so
    # hl stays NaN and the tier is decided by the max/roller body datasets.
    v = page.evaluate(
        "() => ({ hs: parseFloat(document.body.dataset.hsFt),"
        " hm: parseFloat(document.body.dataset.hmaxFt),"
        " fi: (function () { var t = document.getElementById('three');"
        "       return t ? t.textContent : ''; })(),"
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
    # 5F: the standalone clock left the deck; #time-pill is the live clock (compact format).
    v = page.evaluate(
        "() => ({ label: document.getElementById('time-pill').textContent,"
        " hour: document.body.dataset.hour })")
    expected = format_chicago_pill(v["hour"])
    fmt_ok = bool(re.match(r"^\d{1,2}(:\d{2})? (AM|PM)$", v["label"]))
    ok = fmt_ok and v["label"] == expected
    record(5, "clock", ok,
           "time-pill='%s' zoneinfo='%s' data-hour=%s regex=%s"
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
    from_deg = (v["grid"] + gamma) % 360      # source bearing shown in the text
    expected_arrow = (from_deg + 180) % 360   # flow vector: arrow points DOWNWIND
    text_ok = bool(re.match(r"^From [NSEW]{1,2} \d{1,3}°$", v["text"]))
    m = re.match(r"^From [NSEW]{1,2} (\d{1,3})°$", v["text"])
    text_deg_ok = bool(m) and abs(int(m.group(1)) - round(from_deg)) <= 0.5
    mm = re.match(r"matrix\(([^)]+)\)", v["transform"])
    angle = None
    if mm:
        parts = [float(x) for x in mm.group(1).split(",")]
        angle = (math.degrees(math.atan2(parts[1], parts[0]))) % 360
    delta = min(abs(angle - expected_arrow), 360 - abs(angle - expected_arrow)) if angle is not None else 999
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
    aria_ok = bool(v["aria"]) and re.match(
        r"^Wind from [NSEW]{1,2} at \d+ degrees, blowing toward \d+ degrees$",
        v["aria"]) is not None
    ok = text_ok and text_deg_ok and angle is not None and delta <= 1.5 and in_quadrant \
         and clear_zoom and aria_ok
    record(6, "compass badge", ok,
           "text='%s' from=%.2f° arrow=%.2f° expected=%.2f° (downwind) delta=%.2f "
           "top-right=%s clear-zoom=%s aria='%s'"
           % (v["text"], from_deg, angle if angle is not None else float("nan"),
              expected_arrow, delta, in_quadrant, clear_zoom, v["aria"]))


def check_ramp_location(page):
    # Stage 5L: the six-stop ramp is a non-interactive legend card inside #map again
    # (5K had docked it at the deck base; 5L floats it in a card with the wind strip
    # taking the deck's second row).
    v = page.evaluate(
        """() => {
             var bar = document.getElementById('legend-card-bar');
             var deck = document.getElementById('deck');
             var map = document.getElementById('map');
             var ticks = document.getElementById('legend-card-ticks');
             return {
               exists: !!bar,
               inDeck: !!(bar && deck && deck.contains(bar)),
               inMap: !!(bar && map && map.contains(bar)),
               legend: !!document.getElementById('legend-card'),
               stops: ticks ? Array.from(ticks.children).map(function (s) { return s.textContent; }) : [],
               gradient: bar ? getComputedStyle(bar).backgroundImage : '',
             };
           }""")
    grad_ok = all(c in v["gradient"] for c in (
        "rgb(8, 145, 178)", "rgb(6, 182, 212)", "rgb(245, 158, 11)",
        "rgb(234, 88, 12)", "rgb(220, 38, 38)", "rgb(190, 24, 93)"))
    stops_ok = v["stops"] == ["0", "1", "2", "3.5", "4.5", "6+"]
    ok = v["exists"] and v["inMap"] and not v["inDeck"] and v["legend"] and stops_ok and grad_ok
    record("7a", "ramp location", ok,
           "ramp in-deck=%s in-map=%s legend-card-present=%s stops=%s gradient-six=%s"
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
    """5G/5M: #track is a scrolling tape with a fixed centre reticle. A real mouse drag on
    #deck scrolls the tape: LEFT advances into the future, RIGHT rewinds, the amber pill
    never moves, a click on #play does not scrub, and a drag starting in the deck's bottom
    band (the 5M wind row, no second deck row) still scrubs (deck-wide pointer capture)."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    # Pin the 24 h horizon so the far-left/right clamp drags are guaranteed to clamp.
    if page.get_attribute("#h-24h", "aria-pressed") != "true":
        page.click("#h-24h")
        page.wait_for_function(
            "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
            timeout=60000)
        page.wait_for_timeout(300)
    g = page.evaluate(
        """() => {
             var deck = document.getElementById('deck').getBoundingClientRect();
             var play = document.getElementById('play').getBoundingClientRect();
             return { deck: {x: deck.x, y: deck.y, w: deck.width, h: deck.height},
                      play: {w: play.width, h: play.height} };
           }""")

    def metrics():
        return page.evaluate(
            """() => {
                 var t = document.getElementById('track-tape').getBoundingClientRect();
                 var p = document.getElementById('time-pill').getBoundingClientRect();
                 var tl = document.getElementById('timeline').getBoundingClientRect();
                 var max = parseInt(document.getElementById('track').getAttribute('aria-valuemax'), 10);
                 return {
                   idx: parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10),
                   n: max + 1, horizon: max === 671 ? '7d' : '24h',
                   tapeX: t.x, pillCx: p.x + p.width / 2,
                   tlCx: tl.x + tl.width / 2, tlX: tl.x, tlW: tl.width, tlY: tl.y,
                   transform: getComputedStyle(document.getElementById('track-tape')).transform,
                 };
               }""")

    m0 = metrics()
    n, horizon = m0["n"], m0["horizon"]
    pxf = (330.0 if horizon == "7d" else max(550.0, round(m0["tlW"]))) / 96.0
    ty = m0["tlY"] + 24  # inside #timeline, below the floating pill
    cx = m0["tlX"] + m0["tlW"] / 2

    # Known start: Home -> frame 0 so the left/right deltas are unambiguous.
    # Wait out the 320 ms tape glide so the baseline is a settled transform.
    page.focus("#track")
    page.keyboard.press("Home")
    page.wait_for_timeout(500)

    def drag(x_to):
        page.mouse.move(cx, ty)
        page.mouse.down()
        page.mouse.move(x_to, ty, steps=6)
        page.wait_for_timeout(120)
        during = metrics()
        page.mouse.up()
        page.wait_for_timeout(150)
        return during

    # (a) drag LEFT ~120px -> advance ~120/pxf, pill fixed, tape edge moves ~-120px.
    before = metrics()
    d_left = drag(cx - 120)
    adv = d_left["idx"] - before["idx"]
    a_ok = abs(adv - 120.0 / pxf) <= 1.0
    pill_ok = abs(d_left["pillCx"] - before["pillCx"]) <= 0.5
    tape_moved = d_left["tapeX"] - before["tapeX"]
    tape_ok = abs(tape_moved + 120.0) <= 3.0

    # (b) drag RIGHT ~60px -> rewind ~60/pxf, pill still fixed.
    before2 = metrics()
    d_right = drag(cx + 60)
    rew = before2["idx"] - d_right["idx"]
    b_ok = abs(rew - 60.0 / pxf) <= 1.0 and abs(d_right["pillCx"] - before2["pillCx"]) <= 0.5

    # (c) clamp far LEFT (window left edge minus 2x width) -> n-1, pill centred.
    d_hi = drag(m0["tlX"] - 2 * m0["tlW"])
    c_ok = d_hi["idx"] == n - 1 and abs(d_hi["pillCx"] - d_hi["tlCx"]) <= 0.5

    # (d) clamp far RIGHT -> 0, pill centred.
    d_lo = drag(m0["tlX"] + 3 * m0["tlW"])
    d_ok = d_lo["idx"] == 0 and abs(d_lo["pillCx"] - d_lo["tlCx"]) <= 0.5

    # (e) clicking #play must not scrub the tape.
    idx_before = metrics()["idx"]
    page.click("#play")
    page.wait_for_timeout(80)  # < PLAY_INTERVAL_MS, before the first tick
    idx_after = metrics()["idx"]
    page.click("#play")        # back to paused
    page.wait_for_timeout(150)
    e_ok = idx_before == idx_after

    # (f) a drag starting in the deck's bottom band (the new 5M wind row, no second row
    # anymore) still scrubs (deck-wide capture).
    dcx = g["deck"]["x"] + g["deck"]["w"] / 2
    dcy = g["deck"]["y"] + g["deck"]["h"] - 6
    hit = page.evaluate(
        "(p) => { var e = document.elementFromPoint(p[0], p[1]);"
        " var tl = document.getElementById('timeline');"
        " return { tag: e ? e.tagName : 'none', cls: e ? (e.className || '') : '',"
        "   inTape: !!(e && tl && (e === tl || tl.contains(e))),"
        "   interactive: !!(e && e.closest && e.closest('button, [role=button], a, input')) }; }",
        [dcx, dcy])
    ramp_before = metrics()
    page.mouse.move(dcx, dcy)
    page.mouse.down()
    page.mouse.move(dcx + 0.25 * m0["tlW"], dcy - 80, steps=4)
    page.mouse.move(cx - 120, ty, steps=6)
    page.wait_for_timeout(120)
    ramp_during = metrics()
    page.mouse.up()
    page.wait_for_timeout(150)
    ramp_adv = ramp_during["idx"] - ramp_before["idx"]
    f_ok = hit["inTape"] and not hit["interactive"] and abs(ramp_adv - 120.0 / pxf) <= 1.0

    # (g) play button still meets the 44px touch target.
    h_ok = g["play"]["w"] >= 44 and g["play"]["h"] >= 44

    ok = a_ok and pill_ok and tape_ok and b_ok and c_ok and d_ok and e_ok and f_ok and h_ok
    print("        left  drag: idx %d->%d (+%.1f/~%.1f) pill dx=%.2f tape dx=%.1f "
          "transform %s -> %s"
          % (before["idx"], d_left["idx"], adv, 120.0 / pxf,
             d_left["pillCx"] - before["pillCx"], tape_moved,
             before["transform"], d_left["transform"]))
    print("        right drag: idx %d->%d (-%.1f/~%.1f) pill dx=%.2f transform %s -> %s"
          % (before2["idx"], d_right["idx"], rew, 60.0 / pxf,
             d_right["pillCx"] - before2["pillCx"],
             before2["transform"], d_right["transform"]))
    print("        clamp: far-left idx=%d/%d pill-cx=%.1f tl-cx=%.1f | "
          "far-right idx=%d/0 pill-cx=%.1f tl-cx=%.1f"
          % (d_hi["idx"], n - 1, d_hi["pillCx"], d_hi["tlCx"],
             d_lo["idx"], d_lo["pillCx"], d_lo["tlCx"]))
    print("        play-click: before=%d after=%d unchanged=%s play=%dx%d"
          % (idx_before, idx_after, e_ok, round(g["play"]["w"]), round(g["play"]["h"])))
    print("        deck-wind drift: press=(%.1f,%.1f) target=%s.%s in-tape=%s interactive=%s "
          "idx=%d->%d (+%.1f)"
          % (dcx, dcy, hit["tag"], hit["cls"], hit["inTape"], hit["interactive"],
             ramp_before["idx"], ramp_during["idx"], ramp_adv))
    record("7b", "touch ergonomics", ok,
           "pxf=%.4f left-adv=%.1f right-rew=%.1f clamp=[%d/%d, %d/0] pill-fixed=%.2fpx "
           "tape-dx=%.1f play-unchanged=%s play=%dx%d deck-press=%s.%s in-tape=%s "
           "noninteractive=%s strip-adv=%.1f"
           % (pxf, adv, rew, d_hi["idx"], n - 1, d_lo["idx"], pill_ok and b_ok,
              tape_moved, e_ok, round(g["play"]["w"]), round(g["play"]["h"]),
              hit["tag"], hit["cls"], hit["inTape"], not hit["interactive"], ramp_adv))


def check_timeline_labels(page):
    """5L: the 24 h block carries exactly ONE day header, pinned at the block's start at
    idx 0 then clamped to the window's left edge (clear of #play) as the day scrolls; every
    sub-tick stays fully inside its block, the last block carries a right-anchored midnight
    '12', and 7 d keeps its 8 ticks per block with no duplicate '12' at a day join."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    if page.get_attribute("#h-24h", "aria-pressed") != "true":
        page.click("#h-24h")
        page.wait_for_function(
            "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
            timeout=60000)
        page.wait_for_timeout(300)

    def goto(target):
        page.focus("#track")
        page.keyboard.press("Home")
        page.wait_for_timeout(200)
        if target >= 95:
            page.keyboard.press("End")
        else:
            for _ in range(target // 4):
                page.keyboard.press("PageUp")
                page.wait_for_timeout(60)
        page.wait_for_timeout(420)  # let the 320 ms tape glide settle

    def metrics():
        return page.evaluate(
            """() => {
                 var tl = document.getElementById('timeline').getBoundingClientRect();
                 var blocks = Array.from(document.getElementById('track-days').children);
                 function ticks(b) {
                   var br = b.getBoundingClientRect();
                   return Array.from(b.querySelectorAll('.day-sub')).map(function (s) {
                     var r = s.getBoundingClientRect();
                     return { text: s.textContent, edge: s.classList.contains('edge'),
                              transform: getComputedStyle(s).transform,
                              left: getComputedStyle(s).left,
                              inside: r.left >= br.left - 1 && r.right <= br.right + 1 };
                   });
                 }
                 var heads = [];
                 blocks.forEach(function (b, bi) {
                   var br = b.getBoundingClientRect();
                   b.querySelectorAll('.day-head').forEach(function (h) {
                     var r = h.getBoundingClientRect();
                     heads.push({ text: h.textContent, block: bi,
                                  left: r.left, right: r.right,
                                  leftOffset: r.left - br.left,
                                  inside: r.left >= br.left - 1 && r.right <= br.right + 1,
                                  insideTimeline: r.left >= tl.left - 1 && r.right <= tl.right + 1 });
                   });
                 });
                 return {
                   heads: heads,
                   headCount: heads.length,
                   blockCount: blocks.length,
                   tlLeft: tl.left,
                   first: ticks(blocks[0]),
                   last: ticks(blocks[blocks.length - 1]),
                   max: parseInt(document.getElementById('track').getAttribute('aria-valuemax'), 10),
                   now: parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10),
                 };
                 }""", [])

    def wind_alignment():
        """5M: per block, pair each 3-hourly tick with its wind label and measure the centre
        delta; also flag the boundary tick (right-anchored, left:auto) and its wind count."""
        return page.evaluate(
            """() => {
                 var blocks = Array.from(document.getElementById('track-days').children);
                 function cx(el) { var r = el.getBoundingClientRect(); return r.x + r.width / 2; }
                 return blocks.map(function (b) {
                   var subs = Array.from(b.querySelectorAll('.day-sub'));
                   var winds = Array.from(b.querySelectorAll('.day-wind'));
                   var dots = subs.map(function (s) {
                     return { text: s.textContent, cx: cx(s),
                              boundary: s.style.right !== '' };
                   });
                   var deltas = [];
                   for (var i = 0; i < winds.length; i++) {
                     if (dots[i]) deltas.push({ h: dots[i].text,
                       d: Math.abs(cx(winds[i]) - dots[i].cx) });
                   }
                   return {
                     subCount: subs.length, windCount: winds.length,
                     windTexts: winds.map(function (w) { return w.textContent; }),
                     boundaryCount: dots.filter(function (d) { return d.boundary; }).length,
                     deltas: deltas,
                   };
                 });
               }""")

    def summarize_winds(blocks):
        counts = [b["windCount"] for b in blocks]
        texts_ok = bool(blocks) and all(re.fullmatch(r"\d+", t)
                                        for b in blocks for t in b["windTexts"])
        deltas = [d["d"] for b in blocks for d in b["deltas"]]
        paired = all(b["windCount"] == len(b["deltas"]) for b in blocks)
        boundary = sum(b["boundaryCount"] for b in blocks)
        return {"counts": counts, "texts_ok": texts_ok, "paired": paired,
                "boundary": boundary, "worst": max(deltas) if deltas else 0.0,
                "blocks": blocks}

    def ink_gaps():
        """5N: measure the actual text-run ink boxes with Range.getClientRects() — the fixed
        1.5 em span boxes hide real ink collisions. For each block's tick row (.day-sub) and
        wind row (.day-wind), sort the runs and report the minimum consecutive gap."""
        return page.evaluate(
            """() => {
                 var blocks = Array.from(document.getElementById('track-days').children);
                 function runs(el) {
                   var r = document.createRange();
                   r.selectNodeContents(el);
                   return Array.from(r.getClientRects())
                     .filter(function (b) { return b.width > 0; })
                     .map(function (b) { return { l: b.left, r: b.right }; });
                 }
                 function rowGap(els) {
                   var rects = [];
                   els.forEach(function (e) { rects = rects.concat(runs(e)); });
                   rects.sort(function (a, b) { return a.l - b.l; });
                   var min = Infinity;
                   for (var i = 1; i < rects.length; i++)
                     min = Math.min(min, rects[i].l - rects[i - 1].r);
                   return { min: min, n: rects.length };
                 }
                 return blocks.map(function (b) {
                   return { ticks: rowGap(Array.from(b.querySelectorAll('.day-sub'))),
                            winds: rowGap(Array.from(b.querySelectorAll('.day-wind'))) };
                 });
               }""")

    def summarize_gaps(blocks):
        vals = []
        overlap = False
        for b in blocks:
            for row in (b["ticks"], b["winds"]):
                if math.isfinite(row["min"]):
                    vals.append(row["min"])
                    if row["min"] < 0:
                        overlap = True
        return {"min": min(vals) if vals else float("inf"), "overlap": overlap, "n": len(vals)}

    def heat_rows():
        """5P: per 7d block — the .day-heat ribbon geometry/colour, the embedded .day-wind
        containment + shadow, and the row fonts."""
        return page.evaluate(
            """() => {
                 var blocks = Array.from(document.getElementById('track-days').children);
                 var tiers = ['rgb(8, 145, 178)','rgb(16, 185, 129)','rgb(245, 158, 11)',
                              'rgb(249, 115, 22)','rgb(239, 68, 68)'];
                 function tierSet(g) {
                   var m = g.match(/rgb\\(\\s*\\d+,\\s*\\d+,\\s*\\d+\\s*\\)/g) || [];
                   var seen = [];
                   m.forEach(function (c) {
                     var norm = c.replace(/\\s+/g, ' ');
                     if (tiers.indexOf(norm) >= 0 && seen.indexOf(norm) < 0) seen.push(norm);
                   });
                   return seen;
                 }
                 return blocks.map(function (b) {
                   var br = b.getBoundingClientRect();
                   var hs = Array.from(b.querySelectorAll('.day-heat'));
                   var h = hs[0];
                   var hr = h ? h.getBoundingClientRect() : null;
                   var cs = h ? getComputedStyle(h) : null;
                   var winds = Array.from(b.querySelectorAll('.day-wind'));
                   var inside = hr ? winds.every(function (w) {
                     var wr = w.getBoundingClientRect();
                     return wr.top >= hr.top - 1 && wr.bottom <= hr.bottom + 1;
                   }) : false;
                   var head = b.querySelector('.day-head');
                   var sub = b.querySelector('.day-sub:not(.edge)');
                   var wind = winds[0];
                   var grad = cs ? cs.backgroundImage : '';
                   return {
                     n: hs.length,
                     hh: hr ? hr.height : 0,
                     hw: hr ? hr.width : 0,
                     bw: br.width,
                     radius: cs ? parseFloat(cs.borderTopLeftRadius) : 0,
                     tiers: tierSet(grad),
                     stops: (grad.match(/rgb\\(/g) || []).length,
                     headSize: head ? parseFloat(getComputedStyle(head).fontSize) : 0,
                     headWeight: head ? getComputedStyle(head).fontWeight : '',
                     subSize: sub ? parseFloat(getComputedStyle(sub).fontSize) : 0,
                     subColor: sub ? getComputedStyle(sub).color : '',
                     windSize: wind ? parseFloat(getComputedStyle(wind).fontSize) : 0,
                     windWeight: wind ? getComputedStyle(wind).fontWeight : '',
                     windColor: wind ? getComputedStyle(wind).color : '',
                     shadow: wind ? getComputedStyle(wind).textShadow : '',
                     inside: inside,
                     hx: hr ? hr.x : 0,
                     bx: br.x,
                   };
                 });
               }""")

    heads = {}
    head_x = {}
    indices_ok = True
    head_count_ok = True
    sticky_window_ok = True
    sticky_block_ok = True
    ms = {}
    for idx in (0, 24, 48, 72, 95):
        goto(idx)
        m = metrics()
        ms[idx] = m
        if m["now"] != idx:
            indices_ok = False
        if m["headCount"] != 1:
            head_count_ok = False
        heads[idx] = m["headCount"]
        h = m["heads"][0] if m["headCount"] else None
        head_x[idx] = h["left"] if h else float("nan")
        # Sticky header stays inside the window and clear of the 48 px #play button.
        if not h or not h["insideTimeline"] or h["left"] < m["tlLeft"] + 52:
            sticky_window_ok = False
        # It must never leave its own day block.
        if not h or not h["inside"]:
            sticky_block_ok = False

    m0, m24 = ms[0], ms[95]
    # Exactly one header, pinned within 12 px of its block's left edge at the day start.
    one_head = len(m0["heads"]) == 1 and len(m24["heads"]) == 1
    head = m0["heads"][0] if m0["heads"] else {}
    head_pinned = one_head and abs(head.get("leftOffset", 1e9)) <= 12 and \
        head.get("inside") and bool(head.get("text", "").strip())
    # No two heads share the same text within a block.
    no_repeat = True
    by_block = {}
    for h in m24["heads"]:
        by_block.setdefault(h["block"], []).append(h["text"])
    for texts in by_block.values():
        if len(set(texts)) != len(texts):
            no_repeat = False
    # Sticky clamp engages: the header moves > 50 px between idx 0 and the day's end.
    sticky_shift = abs(head_x[95] - head_x[0])
    sticky_engages = sticky_shift > 50

    first, last = m24["first"], m24["last"]
    left_edge_ok = any(t["text"] == "12" and t["edge"] and t["transform"] in ("none", "") and
                       abs(float(t["left"].replace("px", "")) - 3) <= 1 for t in first)
    boundary_ok = any(t["text"] == "12" and t["edge"] and t["transform"] in ("none", "")
                      for t in last)
    ticks_ok = len(last) == 9
    labels_ok = sorted(t["text"] for t in first if t["text"] != "12") == \
        ["03", "03", "06", "06", "09", "09"]
    inside_ok = all(t["inside"] for t in first) and all(t["inside"] for t in last)

    # 5M: wind row at 24 h — one block, 8 three-hourly labels, no boundary sibling.
    w24 = summarize_winds(wind_alignment())
    eight24_ok = len(w24["counts"]) >= 1 and all(c == 8 for c in w24["counts"])
    boundary_no_wind = w24["boundary"] == 1
    wind24_ok = (eight24_ok and w24["texts_ok"] and w24["paired"] and
                 w24["worst"] <= 1.5 and boundary_no_wind)
    g24 = summarize_gaps(ink_gaps())

    # 7 day: 8 ticks per block and no two '12's within 20 px at a day join.
    page.click("#h-7d")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '671'",
        timeout=60000)
    page.wait_for_timeout(600)
    seven = page.evaluate(
        """() => {
             var blocks = Array.from(document.getElementById('track-days').children);
             var counts = blocks.map(function (b) { return b.querySelectorAll('.day-sub').length; });
             var twelves = [];
             blocks.forEach(function (b) {
               b.querySelectorAll('.day-sub').forEach(function (s) {
                 if (s.textContent === '12') {
                   var r = s.getBoundingClientRect();
                   twelves.push(r.x + r.width / 2);
                 }
               });
             });
             twelves.sort(function (a, b) { return a - b; });
             var minGap = Infinity;
             for (var i = 1; i < twelves.length; i++)
               minGap = Math.min(minGap, twelves[i] - twelves[i - 1]);
             return { counts: counts, minGap: minGap, twelves: twelves.length };
           }""")
    seven_ok = seven["counts"] == [8, 8, 8, 8, 8, 8, 8] and seven["minGap"] >= 20
    # 5M: wind row at 7 d — 7 blocks, 8 labels each, all aligned, no boundary tick.
    w7 = summarize_winds(wind_alignment())
    wind7_ok = (w7["counts"] == [8, 8, 8, 8, 8, 8, 8] and w7["texts_ok"] and
                w7["paired"] and w7["worst"] <= 1.5 and w7["boundary"] == 0)
    g7 = summarize_gaps(ink_gaps())
    # 5P: per-day heat ribbon (20 px, tier colours) with the wind numbers embedded inside
    # it, row typography, and the ribbon moving in lockstep with its parent block.
    heats = heat_rows()
    heat_count_ok = all(b["n"] == 1 for b in heats)
    heat_size_ok = all(abs(b["hh"] - 20) <= 1 and
                       abs(b["hw"] - (b["bw"] - 6)) <= 1 and b["radius"] >= 2 for b in heats)
    heat_inside_ok = all(b["inside"] for b in heats)
    # One stop per hourly sample in every block, and >= 2 distinct tier colours across the
    # 7d horizon (a uniformly calm day is legitimately one colour, so a per-block >= 2 would
    # fail on real calm stretches; see the 5p evidence line for per-block tier sets).
    heat_stops_ok = all(b["stops"] == 24 for b in heats)
    all_tiers = set()
    for b in heats:
        all_tiers.update(b["tiers"])
    heat_color_ok = heat_stops_ok and len(all_tiers) >= 2
    shadow_ok = all(b["shadow"] and b["shadow"] != "none" for b in heats)
    fonts_ok = all(b["headSize"] == 12 and b["headWeight"] == "600" and
                   b["subSize"] == 11 and b["subColor"] == "rgb(148, 163, 184)" and
                   b["windSize"] == 12 and b["windWeight"] == "700" and
                   b["windColor"] == "rgb(255, 255, 255)" for b in heats)
    page.focus("#track")
    page.keyboard.press("Home")
    page.wait_for_timeout(420)
    before_x = heat_rows()
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(420)
    after_x = heat_rows()
    moved = any(abs(after_x[i]["hx"] - before_x[i]["hx"]) > 1 for i in range(len(before_x)))
    scroll_ok = (len(before_x) == len(after_x) == len(heats) and moved and
                 all(abs((after_x[i]["hx"] - before_x[i]["hx"]) -
                         (after_x[i]["bx"] - before_x[i]["bx"])) <= 1
                     for i in range(len(before_x))))
    heat_ok = (heat_count_ok and heat_size_ok and heat_inside_ok and heat_color_ok and
               shadow_ok and fonts_ok and scroll_ok)

    # 5N: no two consecutive text runs in either row may overlap, and the minimum gap at
    # both horizons must be >= 6 px (ink boxes, not the fixed 1.5 em span boxes).
    ink_ok = (g24["min"] >= 6.0 and g7["min"] >= 6.0 and
              not g24["overlap"] and not g7["overlap"])

    page.click("#h-24h")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
        timeout=60000)
    page.wait_for_timeout(300)

    ok = (indices_ok and head_count_ok and one_head and head_pinned and no_repeat and
          sticky_window_ok and sticky_block_ok and sticky_engages and
          left_edge_ok and boundary_ok and ticks_ok and labels_ok and inside_ok and seven_ok and
          wind24_ok and wind7_ok and ink_ok and heat_ok)
    print("        heads/idx=%s headCount=%d pinned-offset=%.1f text='%s' "
          "sticky x0=%.0f x95=%.0f shift=%.0f window-ok=%s block-ok=%s sub-ticks/24h=%d "
          "(last block) left-edge=%s boundary=%s inside=%s labels=%s"
          % (heads, m24["headCount"], head.get("leftOffset", float("nan")), head.get("text", ""),
             head_x[0], head_x[95], sticky_shift, sticky_window_ok, sticky_block_ok,
             len(last), left_edge_ok, boundary_ok, inside_ok, labels_ok))
    print("        5M wind 24h: counts=%s worst-delta=%.2fpx nums=%s boundary-no-wind=%s list=%s"
          % (w24["counts"], w24["worst"], w24["texts_ok"], boundary_no_wind,
             w24["blocks"][0]["windTexts"] if w24["blocks"] else []))
    print("        5M wind 7d:  counts=%s worst-delta=%.2fpx nums=%s list(block0)=%s"
          % (w7["counts"], w7["worst"], w7["texts_ok"],
             w7["blocks"][0]["windTexts"] if w7["blocks"] else []))
    print("        5n gaps 24h=%.1fpx 7d=%.1fpx" % (g24["min"], g7["min"]))
    print("        5p ribbon: count=%s h=%s stops=%s colours=%s inside=%s shadow=%s fonts=%s "
          "scroll=%s | ink-gap 24h=%.1fpx 7d=%.1fpx"
          % (heat_count_ok, heat_size_ok, heat_stops_ok, heat_color_ok, heat_inside_ok,
             shadow_ok, fonts_ok, scroll_ok, g24["min"], g7["min"]))
    print("        5p tiers/block: %s (union=%d>=2)"
          % ([b["tiers"] for b in heats], len(all_tiers)))
    record(18, "timeline labels (5L)", ok,
           "indices=%s heads=%s one-head=%s pinned=%s no-repeat=%s sticky-window=%s "
           "sticky-block=%s head-x0=%.0f head-x95=%.0f shift=%.0f>50=%s "
           "left-edge-12=%s last-boundary-12=%s ticks=9=%s labels-3h=%s all-inside=%s | "
           "7d counts=%s min-12-gap=%.1f>=20=%s | 5m wind 24h counts=%s worst=%.2fpx nums=%s "
           "boundary-no-wind=%s list=%s | 7d counts=%s worst=%.2fpx nums=%s list0=%s | "
           "5n gaps 24h=%.1f>=6=%s 7d=%.1f>=6=%s overlap=%s/%s | "
           "5p ribbon heat-count=%s h=%s inside=%s shadow=%s colours=%s fonts=%s scroll=%s"
           % (indices_ok, heads, one_head, head_pinned, no_repeat, sticky_window_ok,
              sticky_block_ok, head_x[0], head_x[95], sticky_shift, sticky_engages,
              left_edge_ok, boundary_ok, ticks_ok, labels_ok, inside_ok, seven["counts"],
              seven["minGap"] if math.isfinite(seven["minGap"]) else -1.0, seven_ok,
              w24["counts"], w24["worst"], w24["texts_ok"], boundary_no_wind,
              w24["blocks"][0]["windTexts"] if w24["blocks"] else [],
              w7["counts"], w7["worst"], w7["texts_ok"],
              w7["blocks"][0]["windTexts"] if w7["blocks"] else [],
              g24["min"], g24["min"] >= 6.0, g7["min"], g7["min"] >= 6.0,
              g24["overlap"], g7["overlap"],
              heat_count_ok, heat_size_ok, heat_inside_ok, shadow_ok, heat_color_ok, fonts_ok,
              scroll_ok))


def check_deck_geometry(page):
    """5F/5L/5M: single full-height tape, timeline geometry, permanent amber pill, embedded
    play, wind strip gone."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(400)
    v = page.evaluate(
        """() => {
             var deck = document.getElementById('deck').getBoundingClientRect();
             var track = document.getElementById('track').getBoundingClientRect();
             var timelineEl = document.getElementById('timeline');
             var timeline = timelineEl.getBoundingClientRect();
             var play = document.getElementById('play').getBoundingClientRect();
             var strip = document.getElementById('wind-strip');
             var pill = document.getElementById('time-pill');
             var pr = pill.getBoundingClientRect();
             var days = document.getElementById('track-days');
             var blocks = Array.from(days.children);
             return {
               deckH: deck.height,
               stripAbsent: !strip,
               trackH: track.height,
               timelineH: timeline.height,
               absent: {
                 main: !document.querySelector('.deck-main'),
                 playhead: !document.getElementById('playhead'),
                 rail: !document.getElementById('track-rail'),
                 progress: !document.getElementById('track-progress'),
               },
               pillVisible: pr.width > 0 && pr.height > 0,
               pillHidden: pill.hasAttribute('hidden'),
               pillText: pill.textContent,
               pillRect: {x: pr.x, y: pr.y, w: pr.width, h: pr.height},
               play: {x: play.x, y: play.y, r: play.x + play.width, b: play.y + play.height,
                      w: play.width, h: play.height},
               track: {x: track.x, y: track.y, r: track.x + track.width, b: track.y + track.height},
               timeline: {x: timeline.x, y: timeline.y, r: timeline.x + timeline.width,
                          b: timeline.y + timeline.height},
               blockCount: blocks.length,
               blockBg: blocks.map(function (b) { return getComputedStyle(b).backgroundColor; }),
             };
           }""")
    p, t, tl = v["play"], v["track"], v["timeline"]
    play_inside = (p["x"] >= t["x"] - 0.5 and p["r"] <= t["r"] + 0.5 and
                   p["y"] >= t["y"] - 0.5 and p["b"] <= t["b"] + 0.5 and
                   p["x"] - t["x"] <= 2)
    # 5G: the play button overlays the window, so #timeline fills the whole track row.
    timeline_inside = (abs(tl["x"] - t["x"]) <= 1 and abs(tl["r"] - t["r"]) <= 1 and
                       tl["y"] >= t["y"] - 0.5 and tl["b"] <= t["b"] + 0.5)
    tl_cx = tl["x"] + (tl["r"] - tl["x"]) / 2
    pill_cx = v["pillRect"]["x"] + v["pillRect"]["w"] / 2
    pill_centred = abs(pill_cx - tl_cx) <= 1  # 5G: pill is anchored to the window centre
    bgs = v["blockBg"]
    adjacent_ok = all(bgs[i] != bgs[i + 1] for i in range(len(bgs) - 1))
    # 5P: the wind strip stays gone and the 3-tier deck is 62 px: #track/#timeline are 62 px.
    tape_62 = abs(v["trackH"] - 62) <= 1 and abs(v["timelineH"] - 62) <= 1
    ok = (v["deckH"] <= 72 and v["stripAbsent"] and tape_62 and all(v["absent"].values()) and
          v["pillVisible"] and not v["pillHidden"] and bool(v["pillText"].strip()) and
          pill_centred and play_inside and timeline_inside and v["blockCount"] >= 1 and adjacent_ok)
    print("        5F/5P rects: deck h=%.1f wind-strip-absent=%s track h=%.1f timeline h=%.1f "
          "play=[%.1f,%.1f]x%.1fx%.1f timeline=[%.1f,%.1f]-[%.1f,%.1f] pill=[%.1f,%.1f] %.1fx%.1f "
          "text='%s' pill-cx=%.1f timeline-cx=%.1f blocks=%d bg=%s"
          % (v["deckH"], v["stripAbsent"], v["trackH"], v["timelineH"],
             p["x"], p["y"], p["w"], p["h"], tl["x"], tl["y"], tl["r"], tl["b"],
             v["pillRect"]["x"], v["pillRect"]["y"], v["pillRect"]["w"], v["pillRect"]["h"],
             v["pillText"], pill_cx, tl_cx, v["blockCount"], bgs))
    record(15, "deck geometry (5F)", ok,
           "deckH=%.1f absent=%s strip-absent=%s trackH=%.1f timelineH=%.1f pill-visible=%s "
           "pill-hidden=%s pill='%s' pill-centred=%s (cx=%.1f timeline-cx=%.1f) play-inside=%s "
           "timeline-fills=%s blocks=%d adjacent-differ=%s"
           % (v["deckH"], v["absent"], v["stripAbsent"], v["trackH"], v["timelineH"],
              v["pillVisible"], v["pillHidden"], v["pillText"],
              pill_centred, pill_cx, tl_cx, play_inside, timeline_inside, v["blockCount"],
              adjacent_ok))


def check_tape_architecture(page):
    """5G: fixed centre reticle + wide scrolling tape. Asserts the reticle is centred in
    #timeline, #track-tape is a #timeline child holding #now-tick, the 24 h tape fills the
    window while 7 d is 1,100-1,400 px, the active frame sits under the reticle, #play
    overlays the window's left edge with z-index >= 10, and day blocks alternate with the
    full 8-label 3 h sub-row in the 7-day view. Restores 24 h when done."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(400)

    def metrics():
        return page.evaluate(
            """() => {
                 var tlEl = document.getElementById('timeline');
                 var tlr = tlEl.getBoundingClientRect();
                 var tape = document.getElementById('track-tape');
                 var tr = tape.getBoundingClientRect();
                 var pill = document.getElementById('time-pill').getBoundingClientRect();
                 var play = document.getElementById('play');
                 var pr = play.getBoundingClientRect();
                 var track = document.getElementById('track').getBoundingClientRect();
                 var blocks = Array.from(document.getElementById('track-days').children);
                 var max = parseInt(document.getElementById('track').getAttribute('aria-valuemax'), 10);
                 var cur = parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10);
                 var now = document.getElementById('now-tick');
                 return {
                   tlCx: tlr.x + tlr.width / 2, tlW: tlr.width,
                   tapeX: tr.x, tapeW: tr.width,
                   pillCx: pill.x + pill.width / 2,
                   tapeInTimeline: tape.parentElement === tlEl,
                   nowInTape: !!(now && now.parentElement === tape),
                   cur: cur, n: max + 1, horizon: max === 671 ? '7d' : '24h',
                   playX: pr.x, playW: pr.width, playZ: getComputedStyle(play).zIndex,
                   trackX: track.x,
                   blockCount: blocks.length,
                   blockBg: blocks.map(function (b) { return getComputedStyle(b).backgroundColor; }),
                   subCounts: blocks.map(function (b) { return b.querySelectorAll('.day-sub').length; }),
                   transform: getComputedStyle(tape).transform,
                 };
               }""")

    def pxf_for(m):
        return (330.0 if m["horizon"] == "7d" else max(550.0, round(m["tlW"]))) / 96.0

    def centred(m):
        return abs(m["pillCx"] - m["tlCx"]) <= 1.0

    def frame_under_reticle(m):
        return abs((m["tapeX"] + m["cur"] * pxf_for(m)) - m["pillCx"]) <= 1.0

    m24 = metrics()
    ok_parent = m24["tapeInTimeline"] and m24["nowInTape"]
    ok_play = (0 <= (m24["playX"] - m24["trackX"]) <= 56 and
               int(m24["playZ"] or 0) >= 10 and m24["playW"] >= 44)
    ok_centre24 = centred(m24)
    ok_frame24 = frame_under_reticle(m24)
    ok_tape24 = m24["tapeW"] >= m24["tlW"] - 2 and m24["tapeW"] >= m24["tlW"] + 100
    ok_blocks24 = m24["blockCount"] >= 1
    print("        24h: tapeW=%.1f (window %.1f, runway %.1f, pxf=%.4f) pill-cx=%.1f tl-cx=%.1f "
          "frame-cx=%.1f cur=%d transform=%s"
          % (m24["tapeW"], m24["tlW"], m24["tapeW"] - m24["tlW"], pxf_for(m24),
             m24["pillCx"], m24["tlCx"],
             m24["tapeX"] + m24["cur"] * pxf_for(m24), m24["cur"], m24["transform"]))

    # scrub mid-window, then re-check the reticle.
    tl = page.evaluate(
        "() => { var r = document.getElementById('timeline').getBoundingClientRect();"
        " return {cx: r.x + r.width / 2, y: r.y + r.height / 2}; }")
    page.mouse.move(tl["cx"], tl["y"])
    page.mouse.down()
    page.mouse.move(tl["cx"] - 140, tl["y"], steps=8)
    page.mouse.up()
    page.wait_for_timeout(500)
    m_scrub = metrics()
    ok_scrub = centred(m_scrub) and frame_under_reticle(m_scrub)
    print("        scrub@24h: cur=%d pill-cx=%.1f tl-cx=%.1f frame-cx=%.1f"
          % (m_scrub["cur"], m_scrub["pillCx"], m_scrub["tlCx"],
             m_scrub["tapeX"] + m_scrub["cur"] * pxf_for(m_scrub)))

    # widen to 7 days.
    page.click("#h-7d")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '671'",
        timeout=60000)
    page.wait_for_timeout(700)
    m7 = metrics()
    ok_centre7 = centred(m7)
    ok_frame7 = frame_under_reticle(m7)
    ok_tape7 = 2280 <= m7["tapeW"] <= 2340
    bgs = m7["blockBg"]
    ok_alt = len(bgs) >= 2 and all(bgs[i] != bgs[i + 1] for i in range(len(bgs) - 1))
    # 5O: the two tones are pinned exactly (#23272e vs #1b1d22) and must alternate.
    tone_set = set(bgs)
    tones_ok = tone_set == {"rgb(35, 39, 46)", "rgb(27, 29, 34)"} and ok_alt
    ok_blocks7 = m7["blockCount"] == 7 and all(c == 8 for c in m7["subCounts"])
    print("        7d:  tapeW=%.1f (window %.1f, pxf=%.4f) pill-cx=%.1f tl-cx=%.1f "
          "frame-cx=%.1f cur=%d blocks=%d subs=%s transform=%s"
          % (m7["tapeW"], m7["tlW"], pxf_for(m7), m7["pillCx"], m7["tlCx"],
             m7["tapeX"] + m7["cur"] * pxf_for(m7), m7["cur"], m7["blockCount"],
             m7["subCounts"], m7["transform"]))
    print("        5o tones: set=%s alternating=%s" % (sorted(tone_set), ok_alt))

    ok = (ok_parent and ok_play and ok_centre24 and ok_frame24 and ok_tape24 and
          ok_blocks24 and ok_scrub and ok_centre7 and ok_frame7 and ok_tape7 and
          ok_alt and ok_blocks7 and tones_ok)
    record(16, "tape architecture (5G)", ok,
           "tape-in-timeline=%s now-in-tape=%s play-left=%.1f z=%s | "
           "24h tape=%.1f/window=%.1f runway=%.1f centred=%s frame-under=%s | "
           "7d tape=%.1f blocks=%d subs=%s alt=%s tones=%s tones-ok=%s centred=%s frame-under=%s"
           % (m24["tapeInTimeline"], m24["nowInTape"], m24["playX"] - m24["trackX"],
              m24["playZ"], m24["tapeW"], m24["tlW"], m24["tapeW"] - m24["tlW"],
              ok_centre24, ok_frame24,
              m7["tapeW"], m7["blockCount"], m7["subCounts"], ok_alt, sorted(tone_set),
              tones_ok, ok_centre7, ok_frame7))

    # restore 24 h for the checks that follow.
    page.click("#h-24h")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
        timeout=60000)
    page.wait_for_timeout(300)


# Stage 5H: external instrumentation for the scrub-decoupling group. It must be installed
# while #track-tape exists. Counts: inline translateX writes, overlay src swaps, long tasks,
# and delivered pointer moves (capture phase).
SCRUB_INSTR = r"""
() => {
  var tape = document.getElementById('track-tape');
  window.__sb = { tx: 0, moves: 0, downX: null, lastX: null, swaps: 0, long: [],
                  txInst: false, srcInst: false, longInst: false };
  // Chromium has no prototype transform accessor; shadow it on #track-tape's own style.
  try {
    if (tape && tape.style) {
      Object.defineProperty(tape.style, 'transform', {
        configurable: true,
        get: function () { return this.getPropertyValue('transform'); },
        set: function (v) {
          if (String(v).indexOf('translateX') === 0) window.__sb.tx++;
          this.setProperty('transform', v);
        }
      });
      window.__sb.txInst = true;
    }
  } catch (e) { window.__sb.txInst = false; }
  try {
    var img = document.querySelector('.leaflet-image-layer');
    if (img && window.MutationObserver) {
      new MutationObserver(function () { window.__sb.swaps++; })
        .observe(img, { attributes: true, attributeFilter: ['src'] });
      window.__sb.srcInst = true;
    }
  } catch (e) { window.__sb.srcInst = false; }
  try {
    new PerformanceObserver(function (l) {
      l.getEntries().forEach(function (en) { window.__sb.long.push(Math.round(en.duration)); });
    }).observe({ entryTypes: ['longtask'] });
    window.__sb.longInst = true;
  } catch (e) { window.__sb.longInst = false; }
  window.addEventListener('pointerdown', function (e) { window.__sb.downX = e.clientX; }, true);
  window.addEventListener('pointermove', function (e) {
    window.__sb.moves++; window.__sb.lastX = e.clientX;
  }, true);
  return { tx: window.__sb.txInst, src: window.__sb.srcInst, long: window.__sb.longInst };
}
"""


def _js_round(x):
    """JS Math.round semantics (half up, toward +inf) for the dx -> index check."""
    return math.floor(x + 0.5)


def check_scrub_decoupling(page):
    """5H: a scripted 30-step drag decouples the tape UI from the map render. The tape
    transform writes on every delivered move, overlay src swaps stay <= 12, no long task
    (>50 ms) lands inside the drag, and pointerup snaps to the exact final index/pill."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    if page.get_attribute("#h-24h", "aria-pressed") != "true":
        page.click("#h-24h")
        page.wait_for_function(
            "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
            timeout=60000)
        page.wait_for_timeout(300)

    # Known start: Home -> frame 0, then wait out the 320 ms tape glide.
    page.focus("#track")
    page.keyboard.press("Home")
    page.wait_for_timeout(500)

    # Warm-up (throwaway, same as the bench): JIT + a few cache entries so the measured
    # drag is not dominated by the first cold build.
    tl = page.evaluate(
        "() => { var r = document.getElementById('timeline').getBoundingClientRect();"
        " return { cx: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width }; }")
    page.mouse.move(tl["cx"], tl["y"])
    page.mouse.down()
    for k in range(1, 31):
        page.mouse.move(tl["cx"] - 8 * k, tl["y"])
    page.mouse.up()
    page.wait_for_timeout(300)
    page.focus("#track")
    page.keyboard.press("Home")
    page.wait_for_timeout(500)

    # Instrumentation is installed only after warm-up so its counters cover the drag alone.
    inst = page.evaluate(SCRUB_INSTR)
    tl = page.evaluate(
        "() => { var r = document.getElementById('timeline').getBoundingClientRect();"
        " return { cx: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width }; }")
    n = int(page.get_attribute("#track", "aria-valuemax")) + 1
    pxf = (330.0 if n == 672 else max(550.0, round(tl["w"]))) / 96.0
    start_idx = int(page.get_attribute("#track", "aria-valuenow"))

    cx, ty = tl["cx"], tl["y"]
    step = 8  # 30 steps * 8 px = 240 px, dragging LEFT = forward in time
    page.mouse.move(cx, ty)
    page.mouse.down()
    for k in range(1, 31):
        page.mouse.move(cx - step * k, ty)
    page.wait_for_timeout(80)
    during = page.evaluate(
        "() => ({ tx: window.__sb.tx, moves: window.__sb.moves, swaps: window.__sb.swaps,"
        " long: window.__sb.long.slice(), downX: window.__sb.downX, lastX: window.__sb.lastX })")
    page.mouse.up()
    page.wait_for_timeout(400)
    after = page.evaluate(
        "() => ({ idx: parseInt(document.getElementById('track').getAttribute('aria-valuenow'), 10),"
        " pill: document.getElementById('time-pill').textContent,"
        " hour: document.body.dataset.hour })")

    dx = during["lastX"] - during["downX"]
    expected = max(0, min(n - 1, _js_round(start_idx - dx / pxf)))
    a_ok = during["swaps"] <= 12
    b_ok = during["tx"] >= during["moves"]
    long_max = max(during["long"]) if during["long"] else 0
    c_ok = long_max <= 50
    d_ok = after["idx"] == expected
    pill_expected = format_chicago_pill(after["hour"]) if after["hour"] else ""
    e_ok = after["pill"] == pill_expected
    instruments = bool(inst["tx"]) and bool(inst["src"]) and bool(inst["long"])
    ok = instruments and a_ok and b_ok and c_ok and d_ok and e_ok
    print("        drag: moves=%d tx=%d swaps=%d long=%s downX=%.1f lastX=%.1f dx=%.1f"
          % (during["moves"], during["tx"], during["swaps"], during["long"],
             during["downX"] or 0.0, during["lastX"] or 0.0, dx))
    print("        final: idx=%d expected=%d start=%d pxf=%.4f pill='%s' expected='%s' hour=%s"
          % (after["idx"], expected, start_idx, pxf, after["pill"], pill_expected, after["hour"]))
    record(17, "scrub decoupling (5H)", ok,
           "moves=%d tx>=moves=%s swaps=%d<=12=%s long-max=%d<=50=%s "
           "idx=%d expected=%d=%s pill=%s instruments(tx/src/long)=%s/%s/%s"
           % (during["moves"], b_ok, during["swaps"], a_ok, long_max, c_ok,
              after["idx"], expected, d_ok, e_ok,
              inst["tx"], inst["src"], inst["long"]))


def capture_shots(page):
    """Done-when 3: phone-viewport screenshots with the deck visible at the frame bottom."""
    def shot(name):
        page.screenshot(path=str(SHOTS / name))

    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(500)
    shot("24h.png")
    page.set_viewport_size({"width": 360, "height": 800})
    page.wait_for_timeout(500)
    shot("24h-360.png")
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    page.click("#h-7d")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '671'",
        timeout=60000)
    page.wait_for_timeout(700)
    shot("7d.png")
    # 5G: scrub to the middle of the 7-day tape so the sheet shows it scrolled with the
    # reticle still centred (two full-width drags left = forward in time).
    tl7 = page.evaluate(
        "() => { var r = document.getElementById('timeline').getBoundingClientRect();"
        " return {x: r.x, w: r.width, y: r.y + r.height / 2}; }")
    for _ in range(2):
        page.mouse.move(tl7["x"] + tl7["w"] - 6, tl7["y"])
        page.mouse.down()
        page.mouse.move(tl7["x"] + 6, tl7["y"], steps=10)
        page.mouse.up()
        page.wait_for_timeout(100)
    page.wait_for_timeout(400)
    shot("tape-7d.png")
    page.click("#h-24h")
    page.wait_for_function(
        "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
        timeout=60000)
    page.wait_for_timeout(400)
    tl = page.evaluate(
        "() => { var r = document.getElementById('timeline').getBoundingClientRect();"
        " return {x: r.x + 0.25 * r.width, y: r.y + 24, x2: r.x + 0.72 * r.width}; }")
    page.mouse.move(tl["x"], tl["y"])
    page.mouse.down()
    page.mouse.move(tl["x2"], tl["y"], steps=8)
    page.wait_for_timeout(200)
    shot("scrub.png")
    page.mouse.up()


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
# [19] Stage 6C: marine header verification (src-free, route-stubbed)
# --------------------------------------------------------------------------- #
S6_SHOTS = ROOT / "tmp" / "s6-shots"
S6_SHOTS.mkdir(parents=True, exist_ok=True)
S6_LAKE_LAT, S6_SHORE_LAT = 46.22, 46.13
# Host set observed on a clean boot: the dual-location ingest must not add a
# second weather host (see STAGE-6-RECEIPTS for the observation).
S6_HOSTS_OK = {"127.0.0.1", "api.open-meteo.com", "tile.openstreetmap.org", "unpkg.com"}
# Row order is Shore / Lake / Gust (the spec's "normal (8/17/24)" reads shore/lake/gust).
S6_STATES = {
    "normal": {"lake": 17.0, "shore": 8.0, "gust": 24.0},
    "wide": {"lake": 27.0, "shore": 12.0, "gust": 38.0},
    "calm": {"lake": 4.0, "shore": 3.0, "gust": 6.0},
}

S6_GEOMETRY_JS = r"""
() => {
  // Null-safe: a missing id is NAMED in `missing` and its rect is null, so the
  // gate reports the element instead of throwing (stage 6C hardening).
  const missing = [];
  const R = (el, label) => { if (!el) { missing.push(label || '?'); return null; }
    const r = el.getBoundingClientRect();
    return {x:+r.x.toFixed(2), y:+r.y.toFixed(2), w:+r.width.toFixed(2), h:+r.height.toFixed(2),
            top:+r.top.toFixed(2), bottom:+r.bottom.toFixed(2), right:+r.right.toFixed(2)}; };
  const g = (id) => { const el = document.getElementById(id);
    if (!el) { missing.push('#' + id); } return el; };
  const header = document.querySelector('header');
  if (!header) { missing.push('header'); }
  const hr = R(header, 'header');
  const three = g('three');
  const kids = three ? Array.from(three.children) : [];
  const el0 = kids.length ? R(kids[0], 'row-first') : null;
  const elN = kids.length ? R(kids[kids.length - 1], 'row-last') : null;
  const ink = (el0 && elN) ? +(elN.right - el0.x).toFixed(2) : null;
  const cs3 = three ? getComputedStyle(three) : null;
  const avail = three ? +(three.clientWidth - (parseFloat(cs3.paddingLeft) || 0)
                  - (parseFloat(cs3.paddingRight) || 0)).toFixed(2) : null;
  const pills = ['pill-shore', 'pill-lake', 'pill-gust'].map(function (id) {
    const el = g(id), r = R(el, '#' + id);
    return {id: id, r: r, bg: el ? getComputedStyle(el).backgroundColor : null,
            inside: !!(r && hr && r.top >= hr.top - 0.01 && r.bottom <= hr.bottom + 0.01 &&
                    r.x >= hr.x - 0.01 && r.right <= hr.right + 0.01)};
  });
  const styles = {};
  ['shore','shore-u','lake','lake-u','gust','gust-u','mph','dot','help'].forEach(function (id) {
    const el = g(id);
    if (!el) { styles[id] = null; return; }
    const s = getComputedStyle(el);
    styles[id] = {color: s.color, fontSize: s.fontSize, fontWeight: s.fontWeight,
                  fontVariantNumeric: s.fontVariantNumeric, fontFamily: s.fontFamily};
  });
  const hs = header ? getComputedStyle(header) : null;
  const help = R(g('help'), '#help'), refresh = R(g('refresh'), '#refresh');
  const mph = R(g('mph'), '#mph');
  const mapR = R(g('map'), '#map');
  const horizon = R(g('horizon'), '#horizon'), badge = R(g('wind-badge'), '#wind-badge');
  return {
    missing: missing,
    header: header ? {r: hr, clientHeight: header.clientHeight, scrollHeight: header.scrollHeight} : null,
    headerStyle: hs ? {backdropFilter: hs.backdropFilter || hs.webkitBackdropFilter,
                  zIndex: hs.zIndex, background: hs.backgroundColor,
                  position: hs.position, fontFamily: hs.fontFamily} : null,
    three: three ? {r: R(three, '#three'), scrollWidth: three.scrollWidth,
            clientWidth: three.clientWidth, ink: ink, avail: avail} : null,
    mph: mph ? {r: mph, text: document.getElementById('mph').textContent,
          scrollWidth: document.getElementById('mph').scrollWidth,
          clientWidth: document.getElementById('mph').clientWidth} : null,
    pills: pills, pillsInside: pills.length > 0 && pills.every(function (p) { return p.inside; }),
    help: help, refresh: refresh,
    helpGap: (help && refresh) ? +(refresh.x - help.right).toFixed(2) : null,
    map: mapR, overlaps: !!(hr && mapR && hr.bottom > mapR.top && hr.top < mapR.bottom),
    horizonClear: (horizon && hr) ? +(horizon.top - hr.bottom).toFixed(2) : null,
    badgeClear: (badge && hr) ? +(badge.top - hr.bottom).toFixed(2) : null,
    styles: styles,
    lakeText: g('lake') ? document.getElementById('lake').textContent : null,
    shoreText: g('shore') ? document.getElementById('shore').textContent : null,
    gustText: g('gust') ? document.getElementById('gust').textContent : null
  };
}
"""

S6_CONTRAST_JS = r"""
() => {
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const L = (rgb) => 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
  const parse = (s) => { const m = s.match(/[\d.]+/g).map(Number); return {rgb: m.slice(0, 3), a: m.length > 3 ? m[3] : 1}; };
  const over = (fg, bg) => fg.rgb.map((c, i) => c * fg.a + bg[i] * (1 - fg.a));
  const ratio = (a, b) => { const l1 = L(a), l2 = L(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
  const cs = getComputedStyle(document.querySelector('header'));
  const GLASS = over(parse(cs.backgroundColor), [20, 40, 59]);
  const pills = {};
  ['pill-shore', 'pill-lake', 'pill-gust'].forEach(function (id) {
    pills[id] = over(parse(getComputedStyle(document.getElementById(id)).backgroundColor), GLASS);
  });
  const P = (id) => parse(getComputedStyle(document.getElementById(id)).color).rgb;
  const out = {};
  out['#lake numeral vs #pill-lake'] = ratio(P('lake'), pills['pill-lake']);
  out['#shore numeral vs #pill-shore'] = ratio(P('shore'), pills['pill-shore']);
  out['#gust numeral vs #pill-gust'] = ratio(P('gust'), pills['pill-gust']);
  out['#lake-u label vs #pill-lake'] = ratio(P('lake-u'), pills['pill-lake']);
  out['#shore-u label vs #pill-shore'] = ratio(P('shore-u'), pills['pill-shore']);
  out['#gust-u label vs #pill-gust'] = ratio(P('gust-u'), pills['pill-gust']);
  out['#mph unit vs header glass'] = ratio(P('mph'), GLASS);
  out['#dot vs header glass'] = ratio(P('dot'), GLASS);
  out['#arrow vs header glass'] = ratio(P('arrow'), GLASS);
  out['#help glyph vs header glass'] = ratio(P('help'), GLASS);
  const keys = Object.keys(out);
  const min = Math.min.apply(null, keys.map((k) => out[k]));
  return {ratios: out, min: +min.toFixed(2), minPair: keys.filter((k) => out[k] === min)[0]};
}
"""

S6_POPOVER_JS = r"""
() => {
  // Null-safe by construction: a probe must never throw in a page.evaluate — it
  // reports which element was missing instead (stage 6C: a navigation mid-check
  // used to null the whole document and abort the group).
  const missing = [];
  const need = (id) => {
    const el = document.getElementById(id);
    if (!el) { missing.push('#' + id); }
    return el;
  };
  const rectOf = (el, label) => {
    if (!el) { missing.push(label); return null; }
    const r = el.getBoundingClientRect();
    return {top: +r.top.toFixed(2), bottom: +r.bottom.toFixed(2), left: +r.left.toFixed(2),
            right: +r.right.toFixed(2), width: +r.width.toFixed(2), height: +r.height.toFixed(2)};
  };
  const el = need('help-pop');
  const header = document.querySelector('header');
  if (!header) { missing.push('header'); }
  const help = need('help');
  const er = rectOf(el, '#help-pop');
  const hr = rectOf(header, 'header rect');
  return {missing: missing,
          hidden: el ? el.hidden : null,
          parent: el && el.parentElement ? el.parentElement.tagName : null,
          prev: el && el.previousElementSibling ? el.previousElementSibling.tagName : null,
          aria: help ? help.getAttribute('aria-expanded') : null,
          focus: document.activeElement ? document.activeElement.id : null,
          rect: er, top: er ? er.top : null, bottom: er ? er.bottom : null,
          headerBottom: hr ? hr.bottom : null};
}
"""

S6_IDENTITY_JS = r"""
async () => {
  const res = await fetch('src/wind.js');
  const src = await res.text();
  const mod = {exports: {}};
  new Function('module', 'exports', 'require', src)(mod, mod.exports,
    function (req) { throw new Error('harness require ' + req); });
  const data = await mod.exports.ingest({horizon: '24h'});
  const idx = Number(document.getElementById('track').getAttribute('aria-valuenow'));
  return {idx: idx, dayLen: data.day.length,
          shoreLen: data.shoreDay ? data.shoreDay.length : null,
          day: data.day[idx] ? data.day[idx].speedMph : null,
          shore: data.shoreDay ? data.shoreDay[idx].speedMph : null,
          gust: data.day[idx] ? data.day[idx].gustMph : null};
}
"""


def _s6_series(today, lake, shore, gust, varying=False):
    """A crafted Open-Meteo paired response: [lake, shore], 8 local days of hourly
    samples (past day inclusive) so today always slices to 96 15-min frames."""
    start = today - timedelta(days=1)
    n = 8 * 24
    times, ls, ld, lg, ss, sd, sg = [], [], [], [], [], [], []
    for i in range(n):
        d = start + timedelta(days=i // 24)
        h = i % 24
        times.append("%04d-%02d-%02dT%02d:00" % (d.year, d.month, d.day, h))
        if varying:
            lv, sv, gv = 11.0 + (i % 19), 8.0 + (i % 3), 15.0 + (i % 20)
        else:
            lv, sv, gv = lake, shore, gust
        ls.append(lv); ld.append(270.0); lg.append(gv)
        ss.append(sv); sd.append(250.0); sg.append(gv)
    units = {"wind_speed_10m": "mph", "wind_gusts_10m": "mph",
             "wind_direction_10m": "deg", "time": "iso8601"}

    def loc(lat, lon, sp, dr, gu):
        return {"latitude": lat, "longitude": lon, "timezone": "America/Chicago",
                "hourly_units": units,
                "hourly": {"time": times, "wind_speed_10m": sp,
                           "wind_direction_10m": dr, "wind_gusts_10m": gu}}
    return [loc(S6_LAKE_LAT, -93.657, ls, ld, lg),
            loc(S6_SHORE_LAT, -93.57, ss, sd, sg)]


def _s6_eq(dom_text, value):
    try:
        return str(int(round(float(value)))) == str(dom_text).strip()
    except (TypeError, ValueError):
        return False


def check_marine_header(pw, port):
    """Stage 6C [19]: drive the shipped marine header from crafted dual-location
    responses (route-intercepted) and verify geometry, typography, contrast,
    identity, jitter, network shape, popover plumbing and the missing-shore path."""
    base = "http://127.0.0.1:%d/index.html" % port
    today = datetime.now(CHICAGO).date()
    vps = ((360, 800), (390, 844))
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 800}, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    requests = []
    page.on("pageerror", lambda e: errors.append("pageerror: %s" % e))
    page.on("console", lambda m: errors.append("console: %s" % m.text) if m.type == "error" else None)
    page.on("request", lambda r: requests.append((urlparse(r.url).hostname or "", r.url)))
    holder = {"body": None}

    def route_wind(route):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(holder["body"]))
    page.route("**/api.open-meteo.com/**", route_wind)

    def load(body):
        holder["body"] = body
        page.goto(base, wait_until="domcontentloaded")
        page.wait_for_function(
            "() => { var p = document.getElementById('time-pill');"
            " return !!p && p.textContent.trim() !== '\u2014' &&"
            " document.getElementById('track-days').children.length >= 1; }",
            timeout=120000)
        page.wait_for_timeout(450)

    def view(w, h):
        page.set_viewport_size({"width": w, "height": h})
        page.wait_for_timeout(400)

    all_ok = [True]
    fails = []

    def emit(ok, line, tag=None):
        if not ok:
            all_ok[0] = False
            fails.append(tag or line.split()[0])
        print("        19 %s" % line, flush=True)
        return ok

    def gate(num, label, fn, *args):
        """Run one numbered gate; an exception (Playwright / Python / a probe that
        could not read a destroyed document) fails ONLY that gate and the group
        keeps going.  Never a silent pass: an exception is always a FAIL."""
        try:
            return fn(*args)
        except Exception as exc:  # noqa: BLE001 - QA records, never aborts
            emit(False, "[%s] %s EXCEPTION %s: %s"
                 % (num, label, type(exc).__name__, str(exc).splitlines()[0]))
            return None

    geos = {}

    def layout_block(name, w, h):
        view(w, h)
        geo = page.evaluate(S6_GEOMETRY_JS)
        con = page.evaluate(S6_CONTRAST_JS)
        geos[(name, w)] = geo
        if geo["missing"]:
            emit(False, "[19.probe] %s @%dx%d MISSING ELEMENTS %s"
                 % (name, w, h, geo["missing"]))
        hd, three, mph, st = geo["header"], geo["three"], geo["mph"], geo["styles"]
        emit(hd is not None and abs(hd["r"]["h"] - 72.0) < 0.005
             and hd["scrollHeight"] == hd["clientHeight"],
             "[19.1] %s @%dx%d header_h=%s scrollH=%s clientH=%s"
             % (name, w, h, hd and hd["r"]["h"], hd and hd["scrollHeight"],
                hd and hd["clientHeight"]))
        emit(three is not None and mph is not None
             and three["scrollWidth"] <= three["clientWidth"] and mph["r"]["w"] >= 19.0,
             "[19.2] %s @%dx%d #three sw=%s cw=%s mph_w=%s (>=19)"
             % (name, w, h, three and three["scrollWidth"], three and three["clientWidth"],
                mph and mph["r"]["w"]))
        slack = (three["avail"] - three["ink"]) if (three and three["ink"] is not None
                 and three["avail"] is not None) else None
        emit(three is not None and three["ink"] is not None and three["avail"] is not None
             and three["ink"] <= three["avail"],
             "[19.3] %s @%dx%d ink=%s avail=%s slack=%s"
             % (name, w, h, three and three["ink"], three and three["avail"], slack))
        emit(geo["pillsInside"] and geo["help"] and geo["help"]["w"] >= 44.0
             and geo["help"]["h"] >= 44.0 and geo["helpGap"] is not None
             and geo["helpGap"] >= 8.0,
             "[19.4] %s @%dx%d pills-inside=%s help=%sx%s gap=%s"
             % (name, w, h, geo["pillsInside"],
                geo["help"] and geo["help"]["w"], geo["help"] and geo["help"]["h"],
                geo["helpGap"]))
        styles_present = all(st.get(k) for k in ("shore", "lake", "gust", "shore-u", "lake-u", "gust-u"))
        nums_ok = styles_present and all(st[k]["fontSize"] == "13px" and st[k]["fontWeight"] == "700"
                      and st[k]["fontVariantNumeric"] == "tabular-nums"
                      for k in ("shore", "lake", "gust"))
        labels_ok = styles_present and all(st[k]["fontSize"] == "10px"
                                          for k in ("shore-u", "lake-u", "gust-u"))
        font_ok = styles_present and all(t in st["lake"]["fontFamily"]
                                         for t in ("Inter", "Roboto", "sans-serif"))
        emit(nums_ok and labels_ok and font_ok,
             "[19.5] %s @%dx%d numerals=%s/%s/%s labels=%s font=%s"
             % (name, w, h, st.get("lake") and st["lake"]["fontSize"],
                st.get("lake") and st["lake"]["fontWeight"],
                st.get("lake") and st["lake"]["fontVariantNumeric"],
                st.get("lake-u") and st["lake-u"]["fontSize"],
                st.get("lake") and st["lake"]["fontFamily"]))
        emit(con["min"] >= 4.5,
             "[19.6] %s @%dx%d contrast min=%.2f:1 (%s) pairs=%s"
             % (name, w, h, con["min"], con["minPair"],
                " ".join("%s=%.2f" % (k.split()[0], v) for k, v in con["ratios"].items())))

    # ---- gates 1-6: normal / wide / calm, both viewports -------------------
    for name in ("normal", "wide", "calm"):
        cfg = S6_STATES[name]
        if name == "normal":
            requests[:] = []
        load(_s6_series(today, cfg["lake"], cfg["shore"], cfg["gust"]))
        if name == "normal":
            boot = list(requests)
            om = [u for hh, u in boot if hh == "api.open-meteo.com"]

            def gate8():
                hosts = sorted(set(hh for hh, _ in boot))
                both = bool(om) and ("46.22" in om[0] and "46.13" in om[0])
                emit(len(om) == 1 and both and set(hosts) <= S6_HOSTS_OK,
                     "[19.8] normal @boot open-meteo=%d url-has-both-lats=%s hosts=%s unexpected=%s"
                     % (len(om), both, hosts, sorted(set(hosts) - S6_HOSTS_OK) or "none"))
            gate("19.8", "network shape", gate8)
            for w, h in vps:
                def gate9(w=w, h=h):
                    view(w, h)
                    ident = page.evaluate(S6_IDENTITY_JS)
                    dom_lake = page.evaluate("() => document.getElementById('lake').textContent")
                    dom_shore = page.evaluate("() => document.getElementById('shore').textContent")
                    emit(ident["day"] is not None and ident["shore"] is not None
                         and _s6_eq(dom_lake, ident["day"]) and _s6_eq(dom_shore, ident["shore"]),
                         "[19.9] identity @%dx%d idx=%s day[idx]=%s shoreDay[idx]=%s "
                         "DOM lake='%s' shore='%s' lake-match=%s shore-match=%s"
                         % (w, h, ident["idx"], ident["day"], ident["shore"], dom_lake, dom_shore,
                            _s6_eq(dom_lake, ident["day"]), _s6_eq(dom_shore, ident["shore"])))
                gate("19.9", "identity", gate9)
        for w, h in vps:
            gate("layout@%dx%d" % (w, h), "layout @%dx%d" % (w, h), layout_block, name, w, h)
            if name == "normal":
                page.screenshot(path=str(S6_SHOTS / ("header-%d.png" % w)))
            if name == "wide" and w == 360:
                page.screenshot(path=str(S6_SHOTS / "wide-360.png"))

    # ---- gate 12: overlay / blur / clearance -------------------------------
    def gate12():
        g0 = geos[("normal", 360)]
        render_src = (ROOT / "src/render.js").read_text()
        hs = g0["headerStyle"]
        emit(hs is not None and hs["backdropFilter"] == "blur(8px)"
             and hs["zIndex"] is not None and int(float(hs["zIndex"])) >= 1001 and g0["overlaps"]
             # 6B.2: the top padding is now computed from the LIVE header band
             # (72 px of content + notch inset) instead of a hard-coded 84 px.
             and "headerBand() + 12" in render_src
             and g0["horizonClear"] is not None and g0["horizonClear"] >= 12.0
             and g0["badgeClear"] is not None and g0["badgeClear"] >= 12.0,
             "[19.12] overlay backdropFilter=%s zIndex=%s overlaps-map=%s fit-padding-dynamic=%s "
             "horizon-clearance=%s badge-clearance=%s"
             % (hs and hs["backdropFilter"], hs and hs["zIndex"], g0["overlaps"],
                "headerBand() + 12" in render_src, g0["horizonClear"], g0["badgeClear"]))
    gate("19.12", "overlay/blur", gate12)

    # ---- gate 7: jitter on a varying frame series --------------------------
    def gate7():
        load(_s6_series(today, 11.0, 8.0, 15.0, varying=True))
        for w, h in vps:
            view(w, h)
            page.focus("#track")
            page.keyboard.press("Home")
            page.wait_for_timeout(500)
            samples = []
            for _ in range(24):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(40)
                samples.append(page.evaluate(
                    "() => ({lake: document.getElementById('lake').textContent,"
                    " w: document.getElementById('pill-lake').getBoundingClientRect().width,"
                    " rowRight: document.getElementById('three').getBoundingClientRect().right,"
                    " refreshLeft: document.getElementById('refresh').getBoundingClientRect().left})"))
            deltas = [abs(samples[i]["w"] - samples[i - 1]["w"]) for i in range(1, len(samples))
                      if len(samples[i]["lake"]) == len(samples[i - 1]["lake"])]
            maxd = max(deltas) if deltas else 0.0
            cross = any(s["rowRight"] > s["refreshLeft"] for s in samples)
            emit(bool(deltas) and maxd <= 0.5 and not cross,
                 "[19.7] jitter @%dx%d frames=%d equal-digit-pairs=%d max-lake-delta=%.2fpx "
                 "row-crosses-refresh=%s lakes=%s"
                 % (w, h, len(samples), len(deltas), maxd, cross,
                    ",".join(s["lake"] for s in samples)))
    gate("19.7", "jitter", gate7)

    # ---- gate 10: popover with real clicks + pin/card guard ---------------
    def gate10():
        load(_s6_series(today, 17.0, 8.0, 24.0))
        for w, h in vps:
            view(w, h)
            opened = page.evaluate(
                "() => { var r = window.__bpcTap(46.23846, -93.64229);"
                " return {ret: !!r, hidden: document.getElementById('card').hidden}; }")
            pins0 = page.evaluate("() => document.querySelectorAll('#map .leaflet-overlay-pane path').length")
            page.click("#help")
            page.wait_for_timeout(150)
            p1 = page.evaluate(S6_POPOVER_JS)
            open_ok = (p1["missing"] == [] and not p1["hidden"] and p1["aria"] == "true"
                       and p1["parent"] == "BODY" and p1["prev"] == "HEADER"
                       and p1["top"] is not None and p1["headerBottom"] is not None
                       and p1["top"] >= p1["headerBottom"] - 0.5
                       and p1["bottom"] > 72.0)
            card_open = not page.evaluate("() => document.getElementById('card').hidden")
            if w == 360:
                page.screenshot(path=str(S6_SHOTS / "popover-360.png"))
            page.click("#help-pop", position={"x": 30, "y": 20})
            page.wait_for_timeout(120)
            p_in = page.evaluate(S6_POPOVER_JS)
            inner_ok = (not p_in["hidden"]) and not page.evaluate(
                "() => document.getElementById('card').hidden")
            pins1 = page.evaluate("() => document.querySelectorAll('#map .leaflet-overlay-pane path').length")
            page.click("#help")
            page.wait_for_timeout(120)
            p2 = page.evaluate(S6_POPOVER_JS)
            close_ok = p2["hidden"] and p2["aria"] == "false" and p2["focus"] == "help"
            page.click("#help")
            page.wait_for_timeout(100)
            page.keyboard.press("Escape")
            page.wait_for_timeout(120)
            p3 = page.evaluate(S6_POPOVER_JS)
            esc_ok = p3["hidden"] and p3["aria"] == "false" and p3["focus"] == "help"
            # dismiss the card, then prove an outside map tap closes the popover.
            # 6C fix: the old point (w//2, h-140) = (180, 660) landed on Leaflet's
            # attribution <a href="https://leafletjs.com/"> and NAVIGATED the page
            # away, which destroyed the context and crashed the whole group.  Pick a
            # bare map point that is provably not a link or control.
            page.click("#card-close")
            page.wait_for_timeout(120)
            page.click("#help")
            page.wait_for_timeout(100)
            tap = page.evaluate(
                "([w, hMax]) => { for (var y = 300; y <= hMax; y += 20) {"
                "  var e = document.elementFromPoint(Math.round(w / 2), y);"
                "  if (e && !e.closest('a') && !e.closest('button')"
                "      && !e.closest('.leaflet-control'))"
                "    return {x: Math.round(w / 2), y: y}; } return null; }",
                [w, h - 40])
            if not tap:
                emit(False, "[19.10] popover @%dx%d NO BARE MAP POINT FOUND for the outside tap" % (w, h))
                continue
            page.mouse.click(tap["x"], tap["y"])
            page.wait_for_timeout(150)
            p4 = page.evaluate(S6_POPOVER_JS)
            out_ok = p4["missing"] == [] and p4["hidden"] and p4["aria"] == "false" and p4["focus"] == "help"
            emit(opened["ret"] and not opened["hidden"] and open_ok and card_open and inner_ok
                 and pins1 == pins0 and close_ok and esc_ok and out_ok,
                 "[19.10] popover @%dx%d pin-opened=%s chip-open(hidden=%s aria=%s sibling=%s prev=%s "
                 "top=%s bottom=%s>72) inside-keeps-card=%s pins=%d==%d escape(hidden=%s aria=%s focus=%s) "
                 "outside-tap@%s,%s(hidden=%s aria=%s focus=%s missing=%s)"
                 % (w, h, opened["ret"], p1["hidden"], p1["aria"], p1["parent"] == "BODY",
                    p1["prev"], p1["top"], p1["bottom"], inner_ok, pins1, pins0, p3["hidden"],
                    p3["aria"], p3["focus"], tap["x"], tap["y"], p4["hidden"],
                    p4["aria"], p4["focus"], p4["missing"]))
    gate("19.10", "popover", gate10)

    # ---- gate 11: missing shore (single-object response) ------------------
    def gate11():
        err0 = len(errors)
        single = _s6_series(today, 17.0, 8.0, 24.0)[0]
        load(single)
        for w, h in vps:
            view(w, h)
            v = page.evaluate(
                "() => ({shore: document.getElementById('shore').textContent,"
                " lake: document.getElementById('lake').textContent,"
                " h: document.querySelector('header').getBoundingClientRect().height})")
            ne = len(errors) - err0
            emit(v["shore"] == "\u2014" and _s6_eq(v["lake"], 17.0) and abs(v["h"] - 72.0) < 0.005
                 and ne == 0,
                 "[19.11] shore-missing @%dx%d #shore='%s' #lake='%s' header=%.2f new-console-errors=%d"
                 % (w, h, v["shore"], v["lake"], v["h"], ne))
    gate("19.11", "shore-missing", gate11)

    page.close()
    ctx.close()
    browser.close()
    record(19, "6 marine header", all_ok[0],
           "all gates ok=%s%s" % (all_ok[0], "" if all_ok[0] else " failing=%s" % fails))


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    for stale in SHOTS.glob("*.png"):
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
            safe(15, "deck geometry (5F)", check_deck_geometry, page)
            safe(16, "tape architecture (5G)", check_tape_architecture, page)
            safe(17, "scrub decoupling (5H)", check_scrub_decoupling, page)
            safe(2, "frame base", check_frame_base, page)
            # 5D.2: the boot skeleton hides on every first paint again, so [2b] runs in
            # its spec position ([2], per the 5E spec) and the map-tap group below
            # regression-tests the fix (it would deadlock on a stuck skeleton).
            safe("2b", "horizon ceiling", check_horizon_ceiling, page)
            safe(3, "header layout", check_header, page, names)
            safe(4, "tier chip", check_tier, page)
            safe(5, "clock", check_clock, page)
            safe(6, "compass badge", check_compass, page, gamma)
            safe("7a", "ramp location", check_ramp_location, page)
            safe(7, "touch", check_card_and_touch, page, warp)
            safe("7b", "touch ergonomics", check_touch_ergonomics, page)
            safe(18, "timeline labels (5L)", check_timeline_labels, page)
            safe(19, "6 marine header", check_marine_header, pw, port)
            safe(9, "playback perf", check_playback, page, warp)
            now_ups = safe(10, "radar smoothing", check_smoothing, page, meta, warp)
            if now_ups:
                safe(11, "before/after", check_before_after, pw, now_ups, warp)
            safe(13, "lazy 7d compute", check_lazy_7d, page)
            safe("15.1", "screenshots", capture_shots, page)
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
    print("screenshots: %s" % ", ".join(sorted(p.name for p in SHOTS.glob("*.png"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
