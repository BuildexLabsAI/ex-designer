"""All checks of The Ex-Designer skill, on an invented two-brand site (tests/fixtures/code-site). Usage: python3 tests/run_all.py

1  colour maths: CIEDE2000 against Sharma's published test pairs, WCAG contrast, color-mix(), oklch(), hex, rgb()
2  tokens.py finds every planted trap: one colour as hex and as rgb(), an arbitrary Tailwind value, palette classes,
   a .dark block, a second brand and its dark mode, a near-duplicate grey, a hard-coded font, a font the docs name,
   a named one-off; and none of the decoys: a #fragment link, an SVG url(#id), an asset named with a hex code, an HTML
   entity, colours in comments and docs. tokens.json is DTCG 2025.10.
3  harness: every shot identical across 3 runs in fresh browsers, and across two separate runs
4  harness: 10 planted colour shifts of CIEDE2000 2 caught 10/10, each only on the brand and mode it reaches
5  the page that overflows sideways is caught at 390 px, and nothing else is flagged
6  no request leaves the machine: the 4 planted third-party requests are blocked and listed, the local server saw only
   the site's hosts, and Chrome resolves no host name
7  livecheck: SEO facts of the local build (status, slash redirect, canonical, hreflang, robots, sitemap, brands)
8  livecheck: proof of source: an identical copy compares equal; one changed byte and one changed canonical are caught
9  verify.py: an unchanged site passes; a brand token change passes on its host and fails when another host was
   expected; low contrast and a new hard-coded colour fail
10 the dummy key in the fixture appears in no output
11 no client data in src/ex-designer: the hashed denylist in tests/denylist.sha256 (tests/denylist.py) and e-mail
   addresses
12 edge cases: the CSS cascade (selector lists, a later declaration, !important, specificity), values that must not
   leak (an unreadable colour, a non-design value, a link to a secret file, a secret file as the token file),
   literal colours next to var(), font shorthand and local fonts, unique shot names, sitemap indexes, a set without
   a manifest
13 a local request ignores HTTP_PROXY; an unstable baseline shot fails verify
14 report.py: markers on each place's own element, every row of the all tab with its own marker, the dropped list,
   an area narrows every tab, no placeholder injection, only http(s) pages, third-party requests blocked and listed
15 brandbook.py on an invented brand (tests/fixtures/brand-work): read captures the copy of its pages and its brand
   files (hidden copies skipped, the head kept); the clean book passes every check and builds .md, .html (colour, type
   and logo specimens from the tokens) and .pdf with a clean furniture check and gate; each of 39 planted traps fails
   on its own rule only (colours and fonts not the brand's, written as entities or in lower case; facts without a
   source or with a quote not on the page; a mark with no fact, a claim with no mark, a quotation its fact does not
   hold; an inferred fact in the owner's chapter; missing or borrowed chapter content; dashes and banned words, also
   split by emphasis; dates, decision notes, a person deciding, internal paths; links to no kit file, links that run
   code, pictures from the network); the build refuses a failing book; a build that fails its final check leaves the
   kit as it was; a work file never ships; a note or an unreadable file put into the kit is caught
16 the newcomer test's scorer (tests/newcomer): the handover kit builds with a stable baseline; a right solution of
   the four jobs scores 4/4; a wrong one fails each job on its own rule (both brands' accent moved, a font hard-coded
   in a component and never rolled back, an answer not from systems.md); an uncommitted change fails jobs 1-3; a
   re-shot baseline fails job 1
Prints "CHECK <n> PASS|FAIL <detail>". Takes a few minutes: it opens Chrome a few hundred times.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SKILL = REPO / "src" / "ex-designer"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SKILL / "scripts"))
import fixture_server  # noqa: E402
import brandbook  # noqa: E402
import denylist  # noqa: E402
import diff  # noqa: E402
import livecheck  # noqa: E402
import shoot  # noqa: E402
import tokens  # noqa: E402
import verify  # noqa: E402
sys.path.insert(0, str(HERE / "newcomer"))
import newcomer  # noqa: E402
from lib import color as C  # noqa: E402
from lib.site import Site, fetch  # noqa: E402

FIXTURE = HERE / "fixtures" / "code-site"
OUT = HERE / "out"
KEY = "fixture_sk_9f8e7d6c5b4a39281706f5e4d3c2b1a0"
PAGES = ["/", "/about/", "/wide/"]
PLANTED = {"https://api.invalid/beacon", "https://cdn.invalid/pixel.gif", "redirect to https://1.1.1.1/away.png",
           "https://fonts.invalid/css2?family=Fixture+Grotesk", "https://tracker.invalid/t.js"}
COMBO = {"base": ("alpha.invalid", "light"), "dark": ("alpha.invalid", "dark"), "beta": ("beta.invalid", "light"),
         "beta/dark": ("beta.invalid", "dark")}
TRIALS = [("accent", ":root"), ("accent", '[data-brand="beta"]'), ("teal", ":root"), ("destructive", ":root"),
          ("background", ":root"), ("background", ".dark"), ("foreground", ":root"), ("foreground", ".dark"),
          ("muted-foreground", ":root"), ("surface", ".dark")]
RESULTS = []


def check(n, ok, detail):
    RESULTS.append(bool(ok))
    print(f"CHECK {n} {'PASS' if ok else 'FAIL'} {detail}", flush=True)


def check_color():
    sharma = [((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425), ((50, 3.1571, -77.2803), (50, 0, -82.7485), 2.8615),
              ((50, 2.8361, -74.02), (50, 0, -82.7485), 3.4412), ((50, 0, 0), (50, -1, 2), 2.3669),
              ((50, 2.5, 0), (73, 25, -18), 27.1492), ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
              ((2.0776, 0.0795, -1.135), (0.9033, -0.0636, -0.5514), 0.9082)]
    bad = [f"{a}/{b}: {C.de2000(a, b):.4f} not {want}" for a, b, want in sharma if abs(C.de2000(a, b) - want) > 1e-4]
    cases = [("#abc", "#aabbcc"), ("rgb(29 78 216 / 50%)", "#1d4ed880"), ("rgba(22, 22, 22, 0.12)", "#1616161f"),
             ("color-mix(in srgb, #4d9fff 14%, transparent)", "#4d9fff24"), ("hsl(0 0% 100%)", "#ffffff"),
             ("white", "#ffffff")]
    bad += [f"{css} -> {C.hex(C.parse(css)) if C.parse(css) else None}, not {want}" for css, want in cases
            if not C.parse(css) or C.hex(C.parse(css)) != want]
    ok_l = C.parse("oklch(0.708 0 0)")
    if not ok_l or max(abs(round(x * 255) - 0xA1) for x in ok_l[:3]) > 1:
        bad.append(f"oklch(0.708 0 0) -> {C.hex(ok_l) if ok_l else None}, not about #a1a1a1")
    for fg, bg, want in (("#767676", "#ffffff", 4.54), ("#000000", "#ffffff", 21.0)):
        got = round(C.contrast(C.parse(fg), C.parse(bg)), 2)
        if got != want:
            bad.append(f"contrast {fg}/{bg} {got}, not {want}")
    check(1, not bad, f"{len(sharma)} CIEDE2000 pairs within 0.0001 of Sharma's table; {len(cases) + 1} CSS colour forms "
                      f"and 2 WCAG contrast ratios exact" + (f"; {'; '.join(bad)}" if bad else ""))


def check_tokens():
    data = tokens.extract(Site(FIXTURE / "tools" / "site.json"))
    off = {(o["kind"], o["value"]): o for o in data["offtoken"]}
    toks = data["tokens"]
    teal = off.get(("color", "#0f766e"), {})
    found = {
        "hex and rgb() as one value": {"components/footer.tsx:4", "components/hero.tsx:10"} <= set(teal.get("uses", []))
        and "teal" in teal.get("equals_token", []),
        "arbitrary colour": "arbitrary" in off.get(("color", "#1d4ed8"), {}).get("how", []),
        "arbitrary shadow colour": ("color", "#16161614") in off,
        "arbitrary size": ("dimension", "13px") in off,
        "palette classes": ("color", "tailwind:gray-500") in off and "palette class" in off.get(("color", "#ffffff"), {}).get("how", []),
        "dark block": toks["background"]["contexts"]["dark"]["hex"] == "#0b0b0f",
        "second brand": toks["accent"]["contexts"]["beta"]["hex"] == "#b93a0b",
        "brand in dark mode": toks["accent"]["contexts"].get("beta/dark", {}).get("hex") == "#b93a0b"
        and toks["background"]["contexts"].get("beta/dark", {}).get("hex") == "#0b0b0f",
        "near-duplicate grey": any({n["a"], n["b"]} == {"#5c5c5c", "#5e5e5e"} for n in data["near_duplicates"]),
        "hard-coded font": data["coverage"]["font_unexplained"] == ["Comic Neue"],
        "docs font": "FixtureGrotesk" in data["fonts"]["docs"],
        "named one-off": off.get(("color", "#e8e6df"), {}).get("oneoff") and "#e8e6df" not in data["coverage"]["color_unexplained_values"],
        "@apply use": any(u.startswith("app/globals.css:") for u in toks["color-border"]["uses"]),
        "utility use": data["utilities"]["display"]["uses"] == ["components/hero.tsx:6"],
        "alias uses rolled up": len(toks["accent"]["uses_all"]) >= 2,
    }
    asset_line = next(i for i, l in enumerate((FIXTURE / "components/hero.tsx").read_text().splitlines(), 1) if "stripe-0f766e" in l)
    all_uses = {u for o in data["offtoken"] for u in o["uses"]}
    values = {o["value"] for o in data["offtoken"]}
    decoys = {
        "#fragment link": "#ccaaffee" not in values,
        "SVG url(#id)": "#bead42" not in values,
        "asset named with a hex code": f"components/hero.tsx:{asset_line}" not in all_uses,
        "HTML entity": "#116699" not in values,
        "colours in comments": not values & {"#0000ff", "#2244ff"},
        "colours in docs": not any(u.startswith("docs/") for u in all_uses),
    }
    t = tokens.dtcg(data)
    dtcg_ok = (t["accent"]["$type"] == "color" and t["accent"]["$value"]["colorSpace"] == "srgb"
               and t["accent"]["$value"]["hex"] == "#1d4ed8" and len(t["accent"]["$value"]["components"]) == 3
               and t["color-accent"]["$value"] == "{accent}" and t["font-sans"]["$value"] == ["Arial", "Helvetica", "sans-serif"]
               and t["radius-sm"]["$value"] == {"value": 0.375, "unit": "rem"}
               and "beta" in t["accent"]["$extensions"]["ex-designer"]["contexts"])
    missed = [k for k, v in found.items() if not v] + [f"decoy {k}" for k, v in decoys.items() if not v] + ([] if dtcg_ok else ["DTCG"])
    check(2, not missed, f"{len(found) - len([k for k, v in found.items() if not v])}/{len(found)} traps found, "
                         f"{sum(decoys.values())}/{len(decoys)} decoys ignored, tokens.json DTCG"
                         + (f"; wrong: {', '.join(missed)}" if missed else ""))
    return data


EDGE_CSS = """
@theme inline { --color-fg: var(--fg); --color-surface: var(--surface); }
:root { --accent: #00aa00; --surface: #ffffff; }
:root { --fg: #000000; --x: #111111 !important; --private-config: SECRET_MARKER_123; }
:root { --fg: #aaaaaa; --x: #222222; }
.dark, [data-brand="beta"] { --surface: #000000; }
.brand-gamma.dark { --accent: #ff0000; }
.dark { --accent: #0000ff; }
@media print { :root, .dark { --accent: #ffffff; } }
.button { --accent: #ffffff; }
:root { --loop: color-mix(in srgb, var(--loop), white); }
:root { --edge-font: "Edge Sans"; --g1: #5c5c5c; --g2: #5e5e5e; --text-title: 2rem; --radius-unused: 123px; }
:root { --text-wide: 3rem; }
.dark { --g1: #5e5e5e; --g2: #5c5c5c; }
.v2 { --accent: #123123; --surface: #fefefe; --fg: #010101; font-family: var(--edge-font), Arial, sans-serif; }
@font-face { font-family: "Edge Sans"; src: url("./fonts/edge-sans.woff2") format("woff2"); }
[data-brand="delta"] { font-family: Georgia, serif; }
@utility title { font-size: var(--text-title); @media (width >= 60rem) { font-size: var(--text-wide); }
  @media print { font-size: 8rem; } }
@utility fluid { font-size: clamp(2rem, 5vw, 4rem); }
@utility lead { font-size: var(--missing, 1.5rem); }
@media not print { :root { --screen-only: #0a0a0a; } }
"""
EDGE_SRC = """
export const a = "rgba(PRIVATE_KEY_123456789)";
export const b = <div className="bg-[color-mix(in_srgb,var(--accent)_80%,red)]" />;
export const accept = "image/*"; export const c = <p style={{ color: "#123456" }} />; /* a real comment */
export const d = <p style={{ color: "color(display-p3 0 1 0)" }} />;
export const e = <p style={{ fontFamily: "var(--missing-font, Wingdings)" }} />;
export const f = <p className="text-fg/50 bg-surface" />;
export const g = <p style="font-family: Arial" data-api-key="ATTR_SECRET_MARKER">x</p>;
export const h = <h1 className="title fluid lead">x</h1>;
export const k = <p className="text-[var(--g1)] bg-[var(--g2)]" />;
"""
EDGE_FONTS = """import localFont from "next/font/local";
const brand = localFont({ src: "./fonts/Brandface-Regular.woff2" });
"""


def check_report(base: str):
    """The audit report on the invented site: each finding's place is its own element's box (hidden first matches,
    zero-size or visibility:hidden, are skipped), each outline sits on that box, also on a page wider than the window,
    markers and list share numbers, every row of the all tab has its own marker, two markers on one element stay apart
    on a phone, a finding without a place gets a grey number, a finding on another page switches the screenshot, the
    dropped list is complete and has no markers, an area narrows every tab, the list shows without JavaScript, a
    placeholder name in a finding's text stays text, a moving element is measured as the screenshot shows it, the
    planted third-party requests and the redirects off the machine (direct, in two hops, through a backslash) are
    blocked and listed, and a selector that matches nothing, an error page, a page that moved or a page that is not
    http(s) stops it."""
    from playwright.sync_api import sync_playwright
    work = Path(tempfile.mkdtemp(prefix="ex-designer-report-"))
    (work / "extra" / "public").mkdir(parents=True)  # hidden twins and a page wider than the window
    (work / "extra" / "public" / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Extra</title></head><body style="margin:0">'
        '<p class="tag" style="visibility:hidden;margin:0;height:20px">Tag</p>'
        '<p class="tag" style="margin:40px 0 0;height:20px">Tag</p><div style="width:1800px;height:200px"></div>'
        '<span id="far" style="position:absolute;left:1500px;top:100px;width:20px;height:20px;background:#000"></span>'
        '<style>@keyframes m{to{transform:translateX(800px)}}</style><span id="mover" style="position:absolute;left:0;'
        'top:300px;width:20px;height:20px;background:#000;animation:m 2s linear infinite"></span>'
        '<img src="/assets/hop.png" alt=""><img src="/assets/slash.png" alt=""></body></html>')
    server2, base2, _ = fixture_server.start(work / "extra")
    text = lambda t: {"en": {"title": t, "where": "where " + t, "fix": "fix " + t}}  # noqa: E731
    findings = {"site": "alpha.invalid __DATA__", "date": "2026-10-27",
                "pages": [{"id": "home", "url": base + "/", "name": "Home"},
                          {"id": "about", "url": base + "/about/", "name": "About"},
                          {"id": "extra", "url": base2 + "/", "name": "Extra"}],
                "findings": [
                    {"id": "A", "severity": "high", "area": "seo", "rank": 1, "places": [{"page": "home", "selector": "h1"}],
                     "text": text("Headline")},
                    {"id": "B", "severity": "medium", "area": "ux", "rank": 2, "places": [{"page": "home", "selector": ".card",
                                                                             "all": True}], "text": text("Cards")},
                    {"id": "C", "severity": "low", "area": "privacy", "rank": 3, "places": [], "text": text("Site-wide")},
                    {"id": "D", "severity": "low", "area": "seo", "places": [{"page": "about", "selector": "title, h1"}],
                     "text": text("About headline")},
                    {"id": "E", "severity": "low", "area": "ux", "rank": 4, "places": [{"page": "home", "selector": "h1"}],
                     "text": text("Headline again __DATA__ __IMGS__ </script>")},
                    {"id": "F", "severity": "low", "area": "tech", "places": [{"page": "extra", "selector": ".tag"}],
                     "text": text("Visible twin")},
                    {"id": "G", "severity": "low", "area": "tech", "places": [{"page": "extra", "selector": "#far"}],
                     "text": text("Far right")},
                    {"id": "H", "severity": "low", "area": "tech", "places": [{"page": "extra", "selector": "#mover"}],
                     "text": text("Mover")}],
                "dropped": [{"id": "X", "area": "ux", "text": {"en": {"title": "Dropped hover", "reason": "why X"}}},
                            {"id": "Y", "area": "seo", "text": {"en": {"title": "Dropped size", "reason": "why Y"}}}]}
    (work / "f.json").write_text(json.dumps(findings))
    (work / "labels.json").write_text(json.dumps({"en": {"title": "Audit {site}"}}))
    run = lambda f, out: subprocess.run([sys.executable, str(SKILL / "scripts" / "report.py"), "--findings",  # noqa: E731
                                         str(work / f), "--labels", str(work / "labels.json"), "--out", str(work / out)],
                                        capture_output=True, text=True)
    good = run("f.json", "r.html")
    findings["findings"][0]["places"][0]["selector"] = ".nothing-here"
    (work / "bad.json").write_text(json.dumps(findings))
    bad = run("bad.json", "bad.html")
    findings["findings"][0]["places"][0]["selector"] = "h1"
    findings["pages"][1]["url"] = "file:///etc/hosts"
    (work / "file.json").write_text(json.dumps(findings))
    local = run("file.json", "file.html")
    findings["pages"][1]["url"] = base2 + "/missing/"
    (work / "gone.json").write_text(json.dumps(findings))
    gone = run("gone.json", "gone.html")
    findings["pages"][1]["url"] = base + "/about"  # answers 308 to /about/
    (work / "moved.json").write_text(json.dumps(findings))
    moved = run("moved.json", "moved.html")
    want = {"report written": good.returncode == 0, "a selector that matches nothing stops it":
            bad.returncode == 2 and ".nothing-here" in bad.stdout and not (work / "bad.html").exists(),
            "a page that is not http(s) stops it": local.returncode != 0 and "http or https" in local.stderr
            and not (work / "file.html").exists(),
            "an error page stops it": gone.returncode == 2 and "/missing/ answered HTTP 404" in gone.stdout
            and not (work / "gone.html").exists(),
            "a page that moved stops it": moved.returncode == 2 and "/about redirects to " in moved.stdout
            and not (work / "moved.html").exists(),
            "third-party requests and the redirect off the machine are blocked and listed": all(h in good.stdout for h in (
                "fonts.invalid", "tracker.invalid", "cdn.invalid", "api.invalid", "redirect to https://1.1.1.1/away.png",
                "redirect to https://1.1.1.1/hop.png", "redirect to http://1.1.1.1/slash.png"))}
    if good.returncode == 0:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            pg = b.new_page(viewport={"width": 1280, "height": 800})
            box = """(sel) => [...document.querySelectorAll(sel)].filter(el => el.checkVisibility({visibilityProperty: true}))
                .map(el => { const r = el.getBoundingClientRect(); return [r.x, r.y + scrollY, r.width, r.height].map(Math.round); })"""
            real = {}
            for url, key, sel in ((base + "/", "h1", "h1"), (base + "/", "cards", ".card"), (base + "/about/", "about", "h1"),
                                  (base2 + "/", "tag", ".tag"), (base2 + "/", "far", "#far")):
                pg.goto(url)
                real[key] = pg.evaluate(box, sel)
            extra_w = pg.evaluate("document.scrollingElement.scrollWidth")
            nojs = b.new_context(java_script_enabled=False).new_page()
            nojs.goto((work / "r.html").as_uri())
            want["the list shows without JavaScript"] = nojs.locator(".item").count() == 4
            pg.goto((work / "r.html").as_uri())
            model = json.loads(pg.locator("#model").text_content())
            got = {d["id"]: [p["box"] for p in d["places"]] for d in model["items"]}
            want["each finding's place is its own element's box"] = (
                got["A"] == real["h1"][:1] and got["E"] == real["h1"][:1] and got["B"] == real["cards"]
                and len(real["cards"]) == 3 and got["G"] == real["far"])
            want["a hidden first match is skipped (zero size, visibility:hidden)"] = (
                got["D"] == real["about"][:1] and len(real["tag"]) == 1 and got["F"] == real["tag"])
            pw = {q["id"]: q["w"] for q in model["pages"]}
            want["a page wider than the window keeps its own width"] = pw["extra"] == extra_w > 1280 and pw["home"] == 1280
            want["a placeholder name in a text stays text"] = (
                pg.locator("h1").text_content() == "Audit alpha.invalid __DATA__"
                and pg.locator(".item[data-id=E] .title").text_content() == "Headline again __DATA__ __IMGS__ </script>")
            want["markers and list share numbers"] = (
                sorted(pg.eval_on_selector_all(".marker", "ms => ms.map(m => m.textContent)")) == ["1", "2", "2", "2", "4"])
            want["a finding without a place gets a grey number"] = pg.locator(".item .num.none").count() == 1
            pg.click(".item[data-id=C]")
            want["opening it says it has no place, and what it concerns"] = (
                pg.locator("#noplace").is_visible() and "where Site-wide" in pg.locator("#noplace").inner_text())
            pg.click(".item[data-id=A]")
            want["opening a placed finding hides that note"] = not pg.locator("#noplace").is_visible()
            spots = pg.eval_on_selector_all(".marker", "ms => ms.map(m => m.style.left + ' ' + m.style.top)")
            want["two findings on one element keep two markers"] = len(spots) == len(set(spots))
            pg.click(".areabtn[data-a=seo]")
            want["an area narrows every list"] = (pg.locator(".item").count() == 1  # A is the only ranked SEO finding
                                                  and pg.locator(".item .area").first.text_content() == "area_seo")
            tabs_shown, narrowed = [], []
            for k in pg.eval_on_selector_all(".tab", "ts => ts.map(t => t.dataset.k)"):
                pg.click(f".tab[data-k={k}]")
                tabs_shown.append(k)
                narrowed.append(set(pg.eval_on_selector_all(".item .area", "xs => xs.map(x => x.textContent)")))
            pg.click(".tab[data-k=all]")
            seo_all = pg.locator(".item").count()
            pg.click(".tab[data-k=dropped]")
            seo_dropped = pg.locator(".item").count()
            want["an area narrows every tab, the new ones too"] = (
                {"all", "dropped"} <= set(tabs_shown) and all(n == {"area_seo"} for n in narrowed)
                and seo_all == 2 and seo_dropped == 1)
            pg.click(".areabtn[data-a=all]")
            pg.click(".tab[data-k=all]")
            rows = pg.eval_on_selector_all(".item", "bs => bs.map(b => [b.dataset.id, b.querySelector('.num').textContent])")
            outlines = pg.eval_on_selector_all(".outline", "os => os.map(o => o.dataset.id)")
            markers = pg.eval_on_selector_all(".marker", "ms => ms.map(m => m.textContent)")
            home = {d["id"]: len([p for p in d["places"] if p["page"] == "home"]) for d in model["items"]}
            want["the all tab lists every finding, by severity"] = [r[0] for r in rows] == list("ABCDEFGH")
            want["a moving element is measured as the screenshot shows it"] = got["H"] == [[0, 300, 20, 20]]
            spots = pg.eval_on_selector_all(".outline", "os => os.map(o => [o.dataset.id, +o.dataset.j, parseFloat(o.style.left), parseFloat(o.style.top)])")
            pg.click(".pagebtn >> text=Extra")
            spots += pg.eval_on_selector_all(".outline", "os => os.map(o => [o.dataset.id, +o.dataset.j, parseFloat(o.style.left), parseFloat(o.style.top)])")
            hs = {q["id"]: q["h"] for q in model["pages"]}
            pages_of = {d["id"]: d["places"] for d in model["items"]}
            want["each outline sits on its own element's box"] = len(spots) == 8 and all(
                abs(left - (pages_of[i][j]["box"][0] - 6) / pw[pages_of[i][j]["page"]] * 100) < 0.01
                and abs(top - (pages_of[i][j]["box"][1] - 6) / hs[pages_of[i][j]["page"]] * 100) < 0.01
                for i, j, left, top in spots)
            pg.click(".pagebtn >> text=Home")
            want["every row of the all tab has its own marker on its own element"] = (
                all(outlines.count(i) == home[i] for i in home)
                and sorted(markers) == sorted(n for i, n in rows for _ in range(home[i])))
            pg.click(".tab[data-k=dropped]")
            want["the dropped list is complete, with reasons and no markers"] = (
                pg.locator(".item.dropped").count() == 2 and pg.locator(".marker").count() == 0
                and pg.locator("#intro").is_visible()
                and pg.eval_on_selector_all(".item.dropped .meta", "xs => xs.map(x => x.textContent)")
                == ["reason why X", "reason why Y"])
            pg.click(".tab[data-k=first]")
            want["one screenshot shows at a time"] = pg.evaluate(
                "[...document.querySelectorAll('.shot img')].filter(i => i.offsetHeight > 0).length") == 1
            pg.click(".tab[data-k=low]")
            pg.click(".item[data-id=D]")
            want["a finding on another page switches the screenshot"] = (
                pg.locator(".pagebtn[aria-pressed=true]").text_content() == "About"
                and pg.locator("img[data-page=about]").is_visible())
            phone = b.new_page(viewport={"width": 390, "height": 844})
            phone.goto((work / "r.html").as_uri())
            ra, re_ = (phone.locator(f".marker[data-id={i}]").bounding_box() for i in "AE")
            want["two markers on one element stay apart on a phone"] = (
                ra["y"] + ra["height"] <= re_["y"] or re_["y"] + re_["height"] <= ra["y"]
                or ra["x"] + ra["width"] <= re_["x"] or re_["x"] + re_["width"] <= ra["x"])
            view = phone.locator("#viewer").bounding_box()
            want["every marker stays on the screenshot on a phone"] = all(
                view["x"] <= m["x"] and m["x"] + m["width"] <= view["x"] + view["width"]
                for m in (phone.locator(".marker").nth(i).bounding_box() for i in range(phone.locator(".marker").count())))
            b.close()
    server2.shutdown()
    check(14, all(want.values()), f"{sum(want.values())}/{len(want)} audit report checks"
                                  + "".join(f"; wrong: {k}" for k, v in want.items() if not v))


def check_edges():
    """The cascade and the scan's edge cases, on a small invented project in a temp folder. The secret file is an
    invented fixture.pem: a name the scripts must never read, linked into the sources and named as the token file."""
    work = Path(tempfile.mkdtemp(prefix="ex-designer-edges-"))
    (work / "app").mkdir()
    (work / "app" / "tokens.css").write_text(EDGE_CSS)
    (work / "app" / "page.tsx").write_text(EDGE_SRC)
    (work / "app" / "fonts.ts").write_text(EDGE_FONTS)
    (work / "app" / "label.css").write_text(".label { font: italic 700 16px/1.4 Papyrus, fantasy; }\n")
    (work / "app" / "fonts").mkdir()
    (work / "app" / "fonts" / "edge-sans.woff2").write_bytes(b"wOF2 invented font bytes")
    # Colour-like content: if a scan ever read this file, #abcdef and a font would show in the report.
    (work / "fixture.pem").write_text(".secret { color: #abcdef; font-family: PemSecretFont; }\n")
    (work / "app" / "leak.css").symlink_to(work / "fixture.pem")
    (work / "tools").mkdir()
    (work / "tools" / "site.json").write_text(json.dumps({"root": "..", "tokens": {"file": "app/tokens.css",
                                                          "sources": ["app/**/*.css", "app/**/*.tsx", "app/**/*.ts"]}}))
    data = tokens.extract(Site(work / "tools" / "site.json"))
    t = data["tokens"]
    dump = json.dumps(data)
    off = {o["value"] for o in data["offtoken"]}
    fonts = {f["family"] for f in data["fonts"]["hardcoded"]}
    want = {
        "selector list reaches both contexts": t["surface"]["contexts"]["dark"]["hex"] == "#000000"
        and t["surface"]["contexts"]["beta"]["hex"] == "#000000" and t["surface"]["contexts"]["base"]["hex"] == "#ffffff",
        "the later declaration wins": t["fg"]["contexts"]["base"]["hex"] == "#aaaaaa",
        "!important wins and stays a colour": t["x"]["contexts"]["base"]["hex"] == "#111111",
        "specificity wins over order": t["accent"]["contexts"]["gamma/dark"]["hex"] == "#ff0000"
        and t["accent"]["contexts"]["dark"]["hex"] == "#0000ff",
        "a non-design value is not copied": "SECRET_MARKER_123" not in dump,
        "an unreadable colour is named, not copied": "PRIVATE_KEY" not in dump and "unresolved rgba()" in off,
        "a literal colour inside color-mix() with var()": "#ff0000" in off and bool(t["accent"]["uses"]),
        "font shorthand": "Papyrus" in fonts,
        "next/font/local": "Brandface" in fonts,
        "a link to a secret file is not read": "#abcdef" not in off and "PemSecretFont" not in dump,
        "a component's variable and print styles are not screen tokens": t["accent"]["contexts"]["base"]["hex"] == "#00aa00"
        and t["accent"]["contexts"]["dark"]["hex"] == "#0000ff",
        "a comment mark inside a string": "#123456" in off,
        "color() with a colour space": "#00ff00" in off,
        "a font in a var() fallback": "Wingdings" in fonts,
        "an attribute next to font-family stays out": "ATTR_SECRET_MARKER" not in dump and "Arial" in fonts,
        "a cyclic color-mix() ends": t.get("loop", {}).get("type") == "other",
        "a theme's own font-family is its page font": data["fonts"]["page"].get("v2/dark", {}).get("families", [""])[0]
        == "Edge Sans" and "base" not in data["fonts"]["page"],
        "an @font-face rule keeps its file": {"family": "Edge Sans", "src": "./fonts/edge-sans.woff2", "style": "normal",
                                              "weight": "400"} in data["fonts"]["faces"],
        "a context only a font opens is a context": data["fonts"]["page"].get("delta", {}).get("families")
        == ["Georgia", "serif"],
        "@media not print applies on screen": t["screen-only"]["contexts"]["base"]["hex"] == "#0a0a0a",
        "print media is only print": tokens.print_only("@media print") and tokens.print_only("@media only print and "
        "(orientation: landscape)") and not tokens.print_only("@media not print")
        and not tokens.print_only("@media print, (min-width: 1px)"),
        "a near pair counts in each context it reaches": any(n["context"] == "dark" and {n["a"], n["b"]}
                                                             == {"#5c5c5c", "#5e5e5e"} for n in data["near_duplicates"]),
        "a font family cannot add CSS": tokens.css_stack(["X;background:url(https://x.invalid/p)", "sans-serif"])
        == '"X;background:url(https://x.invalid/p)", sans-serif',
        "a font descriptor cannot add CSS": tokens.face_descriptors('"x}body{background:red}/*"', "400 700")
        == ("normal", "400 700"),
    }
    pairs = {p["fg"]: p["ratio_exact"] for p in tokens.contrast_pairs(data, "base", all_fills=True) if p["bg"] == "surface"}
    want["an opacity modifier counts in contrast"] = "fg/50" in pairs and pairs["fg/50"] < pairs.get("fg", 99)
    design = work / "design"
    design.mkdir()
    (design / "usage.json").write_text(json.dumps(data))
    edge_site = Site(work / "tools" / "site.json")
    shown = tokens.page(edge_site, design, {}).lower()
    asked = tokens.owner_questions(edge_site, design, {"q_unexplained_color": "{value} at {where}?",
                                                       "q_near_duplicate": "{a} ~ {b}?"})
    want["the page holds the system only"] = ("#00aa00" in shown and "#123456" not in shown and "id=outside" not in shown
                                              and "radius-unused" not in shown)
    want["a utility size through a token, print sizes left out"] = ("32 px" in shown and "≥ 960 px: 48 px" in shown
                                                                     and "128 px" not in shown)
    want["a fluid size stays CSS, a var() fallback size resolves"] = ("font-size:clamp(2rem, 5vw, 4rem)" in shown
                                                                       and "24 px" in shown)
    want["var() with a quoted fallback"] = (
        tokens.resolve_vars('var(--family, "DIN (Text)"), Arial', lambda n: "Inter" if n == "--family" else None)
        == "Inter, Arial" and tokens.resolve_vars('var(--none, "DIN (Text)"), Arial', lambda n: None)
        == '"DIN (Text)", Arial')
    want["a near pair is asked once in either order"] = sum(
        "--g1" in q and "--g2" in q for q in asked.splitlines()) == 1
    want["a font file next to the stylesheet is embedded"] = "data:font/woff2;base64," in shown
    want["the owner's questions go to chat"] = asked.startswith("Questions for the owner") and "#123456" in asked
    try:
        Site(work / "tools" / "site.json").file("fixture.pem")
        want["a secret token file is refused"] = False
    except SystemExit:
        want["a secret token file is refused"] = True
    names = [shoot.slug(x) for x in ("/", "/index/", "/a/b/", "/a__b/", "/a/b")]
    want["shot names are unique"] = len(set(names)) == len(names)
    sitemaps = {"/sitemap.xml": b'<sitemapindex><sitemap><loc>https://x.invalid/s1.xml</loc></sitemap>'
                                b'<sitemap><loc>https://x.invalid/sitemap.xml</loc></sitemap></sitemapindex>',
                "/s1.xml": b"<urlset><url><loc>https://x.invalid/</loc></url><url><loc>https://x.invalid/b/</loc></url></urlset>"}
    got = livecheck.sitemap_paths(lambda p: {"status": 200 if p in sitemaps else 404, "body": sitemaps.get(p, b"")},
                                  "/sitemap.xml")
    want["sitemap index followed, loop stopped"] = got == ["/", "/b/"]
    minified = (".content-\\[\\'x\\'\\]{content:'x'}.w-\\[calc\\(100\\%-1rem\\)\\]{width:1px}"
                ":root{--esc:lab(54.29% 80.8 69.89)}:is(.dark,:root:has(.app)){--esc:#0000ff}")
    (work / "app" / "min.css").write_text(minified)
    blocks = {tuple(c): {p: v for p, v, *_ in d} for c, d in tokens.css_blocks(tokens.strip_comments(minified, False))}
    want["escaped selectors and lab() in minified CSS"] = (blocks.get((":root",), {}).get("--esc") == "lab(54.29% 80.8 69.89)"
                                                            and C.hex(C.parse("lab(54.29% 80.8 69.89)")) == "#ff0000"
                                                            and "--esc" in blocks.get((":is(.dark,:root:has(.app))",), {}))
    refused = 0
    for path in ("@evil.invalid/x", "//evil.invalid/x", "/a\\b"):
        try:
            fetch("http://127.0.0.1:9", path)
        except ValueError:
            refused += 1
        except OSError:
            pass
    want["a crafted path never leaves the host"] = refused == 3
    trap = work / "shots-trap"
    (trap / "a").mkdir(parents=True)
    keep = work / "outside.png"
    keep.write_bytes(b"keep")
    (trap / "manifest.json").write_text(json.dumps({"shots": [{"file": "../outside.png"}, {"file": "a/b.png"}]}))
    (trap / "a" / "b.png").write_bytes(b"old")
    shoot.clear(trap)
    want["a manifest cannot delete outside its folder"] = keep.exists() and not (trap / "a" / "b.png").exists()
    empty = work / "no-manifest"
    (empty / "x").mkdir(parents=True)
    try:
        diff.run(OUT / "shots-stable", empty, OUT / "diff-no-manifest")
        want["no manifest, no comparison"] = False
    except ValueError:
        want["no manifest, no comparison"] = True
    shutil.rmtree(work, ignore_errors=True)
    bad = [k for k, v in want.items() if not v]
    check(12, not bad, f"{len(want) - len(bad)}/{len(want)} cascade, scan, secret, naming and sitemap edge cases"
                       + (f"; wrong: {', '.join(bad)}" if bad else ""))


def block_span(css: str, selector: str):
    m = re.search(re.escape(selector) + r"\s*\{", css)
    end = css.index("}", m.end())
    return m.end(), end


def set_token(path: Path, selector: str, name: str, value: str | None = None) -> str:
    """Read (value None) or replace one declaration in one block of the token file; returns the old value."""
    css = path.read_text()
    a, b = block_span(css, selector)
    m = re.search(rf"(--{re.escape(name)}:\s*)([^;]+);", css[a:b])
    old = m.group(2).strip()
    if value is not None:
        css = css[:a + m.start(2)] + value + css[a + m.end(2):]
        path.write_text(css)
    return old


def shifted(value: str) -> tuple[str, float]:
    """A colour CIEDE2000 2 away from value (lighter, or darker for the lightest colours), in 8-bit hex."""
    c = C.parse(value)
    L, a, b = C.lab(c)
    for sign in (1, -1):
        lo, hi = 0.0, 8.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if C.delta_e(c, C.parse(C.hex(C.from_lab(L + sign * mid, a, b)))) < 2.0:
                lo = mid
            else:
                hi = mid
        cand = C.from_lab(L + sign * hi, a, b)
        if all(-0.002 <= x <= 1.002 for x in cand[:3]):
            h = C.hex(cand)
            return h, C.delta_e(c, C.parse(h))
    raise ValueError(f"no shift for {value}")


def changed_combos(d: dict) -> set[tuple[str, str]]:
    return {tuple(r["file"].split("/")[:2]) for r in d["results"] if r["changed_pixels"]}


def expected_combos(before: dict, after: dict) -> set[tuple[str, str]]:
    out = set()
    for ctx, combo in COMBO.items():
        for name, t in after["tokens"].items():
            a, b = t["contexts"].get(ctx, {}), before["tokens"][name]["contexts"].get(ctx, {})
            if a.get("type") == "color" and a.get("hex") != b.get("hex"):
                out.add(combo)
    return out


def replace_in(path: Path, old: str, new: str):
    """Plant a trap: the text to change must be there, so a trap that plants nothing cannot pass by accident."""
    text = path.read_text()
    assert old in text, f"{path.name}: {old!r} not found"
    path.write_text(text.replace(old, new, 1))


def edit_ledger(wd: Path, change):
    led = json.loads((wd / "ledger.json").read_text())
    change(led)
    (wd / "ledger.json").write_text(json.dumps(led))


def fact(led: dict, fid: str) -> dict:
    return next(f for f in led["facts"] if f["id"] == fid)


BRAND_TRAPS = [  # (what, plant(work folder), the rule that must catch it, and only it)
    ("a hex value not in the tokens", lambda wd: replace_in(wd / "book.md", "Blue #1d4ed8", "Blue #2244ff"), "colour"),
    ("the other brand's colour", lambda wd: replace_in(wd / "book.md", "page is #0b0b0f", "page is #b93a0b"), "colour"),
    ("a colour written as an entity", lambda wd: replace_in(wd / "book.md", "Blue #1d4ed8", "Blue &#35;2244ff"),
     "colour"),
    ("a never-value no cited fact quotes", lambda wd: replace_in(
        wd / "book.md", "In dark mode the page is #0b0b0f.",
        "In dark mode the page is #0b0b0f.\n\nNever #2244ff. <!-- value-allow --> [[colour-accent]]"), "colour"),
    ("a named colour in code", lambda wd: replace_in(wd / "book.md", "and nowhere else.",
                                                     "and nowhere else, as in `color: rebeccapurple`."), "colour"),
    ("a font not in the tokens", lambda wd: replace_in(wd / "book.md", "set in Arial.", "set in Inter."), "font"),
    ("a font in lower case", lambda wd: replace_in(wd / "book.md", "set in Arial.", "set in inter."), "font"),
    ("a font split by emphasis", lambda wd: replace_in(wd / "book.md", "set in Arial.", "set in In**te**r."), "font"),
    ("a font split across two lines", lambda wd: replace_in(wd / "book.md", "All text is set in Arial.",
                                                            "All text is set in Neue\nMontreal."), "font"),
    ("a colour split by emphasis", lambda wd: replace_in(wd / "book.md", "Blue #1d4ed8", "Blue #22**44**ff"), "colour"),
    ("a fact with no source", lambda wd: edit_ledger(wd, lambda led: fact(led, "imagery-stripe").update(sources=[])),
     "source"),
    ("a quote not on its page", lambda wd: edit_ledger(wd, lambda led: fact(led, "voice-team")["sources"][0].update(
        quote="A large team that moves fast.")), "source"),
    ("a source on line zero", lambda wd: edit_ledger(wd, lambda led: fact(led, "care-tokens")["sources"][0].update(
        ref="app/globals.css:0")), "source"),
    ("a mark with no fact", lambda wd: replace_in(wd / "book.md", "[[voice-never]]", "[[voice-never-old]]"), "mark"),
    ("a claim with no mark", lambda wd: replace_in(wd / "book.md", "plain and steady. [[who-values]]",
                                                   "plain and steady. [[who-values]]\n\nIt is the calmest studio "
                                                   "in the world."), "mark"),
    ("a quotation its fact does not hold", lambda wd: replace_in(wd / "book.md", '"Start" [[voice-cta]]',
                                                                 '"Sell everything now" [[voice-cta]]'), "quote"),
    ("a quotation in single marks", lambda wd: replace_in(wd / "book.md", '"Start" [[voice-cta]]',
                                                          "‘Sell everything now’ [[voice-cta]]"), "quote"),
    ("a mark alone", lambda wd: replace_in(wd / "book.md", "Never shout. [[voice-never]]",
                                           "Never shout. [[voice-never]]\n\n[[voice-lede]]"), "mark"),
    ("an inferred fact in the owner's chapter", lambda wd: edit_ledger(wd, lambda led: fact(led, "who-values").update(
        status="observed", sources=[{"kind": "page", "host": "alpha.invalid", "path": "/",
                                     "quote": "We make calm software."}])), "status"),
    ("a missing core chapter", lambda wd: replace_in(
        wd / "book.md", "## Imagery {#imagery}\n\nThe home page has one thin teal stripe as decoration. [[imagery-stripe]]"
        "\n\nWhich photographs or illustrations the brand uses is still open. [[open: G1]]\n\n", ""), "chapter"),
    ("another chapter's gap as a chapter's content", lambda wd: replace_in(
        wd / "book.md", "Alpha Studio builds small, calm tools for teams who run a shop on their own. [[who-what]] Its "
        "three words are calm,\nplain and steady. [[who-values]]", "Who it serves is still open. [[open: G1]]"),
     "chapter"),
    ("an optional chapter with another chapter's fact", lambda wd: (wd / "book.md").write_text(
        (wd / "book.md").read_text() + "\n## Motion {#motion}\n\nThe site moves gently. [[voice-lede]]\n"), "chapter"),
    ("an em dash", lambda wd: replace_in(wd / "book.md", "Never shout.", "Never shout — ever."), "gate"),
    ("an en dash used as a dash", lambda wd: replace_in(wd / "book.md", "Never shout.", "Calm –never loud."), "gate"),
    ("a banned word", lambda wd: replace_in(wd / "book.md", "Short sentences", "Robust sentences"), "gate"),
    ("a banned word split by emphasis", lambda wd: replace_in(wd / "book.md", "Short sentences", "Ro**bu**st sentences"),
     "gate"),
    ("the brand's own never-word", lambda wd: replace_in(wd / "book.md", "Never shout.", "Never shout or look cheap."),
     "gate"),
    ("a date", lambda wd: replace_in(wd / "book.md", "The home page opens", "Since 27 October 2026 the home page opens"),
     "furniture"),
    ("a slashed date", lambda wd: replace_in(wd / "book.md", "The home page opens", "Since 10/28/2026 the home page opens"),
     "furniture"),
    ("a decision note", lambda wd: replace_in(wd / "book.md", "for actions only.", "for actions only. Decision: keep "
                                                                                    "the blue."), "furniture"),
    ("a person deciding", lambda wd: replace_in(wd / "book.md", "one line and one button.",
                                                "one line and one button. Pat Example signed it off."), "furniture"),
    ("a link to no kit file", lambda wd: replace_in(wd / "readme.md", "(brand-book.md)", "(brand-book.docx)"), "link"),
    ("a link that runs code", lambda wd: replace_in(wd / "readme.md", "(brand-book.md)", "(javascript:alert(1))"),
     "link"),
    ("a picture from the network", lambda wd: replace_in(
        wd / "book.md", "one line and one button. [[in-use-hero]]",
        "one line and one button. [[in-use-hero]]\n\n![Home](http://127.0.0.1:9/home.png)"), "link"),
    ("a picture behind nested brackets", lambda wd: replace_in(
        wd / "book.md", "one line and one button. [[in-use-hero]]",
        "one line and one button. [[in-use-hero]]\n\n![Home [desktop]](http://127.0.0.1:9/home.png)"), "link"),
    ("raw HTML in the front page", lambda wd: (wd / "readme.md").write_text(
        (wd / "readme.md").read_text() + '\n<img src="http://127.0.0.1:9/pixel.png">\n'), "link"),
    ("raw code HTML beside a fence Markdown does not render", lambda wd: replace_in(
        wd / "book.md", "one line and one button. [[in-use-hero]]",
        "one line and one button. [[in-use-hero]]\n\n- A list item [[in-use-hero]]\n  ```\n  x\n  ```\n\n"
        '<pre><code>A sample <img src="http://127.0.0.1:9/p.png"></code></pre> [[in-use-hero]]'), "link"),
    ("raw HTML across two lines", lambda wd: replace_in(wd / "book.md", "one line and one button. [[in-use-hero]]",
                                                        'one line and one button. <img\nsrc="http://127.0.0.1:9/p.png">'
                                                        " [[in-use-hero]]"), "link"),
    ("an internal path", lambda wd: (wd / "readme.md").write_text(
        (wd / "readme.md").read_text() + "\nSources: `brand-work/ledger.json`\n"), "furniture"),
]


def check_brandbook(base: str, log: list):
    """The brand book step on Alpha Studio, an invented brand of the fixture site: read, the clean book, the traps."""
    work = Path(tempfile.mkdtemp(prefix="ex-designer-brand-"))
    design = work / "design"
    design.mkdir()
    (design / "usage.json").write_text(json.dumps(tokens.extract(Site(FIXTURE / "tools" / "site.json"))))

    def folder(name: str, kit: str, src: Path = HERE / "fixtures" / "brand-work") -> Path:
        wd = work / name
        shutil.copytree(src, wd)
        cfg = json.loads((wd / "brand.json").read_text())
        cfg.update(site=str(FIXTURE / "tools" / "site.json"), design=str(design), kit=str(work / kit))
        (wd / "brand.json").write_text(json.dumps(cfg))
        return wd

    wd = folder("brand-work", "brand")
    asked = len(log)
    cap = brandbook.read(wd, base=base)
    pages = cap["hosts"]["alpha.invalid"]["pages"]
    home = brandbook.page_text(pages["/"])
    want = {
        "read: the brand's three pages": {p: v["status"] for p, v in pages.items()} == {"/": 200, "/about/": 200, "/wide/": 200},
        "read: only the brand's host asked": {h for h, _ in log[asked:]} == {"alpha.invalid"},
        "read: the copy, not the scripts": "We make calm software." in home and "getElementById" not in home
        and "A small team that keeps things running." in brandbook.page_text(pages["/about/"]),
        "read: the brand files in the code": {f["path"] for f in cap["files"]} == {"public/assets/favicon-alpha.svg",
                                                                                  "public/assets/favicon-beta.svg"},
        "read: capture.md": (wd / "capture.md").is_file(),
    }
    parser = brandbook.Copy()  # a framework's hidden copy of the head, and a headline the stylesheet breaks in two
    parser.feed('<body><div hidden><title>Shown title</title><meta name="description" content="Shown meta">'
                '<p>Streamed twice</p></div><h1>Know which deals<span class="block">deserve your time.</span></h1>'
                '<p>One <strong>word</strong>, kept whole.</p><script>var secret = 1</script>'
                '<p hidden>Old line<p>Current line</p><img hidden alt="Old art"><img alt="Shown art">'
                '<p hidden>Old<div>Current div</div><ul><li hidden>Old item</ul><p>After list</p></body>')
    parser.close()
    got = parser.result()
    want["read: hidden copy skipped, the head kept, a stacked line read with its space"] = (
        got["title"] == "Shown title" and got["meta"] == {"description": "Shown meta"}
        and [b["text"] for b in got["blocks"]] == ["Know which deals deserve your time.", "One word, kept whole.",
                                                   "Current line", "Current div", "After list"]
        and [i["alt"] for i in got["images"]] == ["Shown art"])
    rules = brandbook.furniture_rules([])
    want["a standing rule is not a decision note; a record of one is"] = (
        not brandbook.flat_hits("x", "Changes must be approved by the brand owner.", rules, [])
        and bool(brandbook.flat_hits("x", "The blue was approved by the owner.", rules, [])))
    clean = brandbook.check(wd)
    want["the clean book passes every check"] = not clean
    built = brandbook.build(wd)
    kit = work / "brand"
    md = (kit / "brand-book.md").read_text() if (kit / "brand-book.md").exists() else ""
    page = (kit / "brand-book.html").read_text() if (kit / "brand-book.html").exists() else ""
    want["the kit: .md, .html, .pdf, README and the logo"] = built["ok"] and set(built["written"]) == {
        "README.md", "brand-book.md", "brand-book.html", "brand-book.pdf", "files/logo-mark.svg"}
    want["the PDF opens, a page per chapter"] = built.get("pdf_pages", 0) >= 10
    want["the .md for AI tools: no marks, the exact values"] = (
        "[[" not in md and "{#" not in md and "<!--" not in md and "#1D4ED8" in md and "Arial" in md
        and "#B93A0B" not in md)
    want["the .html: every chapter, specimens from the tokens, the open question"] = (
        all(f'id="{c}"' in page for c in brandbook.CORE) and "class=bands" in page and "#1D4ED8" in page
        and "#B93A0B" not in page and "class=open" in page and "[[" not in page and "EXDESIGNER" not in page
        and "files/logo-mark.svg" in page)
    caught, wrong = 0, []
    for i, (what, plant, rule) in enumerate(BRAND_TRAPS):
        trap = folder(f"trap-{i}", f"kit-{i}", wd)  # with the capture that read made
        plant(trap)
        rules = {p["rule"] for p in brandbook.check(trap)}
        if rules == {rule}:
            caught += 1
        else:
            wrong.append(f"{what}: {sorted(rules) or 'nothing'}")
    site_copy = work / "site-copy"  # a site whose code holds a note in a logo file, and the work folder itself
    shutil.copytree(FIXTURE, site_copy)
    (site_copy / "public" / "assets" / "notes-logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><!-- TODO swap the mark --></svg>')
    keeper = folder("keeper", "brand", wd)
    cfg = json.loads((keeper / "brand.json").read_text())
    cfg.update(site=str(site_copy / "tools" / "site.json"),
               files={"logo-mark.svg": "public/assets/favicon-alpha.svg", "notes-logo.svg": "public/assets/notes-logo.svg"})
    (keeper / "brand.json").write_text(json.dumps(cfg))
    before = {p.relative_to(kit).as_posix(): p.read_bytes() for p in kit.rglob("*") if p.is_file()}
    r_keep = brandbook.build(keeper)
    after = {p.relative_to(kit).as_posix(): p.read_bytes() for p in kit.rglob("*") if p.is_file()}
    want["a build that fails its final check leaves the kit as it was"] = (
        not r_keep["ok"] and any("notes-logo.svg" in p["where"] for p in r_keep["problems"]) and after == before
        and not [p for p in work.iterdir() if p.name.startswith(".brand")])
    (site_copy / "public" / "assets" / "OFL.txt").write_text(
        "Copyright 2020 The Example Sans Project Authors\n\nSIL OPEN FONT LICENSE Version 1.1 - 26 February 2007\n")
    licensed = folder("licensed", "kit-licensed", wd)
    cfg = json.loads((licensed / "brand.json").read_text())
    cfg.update(site=str(site_copy / "tools" / "site.json"),
               files={"logo-mark.svg": "public/assets/favicon-alpha.svg", "font-licence-OFL.txt": "public/assets/OFL.txt"})
    (licensed / "brand.json").write_text(json.dumps(cfg))
    r_lic = brandbook.build(licensed)
    shipped = work / "kit-licensed" / "files" / "font-licence-OFL.txt"
    if shipped.exists():
        shipped.write_text(shipped.read_text() + "TODO swap the font\n")
        (site_copy / "public" / "assets" / "LICENSE-notes.txt").write_text("TODO ask Pat Example about the font\n")
        shutil.copyfile(site_copy / "public" / "assets" / "LICENSE-notes.txt", shipped.with_name("notes.txt"))
        cfg["files"]["notes.txt"] = "public/assets/LICENSE-notes.txt"  # named like a licence, but a note
        os.symlink("LICENSE-notes.txt", site_copy / "public" / "assets" / "LICENSE")  # a licence name leading to it
        shutil.copyfile(site_copy / "public" / "assets" / "LICENSE-notes.txt", shipped.with_name("linked.txt"))
        cfg["files"]["linked.txt"] = "public/assets/LICENSE"
        (licensed / "brand.json").write_text(json.dumps(cfg))
    lic_hits, lic_broken, _ = brandbook.inspect_kit(brandbook.Work(licensed))
    want["a font licence ships with its date, and only as the site's code holds it; a note named like one does not"] = (
        r_lic["ok"] and "files/font-licence-OFL.txt" in r_lic["written"]
        and any(b.startswith("files/font-licence-OFL.txt: differs") for b in lic_broken)
        and any(h[0].startswith("files/notes.txt") for h in lic_hits)
        and any(h[0].startswith("files/linked.txt") for h in lic_hits))
    bare = brandbook.Work(wd)
    bare.hex_in = lambda name, ctx: None  # a site without a background token still shows its logo
    want["the logo specimen shows the logo on the page's own ground"] = "<img src='files/logo-mark.svg'" in (
        brandbook.spec_logo_html(bare))
    inside = site_copy / "brand-work"
    shutil.copytree(wd, inside)
    cfg = json.loads((inside / "brand.json").read_text())
    cfg.update(site=str(site_copy / "tools" / "site.json"), kit=str(work / "kit-inside"),
               files={"facts.json": "brand-work/ledger.json"})
    (inside / "brand.json").write_text(json.dumps(cfg))
    want["a work file named for the kit never ships"] = any(
        p["rule"] == "files" and "work folder" in p["text"] for p in brandbook.check(inside))
    refused = folder("refused", "kit-refused", wd)
    replace_in(refused / "book.md", "Never shout.", "Never shout — ever.")
    r = brandbook.build(refused)
    want["the build refuses a failing book, writing nothing"] = not r["ok"] and not (work / "kit-refused").exists()
    secret = folder("secret", "kit-secret", wd)
    (secret / "plain.json").write_text("{}")
    os.symlink(secret / "plain.json", secret / "id_rsa")  # a secret name is refused even when it leads elsewhere
    cfg = json.loads((secret / "brand.json").read_text())
    (secret / "brand.json").write_text(json.dumps({**cfg, "labels": "id_rsa"}))
    try:
        brandbook.Work(secret)
        refused_secret = False
    except SystemExit as e:
        refused_secret = "secret" in str(e)
    want["a secret file named in brand.json is never read, in any letter case"] = (
        refused_secret and brandbook.secret_name(Path("ID_RSA")) and brandbook.secret_name(Path("Server.KEY"))
        and not brandbook.secret_name(Path("favicon.svg")))
    allowed = folder("allowed", "kit-allowed", wd)
    replace_in(allowed / "book.md", "Short sentences and plain words",
               "Never robust words. <!-- gate-allow --> [[voice-never]]\n\nShort sentences and plain words")
    r_allowed = brandbook.build(allowed)
    want["a gate-allow paragraph passes in every built file, the PDF included"] = r_allowed["ok"] and not r_allowed["problems"]
    from PIL import Image
    im = Image.new("RGB", (4, 4), "white")
    exif = im.getexif()
    exif.get_ifd(0x8769)[0x9286] = b"ASCII\x00\x00\x00TODO replace the mark"  # UserComment, in the Exif folder
    im.save(kit / "photo-note.jpg", "JPEG", exif=exif)
    (kit / "broken.jpg").write_bytes(b"\xff\xd8\xffTODO replace the mark")
    (kit / "voice.txt").write_text("Robust words, cheap ones.\n")
    (kit / "notes.txt").write_text("TODO replace the mark. <!-- furniture-allow -->\n")
    (kit / "press-note.txt").write_text("The colours were approved by Pat Example.\n")
    (kit / "logo.ai").write_bytes(b"%!PS-Adobe")
    (kit / "photo.jpg").write_bytes(b"not a picture")
    hits, broken, _ = brandbook.inspect_kit(brandbook.Work(wd))
    want["a note, an unreadable file or a renamed one put into the kit is caught"] = (
        any(h[0].startswith("press-note.txt") for h in hits) and any(b.startswith("logo.ai") for b in broken)
        and any(b.startswith("photo.jpg") for b in broken))
    want["in the kit: a note in nested EXIF, a picture that does not decode, the gate on text files, no self-granted "
         "exemption"] = (
        any(h[0].startswith("photo-note.jpg") for h in hits) and any(b.startswith("broken.jpg") for b in broken)
        and any(h[0].startswith("voice.txt") and any(x.startswith("gate:") for x in h[1]) for h in hits)
        and any(h[0].startswith("notes.txt") for h in hits))
    want[f"{len(BRAND_TRAPS)} traps, each caught by its own rule only"] = caught == len(BRAND_TRAPS)
    check(15, all(want.values()), f"{sum(want.values())}/{len(want)} brand book checks; {caught}/{len(BRAND_TRAPS)} "
                                  f"traps caught by their own rule"
          + (f"; wrong: {', '.join(k for k, v in want.items() if not v)}" if not all(want.values()) else "")
          + (f"; {'; '.join(wrong)}" if wrong else "") + (f"; clean book: {clean[:3]}" if clean else "")
          + (f"; build: {built['problems'][:3]}" if built.get("problems") else ""))
    shutil.rmtree(work, ignore_errors=True)


def solve(root: Path, wrong: bool):
    """A scripted maintainer for the newcomer kit: right, or wrong on each job in its own way."""
    def commit(msg):
        newcomer.git(root, "add", "-A")
        newcomer.git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", msg)
    css = root / "app" / "globals.css"
    replace_in(css, "--accent: #b93a0b;", f"--accent: {newcomer.TARGET};" if wrong else "--accent: rgb(124, 45, 18);")
    if wrong:
        replace_in(css, "--accent: #1d4ed8;", f"--accent: {newcomer.TARGET};")
    commit("Beta accent")
    if wrong:
        replace_in(root / "components" / "hero.tsx", "<h1", '<h1 style={{ fontFamily: "Georgia, serif" }}')
        commit("Georgia")
    else:
        replace_in(css, "--font-sans: Arial, Helvetica, sans-serif;", "--font-sans: \"Georgia\", serif;")
        commit("Georgia")
        newcomer.git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "revert", "--no-edit", "HEAD")
    (root / "answers").mkdir(exist_ok=True)
    (root / "answers" / "contact-form.md").write_text(
        "Check the hosting log and send a test." if wrong else "Check Mailroute's sending log. If MAILROUTE_KEY is "
        "refused, the owner makes a new key and puts it on Pilvi Hosting. One test send, only with the owner's yes.")
    commit("Contact form answer")


def check_newcomer():
    work = Path(tempfile.mkdtemp(prefix="ex-designer-newcomer-"))
    try:
        kit = newcomer.build(work / "kit")
        right, wrong = work / "right", work / "wrong"
        shutil.copytree(kit, right)
        shutil.copytree(kit, wrong)
        solve(right, False)
        solve(wrong, True)
        ev = work / "kit-evidence"
        r, w = newcomer.score(right, ev), newcomer.score(wrong, ev)
        css = right / "app" / "globals.css"
        kept = css.read_text()
        css.write_text(kept + "\n/* an uncommitted change */\n")
        dirty = newcomer.score(right, ev)
        css.write_text(kept)
        shot = next((right / "baseline" / "shots").rglob("*.png"))
        shot.write_bytes(shot.read_bytes() + b" ")
        reshot = newcomer.score(right, ev)
        own = {1: "outside beta", 2: "outside the token file: 1", 3: "Georgia left in ['HEAD:components/hero.tsx']",
               4: "'mailroute'"}
        wrong_ok = all(not j["ok"] and own[n] in j["detail"] for n, j in w["jobs"].items())
        dirty_ok = [j["ok"] for j in dirty["jobs"].values()] == [False, False, False, True]
        ok = (r["passed"] == 4 and w["passed"] == 0 and wrong_ok and dirty_ok and not reshot["jobs"][1]["ok"]
              and reshot["passed"] == 3)
        check(16, ok, f"right solution (rgb() accent, quoted font) {r['passed']}/4; wrong solution {w['passed']}/4, "
                      f"each on its own rule: {'yes' if wrong_ok else 'NO'}; an uncommitted change fails jobs 1-3: "
                      f"{'yes' if dirty_ok else 'NO'}; a re-shot baseline fails job 1: "
                      f"{'yes' if not reshot['jobs'][1]['ok'] else 'NO'}"
                      + ("" if ok else f"; right {r['jobs']}; wrong {w['jobs']}; dirty {dirty['jobs']}"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    t0 = time.time()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    check_color()
    check_tokens()

    work = Path(tempfile.mkdtemp(prefix="ex-designer-test-"))
    site_dir = work / "code-site"
    shutil.copytree(FIXTURE, site_dir)
    server, base, log = fixture_server.start(site_dir)
    site = Site(site_dir / "tools" / "site.json")
    site.data["serve"]["url"] = base
    css = site_dir / "app" / "globals.css"
    original_css = css.read_text()
    try:
        stable = shoot.shoot(site, OUT / "shots-stable", runs=3)
        again = shoot.shoot(site, OUT / "shots-again", runs=1)
        d = diff.run(OUT / "shots-stable", OUT / "shots-again", OUT / "diff-again")
        unstable = [s["file"] for s in stable["shots"] if not s["stable"]]
        check(3, not unstable and d["changed"] == 0 and d["compared"] == 24,
              f"{len(stable['shots'])} shots x 3 runs: {len(unstable)} unstable; a separate run: {d['changed']} of "
              f"{d['compared']} shots differ" + (f"; unstable: {', '.join(unstable[:4])}" if unstable else ""))

        data0 = tokens.extract(site)
        shoot.shoot(site, OUT / "trial-base", pages=["/"])
        caught, notes = 0, []
        for i, (name, selector) in enumerate(TRIALS, 1):
            old = set_token(css, selector, name)
            new, de = shifted(old)
            set_token(css, selector, name, new)
            want = expected_combos(data0, tokens.extract(site))
            shoot.shoot(site, OUT / f"trial-{i}", pages=["/"])
            got = changed_combos(diff.run(OUT / "trial-base", OUT / f"trial-{i}", OUT / f"trial-{i}-diff"))
            css.write_text(original_css)
            if got and got == want:
                caught += 1
            else:
                notes.append(f"--{name} in {selector} {old}->{new} (dE {de:.2f}): changed {sorted(got)}, expected {sorted(want)}")
        check(4, caught == len(TRIALS), f"{caught}/{len(TRIALS)} colour shifts of CIEDE2000 2 caught, each only on the "
                                        f"brand and mode it reaches" + (f"; {'; '.join(notes)}" if notes else ""))

        over = sorted(s["file"] for s in stable["shots"] if s["overflow"])
        want_over = sorted(f"{h}/{m}/390x844/{shoot.slug('/wide/')}.png" for h in ("alpha.invalid", "beta.invalid")
                           for m in ("dark", "light"))
        check(5, over == want_over, f"sideways overflow flagged on {len(over)} shots: the wide page at 390 px on both "
                                    f"brands and modes" + ("" if over == want_over else f"; got {over}"))

        hosts_seen = {h for h, _ in log}
        ok = (set(stable["blocked"]) == PLANTED and hosts_seen <= {"alpha.invalid", "beta.invalid"}
              and shoot.chrome_args(False, {"alpha.invalid"})[0] == "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost"
              and shoot.chrome_args(True, {"alpha.invalid"})[0].endswith("EXCLUDE localhost, EXCLUDE alpha.invalid")
              and not stable["errors"])
        check(6, ok, f"{len(stable['blocked'])} third-party URLs blocked and listed (planted {len(PLANTED)}); the local "
                     f"server saw only {sorted(hosts_seen)}; Chrome resolves no host name (live: only the site's)"
                     + ("" if set(stable["blocked"]) == PLANTED else f"; blocked {sorted(stable['blocked'])}"))

        facts = livecheck.seo(site, livecheck.Source(site, False), PAGES)
        a, b = facts["hosts"]["alpha.invalid"], facts["hosts"]["beta.invalid"]
        want = {
            "home 200": a["pages"]["/"]["status"] == 200,
            "canonical per host": a["pages"]["/"]["canonical"] == "https://alpha.invalid/"
            and b["pages"]["/"]["canonical"] == "https://beta.invalid/",
            "hreflang": a["pages"]["/"]["hreflang"] == [["en", "https://alpha.invalid/"], ["fi", "https://alpha.invalid/fi/"]],
            "slash redirect": a["pages"]["/about/"]["other_slash"] == {"path": "/about", "status": 308, "location": "/about/"},
            "robots noindex": a["pages"]["/wide/"]["robots"] == "noindex",
            "sitemap index and its child": a["sitemap"]["paths"] == ["/", "/about/"]
            and set(a["sitemap"]["files"]) == {"/sitemap.xml", "/sitemap-pages.xml"},
            "robots.txt": a["robots_txt"]["sitemaps"] == ["https://alpha.invalid/sitemap.xml"],
            "brand markers on every page": not a["brand"] and not b["brand"],
            "canonical from href, not data-href": a["pages"]["/"]["canonical"] == "https://alpha.invalid/",
        }
        check(7, all(want.values()), f"{sum(want.values())}/{len(want)} SEO facts right on both hosts"
                                     + (f"; wrong: {', '.join(k for k, v in want.items() if not v)}" if not all(want.values()) else ""))

        live_dir = work / "live-site"
        shutil.copytree(site_dir, live_dir)
        server2, base2, _ = fixture_server.start(live_dir)
        try:
            same = livecheck.compare(site, PAGES, None, stand_in=base2)
            n_assets = sum(len(v) for v in same["assets"].values())
            seen = {a["path"] for v in same["assets"].values() for a in v}
            font = live_dir / "public" / "assets" / "icons.woff2"
            font.write_bytes(font.read_bytes() + b" ")
            chunk = live_dir / "public" / "assets" / "chunk.js"
            chunk.write_text(chunk.read_text().replace('"1"', '"2"'))
            child = live_dir / "public" / "sitemap-pages.xml"
            child.write_text(child.read_text().replace("</urlset>", "  <url><loc>https://{{host}}/wide/</loc></url>\n</urlset>"))
            about = live_dir / "public" / "about" / "index.html"
            about.write_text(about.read_text().replace('href="https://{{host}}/about/"', 'href="https://{{host}}/about"'))
            moved = livecheck.compare(site, PAGES, None, stand_in=base2)
        finally:
            server2.shutdown()
        caught_font = sum(1 for p in moved["problems"] if "/assets/icons.woff2" in p)
        caught_chunk = sum(1 for p in moved["problems"] if "/assets/chunk.js" in p)
        caught_sitemap = sum(1 for p in moved["problems"] if " sitemap: differs" in p)
        caught_canon = sum(1 for p in moved["problems"] if "/about/ canonical" in p)
        deps = {"/assets/icons.woff2", "/assets/stripe-wide.svg", "/assets/chunk.js"} <= seen
        check(8, same["identical"] and deps and caught_font == 2 and caught_canon == 2 and caught_chunk == 2
              and caught_sitemap == 2,
              f"identical copy: {'equal' if same['identical'] else 'NOT equal'} over {n_assets} assets on 2 hosts, the "
              f"stylesheet's font, the srcset image and the script's chunk {'included' if deps else 'MISSING'}; caught on "
              f"2 hosts each: a changed font byte {caught_font}/2, a changed chunk {caught_chunk}/2, a changed child "
              f"sitemap {caught_sitemap}/2, a changed canonical {caught_canon}/2"
              + ("" if same["identical"] else f"; {same['problems'][:3]}"))

        base_dir, design = OUT / "baseline", OUT / "design"
        shutil.copytree(OUT / "shots-stable", base_dir / "shots")
        (base_dir / "seo.json").write_text(json.dumps(facts))
        design.mkdir()
        (design / "usage.json").write_text(json.dumps(data0))
        r_same = verify.run(site, base_dir, design, OUT / "verify-same", None, True)
        # A fresh process with the proxy set before lib.site is imported, as a shell with HTTP_PROXY would have it.
        env = dict(os.environ, HTTP_PROXY="http://127.0.0.1:9", http_proxy="http://127.0.0.1:9", NO_PROXY="", no_proxy="")
        probe = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); from lib.site import fetch; "
                                "print(fetch(sys.argv[2], '/', 'alpha.invalid')['status'])", str(SKILL / "scripts"), base],
                               capture_output=True, text=True, env=env)
        proxied = int(probe.stdout.strip()) if probe.stdout.strip().isdigit() else (probe.stderr.strip().splitlines() or ["?"])[-1]
        shoot.shoot(site, OUT / "reuse", pages=["/"])
        shoot.shoot(site, OUT / "reuse", pages=["/about/"])
        stale = [p.name for p in (OUT / "reuse").rglob("index.png")]
        shaky = json.loads((base_dir / "shots" / "manifest.json").read_text())
        shaky["shots"][0]["stable"] = False
        (base_dir / "shots" / "manifest.json").write_text(json.dumps(shaky))
        r_shaky = verify.run(site, base_dir, design, OUT / "verify-unstable", None, True)
        shaky["shots"][0]["stable"] = True
        (base_dir / "shots" / "manifest.json").write_text(json.dumps(shaky))
        check(13, proxied == 200 and not stale and not r_shaky["ok"] and bool(r_shaky["pixels"]["skipped_unstable"]),
              f"a local request ignores HTTP_PROXY ({proxied}); a reused shot folder keeps no stale shot ({len(stale)}); "
              f"an unstable baseline shot fails verify "
              f"({'fails' if not r_shaky['ok'] else 'PASSES (wrong)'})")
        old = set_token(css, '[data-brand="beta"]', "accent")
        set_token(css, '[data-brand="beta"]', "accent", shifted(old)[0])
        r_beta = verify.run(site, base_dir, design, OUT / "verify-beta", ["beta.invalid"], True)
        r_wrong = verify.run(site, base_dir, design, OUT / "verify-wrong-host", ["alpha.invalid"], True)
        css.write_text(original_css)
        set_token(css, ":root", "muted-foreground", "#a3a3a3")
        card = site_dir / "components" / "card.tsx"
        card_src = card.read_text()
        card.write_text(card_src.replace("<p className=\"text-teal\">", "<p style={{ color: \"#123456\" }}>New</p>\n      <p className=\"text-teal\">"))
        r_bad = verify.run(site, base_dir, design, OUT / "verify-bad", None, True)
        css.write_text(original_css)
        card.write_text(card_src)
        beta_changed = r_beta["pixels"]["changed"]
        ok = (r_same["ok"] and not r_same["pixels"]["changed"]
              and r_beta["ok"] and beta_changed and all(f.startswith("beta.invalid/") for f in beta_changed)
              and not r_wrong["ok"] and r_wrong["pixels"]["outside_expected_hosts"]
              and not r_bad["ok"] and not r_bad["contrast"]["ok"] and not r_bad["outside_tokens"]["ok"]
              and any(v["value"] == "#123456" for v in r_bad["outside_tokens"]["new_values"]))
        check(9, ok, f"unchanged: {'pass' if r_same['ok'] else 'FAIL'}; beta accent shifted: {len(beta_changed)} beta shots "
                     f"changed, {'pass' if r_beta['ok'] else 'FAIL'} with beta expected, "
                     f"{'fail' if not r_wrong['ok'] else 'PASS (wrong)'} with alpha expected; low contrast and #123456: "
                     f"contrast {'fail' if not r_bad['contrast']['ok'] else 'PASS (wrong)'}, outside tokens "
                     f"{'fail' if not r_bad['outside_tokens']['ok'] else 'PASS (wrong)'}")
        check_report(base)
        check_brandbook(base, log)
    finally:
        css.write_text(original_css)
        server.shutdown()

    cli = subprocess.run([sys.executable, str(SKILL / "scripts" / "tokens.py"), "extract", "--site",
                          str(FIXTURE / "tools" / "site.json"), "--out", str(OUT / "design-cli")], capture_output=True, text=True)
    cli_page = subprocess.run([sys.executable, str(SKILL / "scripts" / "tokens.py"), "page", "--site",
                               str(FIXTURE / "tools" / "site.json"), "--design", str(OUT / "design-cli")],
                              capture_output=True, text=True)
    leaks = [str(p.relative_to(REPO)) for p in list(OUT.rglob("*")) + list(work.rglob("*")) if p.is_file()
             and p.suffix in (".json", ".html", ".md", ".txt") and "fixtures" not in p.parts and "code-site" not in p.parts
             and "live-site" not in p.parts and KEY in p.read_text(errors="ignore")]
    leaks += ["tokens.py stdout"] if KEY in cli.stdout + cli.stderr + cli_page.stdout + cli_page.stderr else []
    n_files = sum(1 for p in OUT.rglob("*") if p.is_file() and p.suffix in (".json", ".html"))
    check(10, not leaks and cli.returncode == 0 and cli_page.returncode == 0,
          f"the dummy key is in none of {n_files} output files and no script output" + (f"; found in {leaks}" if leaks else ""))
    shutil.rmtree(work, ignore_errors=True)

    check_edges()
    check_newcomer()

    terms = denylist.load()
    hits = []
    for p in SKILL.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            text = p.read_text(errors="ignore").lower()
            hits += [f"{p.relative_to(SKILL)}: {t}" for t in sorted(denylist.hits(text, terms))]
            hits += [f"{p.relative_to(SKILL)}: {m[0]}" for m in re.finditer(r"[\w.+-]+@((?:[\w-]+\.)+[a-z]{2,})", text)
                     if m[1] not in ("example.com", "example.org", "example.net")
                     and m[1].rsplit(".", 1)[1] not in ("example", "invalid", "test")]
    check(11, not hits, f"src/ex-designer holds none of {len(terms)} denylisted names and no e-mail address"
                        + (f"; found: {', '.join(hits[:6])}" if hits else ""))
    print(f"\n{sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed in {round(time.time() - t0)} s")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
