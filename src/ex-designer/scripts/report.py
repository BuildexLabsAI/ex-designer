"""The audit report: each page of the site as one full-page screenshot with numbered markers on the elements a finding
names, next to one list that opens on the findings to fix first and switches to all of them, to the severe, moderate or
minor ones, or to the dropped items.

  python3 report.py --findings <audit>/data/findings.json --labels <skill>/templates/report-labels.json --lang fi \\
      --out <audit>/report.html

findings.json (the verified findings, one entry per finding; texts by the copy route):
  {"site": "example.com", "date": "2026-10-27",
   "pages": [{"id": "home", "url": "https://example.com/", "name": "example.com /"}],
   "findings": [{"id": "D2", "severity": "high|medium|low", "area": "cro|ux|seo|tech|privacy", "rank": 1,
                 "places": [{"page": "home", "selector": "form label", "text": "Email", "all": true}],
                 "text": {"fi": {"title": "…", "where": "…", "fix": "…"}, "en": {…}}}],
   "dropped": [{"id": "MV01", "area": "ux", "text": {"fi": {"title": "…", "reason": "…"}}}]}

`rank` (1, 2, 3…) puts a finding on the "fix these first" list. A place names the elements by a CSS selector, narrowed
by `text` (a part of their text) and, with `all`, every match instead of the first. A finding without places (DNS,
analytics, the whole site) gets a grey number. `dropped` (optional) lists what an automatic check flagged that the
auditor checked and did not count as a fault, each with the reason.
The pages are read live like a visitor reads them, from their own hosts only (http or https): every request to another
host is blocked and listed, redirects included. Only the report's own screenshots are kept, inside the report. A place
that matches nothing, a page that answers with an error and a page that moved (name it by its final address) stop the
report: exit 2, nothing written.
"""
import argparse
import base64
import html
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402
from shoot import CHROME_ARGS, NO_WEBRTC, Router, chrome_args, settle  # noqa: E402

SEVERITIES = ("high", "medium", "low")
AREAS = ("cro", "ux", "seo", "tech", "privacy")
DEFAULT_LABELS = {k: k for k in (
    "title", "checked", "first", "high", "medium", "low", "high_count_one", "high_count_other", "medium_count_one",
    "medium_count_other", "low_count_one", "low_count_other", "where", "fix", "pages", "lists", "screenshot",
    "marker", "tick", "no_place", "areas", "area_all", "area_cro", "area_ux", "area_seo", "area_tech",
    "area_privacy", "all", "dropped", "dropped_intro", "reason")}

BOXES = r"""(places) => places.map(p => {
  let els;
  try { els = [...document.querySelectorAll(p.selector)]; } catch (e) { return null; }
  if (p.text) els = els.filter(el => el.textContent.includes(p.text));
  // a site can render one part twice (one copy per screen size, the other hidden): the first visible match counts
  els = els.filter(el => el.checkVisibility({visibilityProperty: true}));
  const boxes = els.map(el => { const r = el.getBoundingClientRect();
                                return [r.x, r.y + scrollY, r.width, r.height].map(Math.round); })
                   .filter(b => b[2] > 0 && b[3] > 0);
  return p.all ? boxes : boxes.slice(0, 1);
})"""


# What a screenshot with animations disabled shows: a finite animation at its end, an endless one at its start. The
# boxes are measured in that same state, so an outline never marks where a moving element was a moment earlier.
STILL = r"""() => { for (const a of document.getAnimations()) {
  try { if (a.effect.getComputedTiming().endTime === Infinity) a.cancel(); else a.finish(); } catch (e) { a.cancel(); } } }"""


def load_labels(path: str | None, lang: str) -> dict:
    labels = json.loads(Path(path).read_text()) if path else {}
    return {**DEFAULT_LABELS, **(labels.get(lang) or labels.get("en") or {})}


