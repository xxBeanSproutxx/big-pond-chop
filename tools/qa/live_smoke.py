#!/usr/bin/env python3
"""Live production smoke — big-pond-chop (orchestrator tool, stage 5F).

Drives the DEPLOYED site (GitHub Pages) in headless Chromium at a phone viewport and
checks the things a build green-light cannot: the assets really serve, the deck is the
two-row Windy deck, the amber pill is permanent, and widening to 7 day works live.

Run:  /home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/live_smoke.py [--url URL]
Exit 0 always (findings, not crashes) — read the printed SUMMARY line.
"""
import argparse
import sys

URL = "https://xxbeansproutxx.github.io/big-pond-chop/"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright missing in this interpreter", file=sys.stderr)
        return 1

    results = []
    def rec(name, ok, detail=""):
        results.append(ok)
        print("%-24s %s   %s" % (name, "ok  " if ok else "FAIL", detail))

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(args.url, wait_until="load", timeout=60000)
        # `aria-valuemax="95"` is static markup, so it is NOT a readiness signal —
        # wait for rendered data: a real pill timestamp and at least one day block.
        page.wait_for_function(
            "() => { var p = document.getElementById('time-pill');"
            " return !!p && p.textContent.trim() !== '\u2014' &&"
            " document.getElementById('track-days').children.length >= 1; }",
            timeout=120000)

        v = page.evaluate("""() => {
            const deck = document.getElementById('deck').getBoundingClientRect();
            const track = document.getElementById('track').getBoundingClientRect();
            const tl = document.getElementById('timeline').getBoundingClientRect();
            const play = document.getElementById('play').getBoundingClientRect();
            const pill = document.getElementById('time-pill');
            const pr = pill.getBoundingClientRect();
            const blocks = Array.from(document.getElementById('track-days').children);
            return {deckH: deck.height, trackH: track.height, tlH: tl.height,
                    pillText: pill.textContent, pillHidden: pill.hasAttribute('hidden'),
                    pillVisible: pr.width > 0 && pr.height > 0,
                    pillAboveBar: pr.bottom <= tl.top + 12,
                    pillCentred: Math.abs((pr.x + pr.width / 2) - (tl.x + tl.width / 2)) <= 1,
                    playOverlay: play.x >= track.x - 1 && (play.x - track.x) <= 56 &&
                                 Number(getComputedStyle(document.getElementById('play')).zIndex) >= 10,
                    tapeW: document.getElementById('track-tape').getBoundingClientRect().width,
                    tapeInTimeline: document.getElementById('track-tape').parentElement
                                    === document.getElementById('timeline'),
                    blocks: blocks.length,
                    header: blocks.length ? blocks[0].querySelector('.day-head').textContent : '',
                    subs: blocks.length
                      ? Array.from(blocks[0].querySelectorAll('.day-sub')).map(s => s.textContent)
                      : [],
                    winds: blocks.length
                      ? Array.from(blocks[0].querySelectorAll('.day-wind')).map(s => s.textContent)
                      : [],
                    absent: !document.querySelector('.deck-main') && !document.getElementById('playhead')
                            && !document.getElementById('track-rail') && !document.getElementById('track-progress'),
                    version: (window.__bpc || {})};
        }""")
        rec("deck two-row", 60 <= v["deckH"] <= 72 and v["absent"],
            "deckH=%.1f blocks=%d absent=%s" % (v["deckH"], v["blocks"], v["absent"]))
        rec("pill permanent", v["pillVisible"] and not v["pillHidden"] and bool(v["pillText"].strip()),
            "text='%s' hidden=%s above-bar=%s" % (v["pillText"], v["pillHidden"], v["pillAboveBar"]))
        rec("reticle centred", v["pillCentred"], "pill centre == timeline centre (<=1px)")
        rec("play pinned", v["playOverlay"], "play overlays the window's left edge, z-index>=10")
        rec("tape wired", v["tapeInTimeline"] and v["tapeW"] >= 300,
            "tape=%.0f px inside #timeline=%s" % (v["tapeW"], v["tapeInTimeline"]))
        rec("wind row", len(v["winds"]) == 8 and all(x.isdigit() for x in v["winds"]),
            "block0 .day-wind count=%d all-numeric=%s list=%s"
            % (len(v["winds"]), all(x.isdigit() for x in v["winds"]), v["winds"]))
        rec("day header", bool(v["header"].strip()), "block0 header='%s' subs=%s" % (v["header"], v["subs"]))

        page.click("#h-7d")
        page.wait_for_function(
            "() => document.getElementById('track').getAttribute('aria-valuemax') === '671'",
            timeout=60000)
        page.wait_for_timeout(600)
        w = page.evaluate("""() => {
            const blocks = Array.from(document.getElementById('track-days').children);
            const bgs = blocks.map(b => getComputedStyle(b).backgroundColor);
            return {n: blocks.length,
                    headers: blocks.map(b => b.querySelector('.day-head').textContent),
                    alternating: bgs.every((c, i) => i === 0 || c !== bgs[i - 1]),
                    subs: blocks.map(b => b.querySelectorAll('.day-sub').length),
                    tapeW: document.getElementById('track-tape').getBoundingClientRect().width,
                    boot: document.getElementById('boot').classList.contains('hidden')};
        }""")
        rec("7 day live", w["n"] == 7 and w["alternating"] and w["boot"] and 1100 <= w["tapeW"] <= 1400
            and all(c == 8 for c in w["subs"]),
            "blocks=%d alt=%s boot-hidden=%s tape=%.0f sub-labels=%s"
            % (w["n"], w["alternating"], w["boot"], w["tapeW"], w["subs"]))
        print("       headers: %s" % " | ".join(w["headers"]))

        page.click("#h-24h")
        page.wait_for_function(
            "() => document.getElementById('track').getAttribute('aria-valuemax') === '95'",
            timeout=60000)
        rec("back to 24 h", True, "aria-valuemax=95")
        rec("no page errors", not errors, "errors=%d %s" % (len(errors), errors[:3]))
        browser.close()

    print("\nSUMMARY: %d ok, %d FAIL  (%s)" % (sum(results), results.count(False), args.url))
    return 0

if __name__ == "__main__":
    sys.exit(main())
