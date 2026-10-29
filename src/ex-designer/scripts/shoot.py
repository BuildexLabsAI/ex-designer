"""Screenshots of every page, host, size and mode of a site, made so that an unchanged site gives the same pixels.

  python3 shoot.py --site tools/site.json --out baseline/shots [--runs 3] [--live] [--pages / /about/]

The browser asks for https://<host>/<page> as on the live site. Without --live, each request for one of the site's
hosts is answered by the local build (site.json serve.url) with that host in the Host header, so a site that picks
its brand by Host shows each brand; every other request (trackers, fonts, CDNs, APIs) is blocked and listed. The
browser also resolves no host name at all, so nothing leaves the machine even if a request slips past the router.
With --live the site's own hosts load from the internet and third parties are still blocked.

The browser is the Mac's own Google Chrome (Playwright channel "chrome"); its version goes into the manifest,
because a Chrome update can move anti-aliased pixels: shots are compared only with shots of the same version.
Dark mode: Chrome reports prefers-color-scheme: dark; when site.json has "dark": {"class": "dark", "storage":
{"theme": "dark"}}, the storage keys are set before the page's scripts run, the class is put on <html>, and each shot
checks that the class is on in dark mode and off in light mode (mode_ok in the manifest).
For still pixels: time is fixed, Math.random is seeded, reduced motion is on, CSS animations are stopped, the caret
is hidden, and video, canvas, iframe and site.json "mask" selectors are covered. With --runs N each shot is taken N
times in fresh browser contexts; a shot joins the diff suite ("stable") only when all N are identical.
Writes <out>/<host>/<mode>/<w>x<h>/<page>.png and <out>/manifest.json (stability, sideways overflow, statuses,
blocked requests).
"""
import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.site import Site, fetch, is_local, sitemap_paths  # noqa: E402