def capture(pages: list, places: dict, width: int = 1280, height: int = 800) -> tuple[dict, list, list]:
    """Per page: its full-page screenshot (JPEG) and size, and the boxes of each place on it. Pages without places
    are not opened. Chrome reaches only the pages' own hosts, as in `shoot.py --live`. Returns ({page id: {...}},
    [pages that answered with an error and places that matched nothing], [blocked requests])."""
    from playwright.sync_api import sync_playwright
    shots, missing = {}, []
    router = Router({urlsplit(pg["url"]).hostname for pg in pages}, None, True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", args=chrome_args(True, router.hosts))
        try:
            for pg in pages:
                wanted = places.get(pg["id"], [])
                if not wanted:
                    continue
                ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1,
                                          locale="en-US", service_workers="block")
                ctx.add_init_script(NO_WEBRTC)
                ctx.route("**/*", router)
                ctx.route_web_socket(re.compile(".*"), lambda ws: None)
                page = ctx.new_page()
                try:
                    resp = page.goto(pg["url"], wait_until="load", timeout=45000)
                    status = resp.status if resp else None
                    if not status or status >= 400:  # an error page is not the page: nothing on it is evidence
                        missing.append(f"{pg['url']} answered HTTP {status}")
                        continue
                    if pg["url"] in router.moved:  # its content would stand under the old address
                        missing.append(f"{pg['url']} redirects to {router.moved[pg['url']]}: use that address")
                        continue
                    settle(page, height)
                    page.evaluate(STILL)
                    boxes = page.evaluate(BOXES, [w["place"] for w in wanted])
                    jpg = page.screenshot(full_page=True, type="jpeg", quality=80, animations="disabled", caret="hide",
                                          scale="css")
                finally:
                    ctx.close()
                pw, h = Image.open(io.BytesIO(jpg)).size  # wider than the window when the page overflows sideways
                for w, b in zip(wanted, boxes):
                    # an element that starts above the page or runs past its end (a hero video) is cut to the page
                    b = [[x, max(0, y), bw, min(h, y + bh) - max(0, y)] for x, y, bw, bh in (b or [])
                         if min(h, y + bh) > max(0, y)]
                    if not b:
                        missing.append(f"{w['finding']}: {w['place']['selector']} on {pg['url']}")
                    w["boxes"] = b
                shots[pg["id"]] = {"w": pw, "h": h, "jpg": jpg}
        finally:
            browser.close()
    return shots, missing, sorted(router.blocked)


def build(data: dict, labels: dict, lang: str, shots: dict, places: dict) -> str:
    """The report page, rendered by its own script; `prerender` then saves what the script drew."""
    e = html.escape
    L = labels
    names = {pg["id"]: pg.get("name") or pg["url"] for pg in data["pages"]}
    items = []
    for f in data["findings"]:
        text = f["text"].get(lang) or f["text"].get("en") or next(iter(f["text"].values()))
        boxes = [{"page": w["page"], "box": b}
                 for w in places.get("_by_finding", {}).get(f["id"], []) for b in w["boxes"]]
        items.append({"id": f["id"], "sev": f["severity"], "area": f["area"], "rank": f.get("rank"),
                      "title": text["title"], "where": text["where"], "fix": text["fix"], "places": boxes})
    dropped = []
    for f in data.get("dropped", []):
        text = f["text"].get(lang) or f["text"].get("en") or next(iter(f["text"].values()))
        dropped.append({"id": f["id"], "area": f["area"], "title": text["title"], "reason": text["reason"], "places": []})
    shown = [pg for pg in data["pages"] if pg["id"] in shots]
    imgs = "".join(
        f"<img data-page='{e(pg['id'])}' alt='{e(L['screenshot'].format(page=names[pg['id']]))}' "
        f"src='data:image/jpeg;base64,{base64.b64encode(shots[pg['id']]['jpg']).decode()}'"
        f"{'' if i == 0 else ' hidden'}>" for i, pg in enumerate(shown))
    model = {"pages": [{"id": pg["id"], "name": names[pg["id"]], "w": shots[pg["id"]]["w"], "h": shots[pg["id"]]["h"]}
                       for pg in shown],
             "items": items, "dropped": dropped,
             "L": {k: L[k] for k in ("first", "all", "high", "medium", "low", "dropped", "dropped_intro", "where", "fix",
                                   "reason", "marker", "tick", "no_place", "area_all", *(f"area_{a}" for a in AREAS))},
             "counts": {s: [L[f"{s}_count_one"], L[f"{s}_count_other"]] for s in SEVERITIES}}
    blob = json.dumps(model, ensure_ascii=False).replace("<", "\\u003c")  # no text can close the script tag
    fills = {"__LANG__": "fi" if lang == "fi" else "en", "__TITLE__": e(L["title"].format(site=data["site"])),
             "__CHECKED__": e(L["checked"].format(date=data["date"])), "__PAGES__": e(L["pages"]),
             "__LISTS__": e(L["lists"]), "__AREAS__": e(L["areas"]), "__IMGS__": imgs, "__DATA__": blob}
    # one pass: a placeholder name inside a finding's text is text, never filled again
    return re.sub("|".join(fills), lambda m: fills[m.group(0)], TEMPLATE)