FIXED_TIME = "2026-01-01T12:00:00Z"
DEFAULT_MASK = ["video", "canvas", "iframe"]
MASK_COLOR = "#FF00FF"
CHROME_ARGS = ["--force-color-profile=srgb", "--font-render-hinting=none", "--disable-lcd-text", "--hide-scrollbars",
               "--disable-gpu", "--disable-features=InterestFeedContentSuggestions,Translate,OptimizationHints,MediaRouter",
               "--disable-background-networking", "--disable-component-update", "--no-first-run",
               "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]


def chrome_args(live: bool, hosts) -> list[str]:
    """Chrome resolves no host name at all in local mode; live, only the site's own hosts."""
    keep = ["localhost"] + (sorted(hosts) if live else [])
    return ["--host-resolver-rules=MAP * ~NOTFOUND, " + ", ".join(f"EXCLUDE {h}" for h in keep)] + CHROME_ARGS
SEED_RANDOM = """(() => { let s = 20261027; Math.random = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; })();"""
# WebRTC sends UDP past every HTTP router and host-name rule: the page gets no WebRTC at all.
NO_WEBRTC = """for (const k of ["RTCPeerConnection", "webkitRTCPeerConnection", "RTCDataChannel", "RTCRtpTransceiver"]) {
  try { Object.defineProperty(window, k, { value: undefined, configurable: false, writable: false }); } catch (e) {} }"""


def slug(page: str) -> str:
    """A file name for a page path: readable, and unique because every page but / carries a hash of its exact path."""
    if page == "/":
        return "index"
    s = re.sub(r"[^A-Za-z0-9._-]", "-", page.strip("/").replace("/", "__"))[:80]
    return f"{s}~{hashlib.sha1(page.encode()).hexdigest()[:8]}"


def pages_of(site: Site, server: str | None, live: bool) -> dict[str, list[str]]:
    """The pages to shoot on each host: site.json "pages" for every host, or each host's own sitemap (sitemap indexes
    followed)."""
    hosts = [h["name"] for h in site.hosts]
    if site.get("pages"):
        return {h: list(site.get("pages")) for h in hosts}
    out = {}
    for h in hosts:
        get = (lambda path, h=h: fetch(f"https://{h}", path)) if live else (lambda path, h=h: fetch(server, path, h))
        out[h] = sitemap_paths(get, site.get("sitemap", "/sitemap.xml")) or ["/"]
    return out


class Router:
    """Answers the site's hosts from the local build (or fetches them live) and blocks everything else."""

    def __init__(self, hosts: set[str], server: str | None, live: bool):
        self.hosts, self.server, self.live = hosts, server, live
        self.blocked, self.errors, self.served, self.moved = set(), [], 0, {}

    def allowed(self, url: str) -> bool:
        """A URL a page may load: one of the site's hosts, or (local mode) the local build itself, at its own port:
        no other service on this machine."""
        u = urlsplit(url)
        if u.hostname in self.hosts and u.scheme in ("http", "https"):
            return True
        return not self.live and is_local(url) and u.netloc == urlsplit(self.server).netloc

    @staticmethod
    def follow(url: str, loc: str) -> str:
        """A redirect's target as Chrome reads it: tabs and line breaks dropped, a backslash taken as a slash."""
        return urljoin(url, re.sub(r"[\t\n\r]", "", loc).strip().replace("\\", "/"))

    def __call__(self, route):
        req = route.request
        u = urlsplit(req.url)
        if u.scheme in ("data", "blob", "about"):
            route.continue_()
            return
        if not self.allowed(req.url):
            self.blocked.add(req.url.split("#")[0][:300])
            route.abort("blockedbyclient")
            return
        if self.live:
            self.fetch_live(route)
            return
        # Local mode: Playwright fetches every request itself and hands the browser the answer, redirects included,
        # so a redirect can never take Chrome off this machine: its target is checked here (a later hop of the chain
        # is not routed again, but it names the site's host, which Chrome cannot resolve).
        local = is_local(req.url)
        base = f"{u.scheme}://{u.netloc}" if local else self.server.rstrip("/")
        target = base + (u.path or "/") + (f"?{u.query}" if u.query else "")
        headers = {k: v for k, v in req.headers.items() if k.lower() not in ("host", "accept-encoding")}
        if not local:
            headers["host"] = u.hostname
        try:
            resp = route.fetch(url=target, headers=headers, max_redirects=0, timeout=30000)
        except Exception as e:  # noqa: BLE001  any fetch failure is reported, not raised mid-page
            self.errors.append(f"{req.url}: {str(e).splitlines()[0][:160]}")
            route.abort("failed")
            return
        out = dict(resp.headers)
        loc = out.get("location")
        if loc:
            if loc.startswith(self.server.rstrip("/")) and not local:
                loc = f"https://{u.hostname}" + loc[len(self.server.rstrip("/")):]
            if not self.allowed(self.follow(req.url, loc)):
                self.blocked.add(f"redirect to {self.follow(req.url, loc)[:280]}")
                route.abort("blockedbyclient")
                return
            out["location"] = self.follow(req.url, loc)
        route.fulfill(response=resp, headers=out)
        self.served += 1

    def fetch_live(self, route):
        """Live mode: Chrome would follow a redirect chain past the router (only its first request is routed), so the
        router walks the whole chain itself, checks every hop and hands Chrome the final answer. A page that moved is
        noted in `moved`: its content then stands under the old address."""
        req, url = route.request, route.request.url
        for _ in range(10):
            try:
                resp = route.fetch(url=url, max_redirects=0, timeout=30000)
            except Exception as e:  # noqa: BLE001  any fetch failure is reported, not raised mid-page
                self.errors.append(f"{req.url}: {str(e).splitlines()[0][:160]}")
                route.abort("failed")
                return
            loc = resp.headers.get("location")
            if not (300 <= resp.status < 400 and loc):
                break
            url = self.follow(url, loc)
            if not self.allowed(url):
                self.blocked.add(f"redirect to {url[:280]}")
                route.abort("blockedbyclient")
                return
        else:
            self.errors.append(f"{req.url}: more than 10 redirects")
            route.abort("failed")
            return
        if url != req.url and req.is_navigation_request():
            self.moved[req.url] = url
        route.fulfill(response=resp)
        self.served += 1


def settle(page, h: int):
    """Lazy content loaded (one pass down the page), back to the top, fonts and network done."""
    page.add_style_tag(content="html, body { scroll-behavior: auto !important; }")
    y = 0
    for _ in range(80):
        if y >= page.evaluate("document.scrollingElement.scrollHeight"):
            break
        page.evaluate("(y) => window.scrollTo(0, y)", y)
        page.wait_for_timeout(60)
        y += int(h * 0.8)
    page.evaluate("window.scrollTo(0, 0)")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:  # noqa: BLE001  a page that never idles is still shot; instability shows in the runs
        pass
    page.evaluate("document.fonts.ready.then(() => true)")
    page.evaluate("""() => { for (const v of document.querySelectorAll('video')) { v.pause(); try { v.currentTime = 0; } catch (e) {} } }""")
    page.wait_for_timeout(150)


def mode_script(mode: str, dark: dict | None) -> str:
    """Before the page's own scripts: the theme's storage keys; after it loads: the dark class on <html>."""
    if not dark:
        return ""
    cls = dark.get("class", "dark")
    store = dark.get("storage", {}) if mode == "dark" else dark.get("light_storage", {})
    sets = "".join(f"try {{ localStorage.setItem({json.dumps(k)}, {json.dumps(v)}); }} catch (e) {{}}" for k, v in store.items())
    on = "add" if mode == "dark" else "remove"
    return (f"{sets} document.addEventListener('DOMContentLoaded', () => "
            f"document.documentElement.classList.{on}({json.dumps(cls)}));")


def capture(browser, router, url, w, h, mode, masks, dark=None):
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, color_scheme=mode,
                              reduced_motion="reduce", service_workers="block", locale="en-US", timezone_id="UTC")
    ctx.add_init_script(SEED_RANDOM)
    ctx.add_init_script(NO_WEBRTC)
    if mode_script(mode, dark):
        ctx.add_init_script(mode_script(mode, dark))
    ctx.route("**/*", router)
    ctx.route_web_socket(re.compile(".*"), lambda ws: None)
    page = ctx.new_page()
    page.clock.set_fixed_time(FIXED_TIME)
    navs = []
    page.on("response", lambda r: navs.append(r.status)
            if r.request.is_navigation_request() and r.frame == page.main_frame else None)
    try:
        resp = page.goto(url, wait_until="load", timeout=45000)
        settle(page, h)
        facts = page.evaluate("""(cls) => ({ scrollWidth: document.scrollingElement.scrollWidth, innerWidth: window.innerWidth,
                                           title: document.title, dark: cls ? document.documentElement.classList.contains(cls) : null })""",
                              (dark or {}).get("class", "dark") if dark else None)
        facts["mode_ok"] = facts.pop("dark") in (None, mode == "dark")
        png = page.screenshot(full_page=True, animations="disabled", caret="hide", scale="css",
                              mask=[page.locator(s) for s in masks], mask_color=MASK_COLOR)
        facts["status"] = navs[-1] if navs else (resp.status if resp else None)  # where the page ended up
        facts["final_url"] = page.url
    finally:
        ctx.close()
    return png, facts