def prerender(page_html: str, out: Path) -> dict:
    """Run the report's script once and save the page it drew, so the list and the markers show without JavaScript
    (some previews run none). The script runs again on load and draws the same."""
    from playwright.sync_api import sync_playwright
    out.write_text(page_html)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", args=CHROME_ARGS)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(out.resolve().as_uri())
            page.wait_for_timeout(300)
            facts = page.evaluate("""() => ({items: document.querySelectorAll('.item').length,
                                             markers: document.querySelectorAll('.marker').length})""")
            drawn = "<!doctype html>\n" + page.evaluate("document.documentElement.outerHTML")
        finally:
            browser.close()
    if errors:
        raise SystemExit(f"the report's script failed: {errors[0]}")
    out.write_text(drawn)
    return facts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--labels")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1280)
    args = ap.parse_args()
    data = json.loads(Path(args.findings).read_text())
    for pg in data["pages"]:
        if urlsplit(pg["url"]).scheme not in ("http", "https"):
            raise SystemExit(f"{pg['id']}: the page must be an http or https URL, not {pg['url']!r}")
    pages = {pg["id"] for pg in data["pages"]}
    places, by_finding = {}, {}
    for f in data["findings"]:
        if f["severity"] not in SEVERITIES:
            raise SystemExit(f"{f['id']}: severity must be one of {', '.join(SEVERITIES)}")
        if f.get("area") not in AREAS:
            raise SystemExit(f"{f['id']}: area must be one of {', '.join(AREAS)}")
        for pl in f.get("places", []):
            if pl["page"] not in pages:
                raise SystemExit(f"{f['id']}: no page {pl['page']!r} in pages")
            w = {"finding": f["id"], "page": pl["page"], "place": pl}
            places.setdefault(pl["page"], []).append(w)
            by_finding.setdefault(f["id"], []).append(w)
    for f in data.get("dropped", []):
        if f.get("area") not in AREAS:
            raise SystemExit(f"{f['id']}: area must be one of {', '.join(AREAS)}")
    shots, missing, blocked = capture(data["pages"], places, args.width)
    if missing:
        print("Nothing written. Fix these first (an error page, a page that moved, or a selector that matches nothing on "
              "the live page):\n  " + "\n  ".join(missing))
        return 2
    places["_by_finding"] = by_finding
    labels = load_labels(args.labels, args.lang)
    facts = prerender(build(data, labels, args.lang, shots, places), Path(args.out))
    placed = sum(len(w["boxes"]) for ws in by_finding.values() for w in ws)
    print(f"wrote {args.out}: {len(data['findings'])} findings, {len(data.get('dropped', []))} dropped, {placed} places "
          f"on {len(shots)} pages; first list {facts['items']} items, {facts['markers']} markers; "
          f"{len(blocked)} requests to other hosts blocked" + "".join(f"\n  {u}" for u in blocked))
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--paper:#F4F5F7;--panel:#fff;--ink:#14161B;--quiet:#5A6170;--rule:#DDE0E5;--red:#D93A33;--red-bg:#FDE8E7;--red-ink:#B42C25;--amber-bg:#FDF1DC;--amber-ink:#8A5300;--grey-bg:#ECEEF1;--grey-ink:#4A505C;--none:#9AA0A8}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 "Avenir Next","Segoe UI",system-ui,sans-serif}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;padding:20px 28px 14px}
h1{margin:0;font-size:26px;line-height:1.2;letter-spacing:-.01em}
header p{margin:0;color:var(--quiet)}
main{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(270px,1fr);gap:20px;height:calc(100vh - 78px);padding:0 28px 24px}
.panel{display:flex;flex-direction:column;min-height:0;background:var(--panel);border:1px solid var(--rule);border-radius:14px}
.pages{display:flex;flex-wrap:wrap;gap:6px;padding:14px 20px 10px}
.pagebtn{padding:5px 12px;border:1px solid var(--rule);border-radius:8px;background:none;color:var(--ink);font:600 14px/1.3 inherit;cursor:pointer}
.pagebtn[aria-pressed=true]{background:var(--ink);border-color:var(--ink);color:#fff}
.view{position:relative;display:flex;flex:1;gap:10px;min-height:0;padding:0 12px 14px 20px}
.noplace{position:absolute;left:36px;right:42px;top:24px;display:grid;grid-template-columns:32px 1fr;gap:4px 14px;padding:18px 20px;border-radius:12px;background:var(--panel);box-shadow:0 8px 30px rgba(0,0,0,.35)}
.noplace[hidden]{display:none}
.noplace .num{grid-row:span 3}
.noplace p{margin:0}
.viewer{position:relative;flex:1;overflow-y:auto;border-radius:8px;background:#e6e8ec;scroll-behavior:smooth}
.shot{position:relative}
.shot img{display:block;width:100%;height:auto}
.shot img[hidden]{display:none}
.rail{position:relative;width:14px;border-radius:7px;background:#E6E8EC;cursor:pointer}
.win{position:absolute;left:0;right:0;border-radius:7px;background:rgba(20,22,27,.16);pointer-events:none}
.tick{position:absolute;left:1px;right:1px;height:6px;margin-top:-3px;padding:0;border:0;border-radius:3px;background:var(--red);cursor:pointer}
.outline{position:absolute;border:2px solid var(--red);border-radius:6px;pointer-events:none}
.outline.on{border-width:3px;background:rgba(217,58,51,.16)}
.outline.pulse{animation:pulse .8s ease-out 2}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(217,58,51,.7)}100%{box-shadow:0 0 0 16px rgba(217,58,51,0)}}
.marker{position:absolute;display:grid;place-items:center;width:26px;height:26px;margin:-13px 0 0 -13px;padding:0;border:2px solid #fff;border-radius:50%;background:var(--red);color:#fff;font:700 13px/1 inherit;box-shadow:0 1px 4px rgba(0,0,0,.45);cursor:pointer}
button:focus-visible{outline:3px solid #2563EB;outline-offset:2px}
.tabs{display:flex;flex-wrap:wrap;gap:8px;padding:16px 20px 10px}
.tab{padding:7px 14px;border:0;border-radius:999px;font:600 14px/1.3 inherit;cursor:pointer}
.tab[data-k=first],.tab[data-k=all],.tab[data-k=dropped]{background:#EEF0F3;color:var(--ink)}
.tab[data-k=high]{background:var(--red-bg);color:var(--red-ink)}
.tab[data-k=medium]{background:var(--amber-bg);color:var(--amber-ink)}
.tab[data-k=low]{background:var(--grey-bg);color:var(--grey-ink)}
.tab[aria-selected=true]{background:var(--ink);color:#fff}
.areas{display:flex;flex-wrap:wrap;gap:6px;padding:0 20px 8px}
.areabtn{padding:4px 11px;border:1px solid var(--rule);border-radius:8px;background:none;color:var(--ink);font:600 13px/1.3 inherit;cursor:pointer}
.areabtn[aria-pressed=true]{background:#E4E7EC;border-color:#C9CDD3}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.area{padding:1px 9px;border:1px solid var(--rule);border-radius:6px;color:var(--quiet);font-size:13px;font-weight:600}
.intro{margin:0;padding:4px 20px 6px;color:var(--quiet);font-size:14px}
.intro[hidden]{display:none}
.item.dropped{cursor:default}
.item.dropped:hover{background:none}
.list{flex:1;margin:0;padding:2px 12px 16px;overflow-y:auto;list-style:none}
.list li+li{border-top:1px solid var(--rule)}
.item{display:grid;grid-template-columns:32px 1fr;gap:5px 14px;width:100%;margin:6px 0;padding:12px 10px;border:0;border-radius:10px;background:none;color:inherit;font:inherit;text-align:left;cursor:pointer}
.item:hover{background:#F6F7F9}
.item.active{background:#EFF1F4;box-shadow:inset 3px 0 0 var(--ink)}
.num{display:grid;place-items:center;grid-row:span 5;width:30px;height:30px;border-radius:50%;background:var(--red);color:#fff;font-weight:700}
.num.none{background:var(--none)}
.sev{justify-self:start;padding:2px 10px;border-radius:6px;font-size:13px;font-weight:600}
.sev.high{background:var(--red-bg);color:var(--red-ink)}
.sev.medium{background:var(--amber-bg);color:var(--amber-ink)}
.sev.low{background:var(--grey-bg);color:var(--grey-ink)}
.title{font-size:16px;font-weight:700;line-height:1.35}
.meta{color:var(--quiet);font-size:14px}
.meta b{color:var(--ink);font-weight:600}
.dots{display:flex;gap:5px;padding-top:2px}
.dots i{width:8px;height:8px;border-radius:50%;background:#C9CDD3}
.dots i.cur{background:var(--red)}
@media (max-width:640px){main{grid-template-columns:1fr;height:auto;padding:0 16px 20px}header{padding:16px}.view{flex:none;height:48vh;padding:0 10px 12px 14px}.list{overflow:visible}}
@media (prefers-reduced-motion:reduce){.viewer{scroll-behavior:auto}.outline.pulse{animation:none}}
</style>
</head>
<body>
<header><h1>__TITLE__</h1><p>__CHECKED__</p></header>
<main>
  <section class="panel">
    <div class="pages" id="pages" role="group" aria-label="__PAGES__"></div>
    <div class="view">
      <div class="viewer" id="viewer" tabindex="0"><div class="shot" id="shot">__IMGS__</div></div>
      <div class="rail" id="rail"><div class="win" id="win"></div></div>
      <div class="noplace" id="noplace" role="status" hidden></div>
    </div>
  </section>
  <section class="panel">
    <div class="tabs" id="tabs" role="tablist" aria-label="__LISTS__"></div>
    <div class="areas" id="areas" role="group" aria-label="__AREAS__"></div>
    <p class="intro" id="intro" hidden></p>
    <ol class="list" id="list" role="tabpanel"></ol>
  </section>
</main>
<script type="application/json" id="model">__DATA__</script>
<script>
const M = JSON.parse(document.getElementById("model").textContent);
const L = M.L, PAGES = Object.fromEntries(M.pages.map(p => [p.id, p]));
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = id => document.getElementById(id);
const intro = $("intro"), noplace = $("noplace"), viewer = $("viewer"), shot = $("shot"), rail = $("rail"), win = $("win"), list = $("list"), tabs = $("tabs"), pages = $("pages"), areas = $("areas");
let area = "all", tab = "first", page = M.pages.length ? M.pages[0].id : null, active = null, at = 0;

const SEVS = ["high", "medium", "low"];
const inArea = d => area === "all" || d.area === area;
const listFor = k => k === "first" ? M.items.filter(d => d.rank && inArea(d)).sort((a, b) => a.rank - b.rank)
                   : k === "all" ? M.items.filter(inArea).sort((a, b) => SEVS.indexOf(a.sev) - SEVS.indexOf(b.sev))
                   : k === "dropped" ? M.dropped.filter(inArea)
                   : M.items.filter(d => d.sev === k && inArea(d));
const pct = (v, of) => (v / of * 100) + "%";
const el = (tag, cls, text) => { const x = document.createElement(tag); if (cls) x.className = cls; if (text != null) x.textContent = text; return x; };
const fill = (s, vals) => s.replace(/\{(\w+)\}/g, (m, k) => k in vals ? vals[k] : m);
function anchor([x, y, w, h], W) {
  if (w > W * 0.6) return [x + 28, y + 28];
  // clear of the element's outline, so a small element (a number, a label) stays readable next to its marker
  if (x - 16 < 16) return [Math.min(x + w + 22, W - 16), y + h / 2];
  return [Math.max(x - 22, 16), y + h / 2];
}

function renderAreas() {
  const present = ["cro", "ux", "seo", "tech", "privacy"].filter(a => M.items.concat(M.dropped).some(d => d.area === a));
  areas.replaceChildren(...["all", ...present].map(a => {
    const b = el("button", "areabtn", L["area_" + a]);
    b.dataset.a = a; b.setAttribute("aria-pressed", a === area);
    b.onclick = () => { area = a; active = null; at = 0; noplace.hidden = true; render(); viewer.scrollTo({top: 0}); };
    return b;
  }));
}

function renderTabs() {
  renderAreas();
  const keys = ["first", "all", ...SEVS, "dropped"].filter(k => listFor(k).length);
  if (!keys.includes(tab)) tab = keys[0];
  tabs.replaceChildren(...keys.map(k => {
    const n = listFor(k).length;
    const b = el("button", "tab", k === "first" ? L.first : k in M.counts ? fill(M.counts[k][n === 1 ? 0 : 1], {n}) : fill(L[k], {n}));
    b.dataset.k = k; b.setAttribute("role", "tab"); b.setAttribute("aria-selected", k === tab);
    b.onclick = () => { tab = k; active = null; at = 0; noplace.hidden = true; render(); viewer.scrollTo({top: 0}); };
    return b;
  }));
}

function renderPages() {
  pages.replaceChildren(...M.pages.map(p => {
    const b = el("button", "pagebtn", p.name);
    b.setAttribute("aria-pressed", p.id === page);
    b.onclick = () => { page = p.id; noplace.hidden = true; drawShot(); viewer.scrollTo({top: 0}); };
    return b;
  }));
  shot.querySelectorAll("img").forEach(img => { img.hidden = img.dataset.page !== page; });
}

function drawShot() {
  renderPages();
  shot.querySelectorAll(".outline,.marker").forEach(x => x.remove());
  rail.querySelectorAll(".tick").forEach(x => x.remove());
  if (!page) return;
  const W = PAGES[page].w, H = PAGES[page].h, taken = [];
  const k = (shot.clientWidth || W) / W;  // markers have a fixed size on screen: keep them apart in screen pixels
  listFor(tab).forEach((d, i) => d.places.forEach((p, j) => {
    if (p.page !== page) return;
    const [x, y, w, h] = p.box, n = i + 1;
    // two findings on one element, or on two close ones: the next free spot on the element's own row (left, then
    // right), only then below it
    const [ax, ay] = anchor(p.box, W), gap = 30 / k;
    const free = ([sx, sy]) => !taken.some(([tx, ty]) => Math.abs(tx - sx) < gap && Math.abs(ty - sy) < gap);
    const row = [1, 2].flatMap(i => [[ax - gap * i, ay], [ax + gap * i, ay]]).filter(([sx]) => sx >= gap / 2 && sx <= W - gap / 2);
    let [cx, cy] = [[ax, ay], ...row].find(free) || [ax, ay];
    while (!free([cx, cy])) cy += gap;
    cx = Math.min(Math.max(cx, gap / 2), W - gap / 2);  // the whole marker stays on the screenshot
    taken.push([cx, cy]);
    const o = el("div", "outline"); o.dataset.id = d.id; o.dataset.j = j;
    Object.assign(o.style, {left: pct(x - 6, W), top: pct(y - 6, H), width: pct(w + 12, W), height: pct(h + 12, H)});
    const m = el("button", "marker", n); m.dataset.id = d.id;
    m.setAttribute("aria-label", fill(L.marker, {n, title: d.title}));
    Object.assign(m.style, {left: pct(cx, W), top: pct(cy, H)});
    const pick = () => { active = d.id; at = j; mark(); go(d); list.querySelector(`.item[data-id="${d.id}"]`).scrollIntoView({block: "nearest"}); };
    m.onclick = pick;
    const t = el("button", "tick"); t.style.top = pct(cy, H); t.setAttribute("aria-label", fill(L.tick, {n}));
    t.onclick = ev => { ev.stopPropagation(); pick(); };
    shot.append(o, m); rail.append(t);
  }));
  mark(); sync();
}

function render() {
  renderTabs();
  intro.hidden = tab !== "dropped";
  intro.textContent = L.dropped_intro;
  if (tab === "dropped") {  // checked and not counted as faults: no marker, nothing to open
    list.replaceChildren(...listFor(tab).map((d, i) => {
      const li = el("li"), x = el("div", "item dropped");
      const chips = el("span", "chips");
      chips.append(el("span", "area", L["area_" + d.area]));
      const why = el("span", "meta"); why.append(el("b", null, L.reason + " "), d.reason);
      x.append(el("span", "num none", i + 1), chips, el("span", "title", d.title), why);
      li.append(x);
      return li;
    }));
    drawShot();
    return;
  }
  list.replaceChildren(...listFor(tab).map((d, i) => {
    const li = el("li"), b = el("button", "item");
    b.dataset.id = d.id;
    const chips = el("span", "chips");
    chips.append(el("span", "sev " + d.sev, L[d.sev]), el("span", "area", L["area_" + d.area]));
    b.append(el("span", "num" + (d.places.length ? "" : " none"), i + 1), chips, el("span", "title", d.title));
    const where = el("span", "meta"); where.append(el("b", null, L.where + " "), d.where);
    const fix = el("span", "meta"); fix.append(el("b", null, L.fix + " "), d.fix);
    b.append(where, fix);
    if (d.places.length > 1) { const dots = el("span", "dots"); d.places.forEach(() => dots.append(el("i"))); b.append(dots); }
    b.onclick = () => { if (active === d.id && d.places.length > 1) at = (at + 1) % d.places.length; else { active = d.id; at = 0; } mark(); go(d); };
    li.append(b);
    return li;
  }));
  drawShot();
}

function mark() {
  list.querySelectorAll(".item").forEach(b => {
    b.classList.toggle("active", b.dataset.id === active);
    b.querySelectorAll(".dots i").forEach((i, j) => i.classList.toggle("cur", b.dataset.id === active && j === at));
  });
  shot.querySelectorAll(".outline").forEach(o => o.classList.toggle("on", o.dataset.id === active && +o.dataset.j === at));
}

function go(d) {
  noplace.hidden = !!d.places.length;
  if (!d.places.length) {  // nothing to point at on a page: say so over the screenshot, with what it concerns
    const n = listFor(tab).indexOf(d) + 1;
    noplace.replaceChildren(el("span", "num none", n), el("p", "title", d.title), el("p", "meta", L.no_place),
                            el("p", "meta", d.where));
    return;
  }
  const p = d.places[at];
  if (p.page !== page) { page = p.page; drawShot(); }
  const [x, y, w, h] = p.box, k = shot.offsetHeight / PAGES[page].h;
  if (matchMedia("(max-width: 640px)").matches) viewer.scrollIntoView({block: "nearest", behavior: still ? "auto" : "smooth"});
  viewer.scrollTo({top: (y + h / 2) * k - viewer.clientHeight / 2, behavior: still ? "auto" : "smooth"});
  const o = shot.querySelector(`.outline[data-id="${d.id}"][data-j="${at}"]`);
  if (o) { o.classList.remove("pulse"); void o.offsetWidth; o.classList.add("pulse"); }
}

function sync() {
  const s = viewer.scrollHeight || 1;
  win.style.top = pct(viewer.scrollTop, s); win.style.height = pct(viewer.clientHeight, s);
}
viewer.addEventListener("scroll", sync);
addEventListener("resize", () => drawShot());
rail.addEventListener("click", ev => {
  const r = rail.getBoundingClientRect();
  viewer.scrollTo({top: (ev.clientY - r.top) / r.height * viewer.scrollHeight - viewer.clientHeight / 2, behavior: still ? "auto" : "smooth"});
});
shot.querySelectorAll("img").forEach(img => img.addEventListener("load", sync));
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