def clear(out: Path):
    """An empty folder for the shots: a folder an earlier run made (it has a manifest) loses that run's shots, so no
    stale picture is read as new; any other folder that holds files is refused."""
    out.mkdir(parents=True, exist_ok=True)
    m = out / "manifest.json"
    if m.exists():
        root = out.resolve()
        for s in json.loads(m.read_text()).get("shots", []):
            f = (out / str(s.get("file", ""))).resolve()
            if f.suffix == ".png" and f.is_relative_to(root) and f != root:  # never a file outside this folder
                f.unlink(missing_ok=True)
        m.unlink()
        for d in sorted((x for x in out.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)):
            if not any(d.iterdir()):
                d.rmdir()
    if any(out.iterdir()):
        raise SystemExit(f"{out} holds files that are not shots of an earlier run: use an empty folder")


def changed(a: bytes, b: bytes) -> int:
    ia, ib = np.asarray(Image.open(io.BytesIO(a)).convert("RGB")), np.asarray(Image.open(io.BytesIO(b)).convert("RGB"))
    if ia.shape != ib.shape:
        return max(ia.shape[0] * ia.shape[1], ib.shape[0] * ib.shape[1])
    return int(np.any(ia != ib, axis=2).sum())


def shoot(site: Site, out: Path, runs: int = 1, live: bool = False, pages=None, hosts=None, sizes=None, modes=None,
          server: str | None = None) -> dict:
    server = server or (site.get("serve") or {}).get("url")
    if not live and not server:
        raise SystemExit("site.json has no serve.url: start the local build and name its URL, or pass --live")
    if not live and not is_local(server):
        raise SystemExit(f"serve.url {server} is not on this machine: the local build must be served on 127.0.0.1")
    hosts = hosts or [h["name"] for h in site.hosts]
    sizes = sizes or site.sizes
    modes = modes or site.get("modes", ["light"])
    pages = pages or pages_of(site, server, live)
    if isinstance(pages, list):
        pages = {h: list(pages) for h in hosts}
    masks = DEFAULT_MASK + list(site.get("mask", []))
    dark = site.get("dark")
    router = Router({h["name"] for h in site.hosts}, server, live)
    shots = []
    clear(out)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, args=chrome_args(live, router.hosts))
        version = browser.version
        for host in hosts:
            for mode in modes:
                for w, h in sizes:
                    for p in pages.get(host, []):
                        url = f"https://{host}{p}"
                        caps = [capture(browser, router, url, w, h, mode, masks, dark) for _ in range(runs)]
                        png, facts = caps[0]
                        diffs = [changed(png, c[0]) for c in caps[1:]]
                        rel = Path(host) / mode / f"{w}x{h}" / f"{slug(p)}.png"
                        (out / rel).parent.mkdir(parents=True, exist_ok=True)
                        (out / rel).write_bytes(png)
                        img = Image.open(io.BytesIO(png))
                        shots.append({"file": rel.as_posix(), "host": host, "mode": mode, "size": f"{w}x{h}", "page": p,
                                      "sha256": hashlib.sha256(png).hexdigest(), "width": img.width,
                                      "height": img.height, "runs": runs, "stable": not any(diffs),
                                      "unstable_pixels": max(diffs, default=0), "status": facts["status"],
                                      "final_url": facts["final_url"], "title": facts["title"], "mode_ok": facts["mode_ok"],
                                      "overflow": facts["scrollWidth"] > facts["innerWidth"] + 1,
                                      "scroll_width": facts["scrollWidth"]})
        browser.close()
    manifest = {"live": live, "server": None if live else server, "browser": version, "fixed_time": FIXED_TIME, "masks": masks,
                "dark": dark, "pages": pages, "hosts": hosts, "modes": modes, "sizes": [f"{w}x{h}" for w, h in sizes],
                "shots": shots, "served": router.served, "blocked": sorted(router.blocked), "errors": router.errors}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default="tools/site.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--server")
    ap.add_argument("--pages", nargs="*")
    ap.add_argument("--hosts", nargs="*")
    ap.add_argument("--modes", nargs="*")
    ap.add_argument("--sizes", nargs="*")
    args = ap.parse_args()
    site = Site(args.site)
    sizes = [tuple(int(v) for v in s.split("x")) for s in args.sizes] if args.sizes else None
    m = shoot(site, Path(args.out), args.runs, args.live, args.pages, args.hosts, sizes, args.modes, args.server)
    unstable = [s for s in m["shots"] if not s["stable"]]
    bad = [s for s in m["shots"] if s["status"] is None or s["status"] >= 400]
    over = [s for s in m["shots"] if s["overflow"]]
    wrong_mode = [s for s in m["shots"] if not s["mode_ok"]]
    n_pages = len({p for ps in m["pages"].values() for p in ps})
    print(f"{len(m['shots'])} shots ({n_pages} pages x {len(m['hosts'])} hosts x {len(m['modes'])} modes x "
          f"{len(m['sizes'])} sizes), {args.runs} run(s) each: {len(unstable)} unstable, {len(bad)} with an error "
          f"status, {len(over)} with sideways overflow; {len(m['blocked'])} third-party URLs blocked; "
          f"{len(m['errors'])} fetch errors -> {args.out}/manifest.json")
    for s in unstable:
        print(f"  unstable: {s['file']} ({s['unstable_pixels']} px differ between runs)")
    for s in bad:
        print(f"  status {s['status']}: {s['file']}")
    for e in m["errors"][:10]:
        print(f"  fetch error: {e}")
    for s in wrong_mode:
        print(f"  not in {s['mode']} mode: {s['file']} (site.json \"dark\" says how the site switches)")
    return 1 if unstable or bad or m["errors"] or wrong_mode else 0


if __name__ == "__main__":
    sys.exit(main())
