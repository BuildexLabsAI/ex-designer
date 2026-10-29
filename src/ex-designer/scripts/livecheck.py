"""SEO facts, brand markers and static assets of a site, from its local build or live, and the comparison of the two.

  python3 livecheck.py seo --site tools/site.json --out seo.json [--live]
      per host and page: status, redirect, the other trailing-slash form, title, description, canonical, robots
      (meta and X-Robots-Tag), hreflang, lang, h1 count; per host: robots.txt, every sitemap file (an index and its
      children) and the pages they list
  python3 livecheck.py compare --site tools/site.json [--seo seo.json] [--out report.json]
      the local build (serve.url, each host in the Host header) against the live site: every static asset the pages
      of either side load (scripts and the modules and chunks they name, stylesheets and what they import, fonts
      and images they name, icons, preloads, img and srcset candidates, og:image), byte for byte; the SEO facts; each host's brand markers (site.json expect
      / absent). With --seo, the live facts are also compared with that saved baseline. Exit 0 only when all are equal.

Pages: site.json "pages" for every host, or each host's own sitemap (sitemap indexes followed). Plain HTTP, one
request at a time, redirects never followed (a redirect is a fact to record). Local requests go only to serve.url,
which must be on this machine, and never through a proxy.
"""
import argparse
import hashlib
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.site import Site, fetch, is_local, sitemap_paths  # noqa: E402

SKIP_RELS = {"canonical", "alternate", "dns-prefetch", "preconnect", "prefetch", "prerender", "next", "prev", "me",
             "author", "license", "search"}
MAX_ASSETS = 400


class Doc(HTMLParser):
    """The tags an SEO and asset check needs, with their attributes (names lower-case, values unescaped)."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.tags, self.title, self._in_title = [], None, False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k.lower(): (v or "") for k, v in attrs}))
        if tag == "title" and self.title is None:
            self._in_title, self.title = True, ""

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data

    def all(self, name: str) -> list[dict]:
        return [a for t, a in self.tags if t == name]


def page_facts(r: dict) -> dict:
    f = {"status": r["status"], "location": r["headers"].get("location"),
         "x_robots_tag": r["headers"].get("x-robots-tag")}
    if r["status"] != 200 or "html" not in r["headers"].get("content-type", "html"):
        return f
    d = Doc(r["body"].decode("utf-8", "replace"))

    def meta(key):
        return next((m.get("content") for m in d.all("meta") if (m.get("name") or m.get("property") or "").lower() == key), None)
    links = d.all("link")
    f["title"] = " ".join(d.title.split()) if d.title is not None else None
    f["description"] = meta("description")
    f["robots"] = meta("robots")
    f["og_url"] = meta("og:url")
    f["canonical"] = next((a.get("href") for a in links if "canonical" in a.get("rel", "").lower().split()), None)
    f["hreflang"] = sorted([a["hreflang"], a.get("href")] for a in links
                           if "alternate" in a.get("rel", "").lower().split() and a.get("hreflang"))
    f["lang"] = next((a.get("lang") for a in d.all("html")), None)
    f["h1"] = len(d.all("h1"))
    return f


def other_slash(p: str) -> str | None:
    if p == "/" or "?" in p or re.search(r"\.[a-z0-9]{2,5}$", p):
        return None
    return p.rstrip("/") if p.endswith("/") else p + "/"


def same_origin(base: str, refs, host: str) -> list[str]:
    out = []
    for u in refs:
        if not u or u.startswith(("data:", "blob:", "#", "mailto:", "javascript:")):
            continue
        s = urlsplit(urljoin(base, u.strip()))
        if s.hostname == host:
            path = s.path + (f"?{s.query}" if s.query else "")
            if path not in out:
                out.append(path)
    return out


def asset_urls(text: str, host: str, page: str) -> list[str]:
    """Same-origin static files a page loads: scripts, stylesheets, icons, preloads, images and srcset candidates,
    sources of picture, video and audio, the og:image."""
    d = Doc(text)
    refs = [a.get("src") for a in d.all("script")]
    refs += [a.get("href") for a in d.all("link") if a.get("rel") and not set(a["rel"].lower().split()) & SKIP_RELS]
    for tag in ("img", "source", "video", "audio", "track"):
        for a in d.all(tag):
            refs += [a.get("src"), a.get("poster")]
            refs += [c.strip().split()[0] for c in (a.get("srcset") or "").split(",") if c.strip()]
    refs += [m.get("content") for m in d.all("meta") if (m.get("property") or "").lower() == "og:image"]
    return same_origin(f"https://{host}{page}", refs, host)


def js_urls(text: str, host: str, path: str) -> list[str]:
    """Same-origin files a script loads: static and dynamic imports, and chunk paths a bundle names in strings."""
    refs = [m.group(2) for m in re.finditer(r"(?:import|from|import\()\s*([\"'`])([^\"'`\s]+\.(?:m?js|css))\1", text)]
    refs += [m.group(1) for m in re.finditer(r"[\"'`]((?:\.{1,2})?/[^\"'`\s]+\.(?:m?js|css))[\"'`]", text)]
    return same_origin(f"https://{host}{path}", refs, host)


def css_urls(text: str, host: str, path: str) -> list[str]:
    """Same-origin files a stylesheet loads: url(...) and @import."""
    refs = [m.group(2) for m in re.finditer(r"url\(\s*([\"']?)([^\"')]+)\1\s*\)", text)]
    refs += [m.group(1) for m in re.finditer(r"@import\s+[\"']([^\"']+)[\"']", text)]
    return same_origin(f"https://{host}{path}", refs, host)


class Source:
    """The site from one side: the local build (Host header) or live (https://host). `stand_in` replaces live with
    another local server (the tests' stand-in for the internet)."""

    def __init__(self, site: Site, live: bool, stand_in: str | None = None):
        self.live = live and not stand_in
        self.server = stand_in or (None if live else (site.get("serve") or {}).get("url"))
        if not self.live and (not self.server or not is_local(self.server)):
            raise SystemExit("site.json serve.url must be the local build on 127.0.0.1 (start it first)")

    def get(self, host: str, path: str) -> dict:
        if self.live:
            return fetch(f"https://{host}", path)
        return fetch(self.server, path, host)


def pages_of(site: Site, src: Source) -> dict[str, list[str]]:
    hosts = [h["name"] for h in site.hosts]
    if site.get("pages"):
        return {h: list(site.get("pages")) for h in hosts}
    return {h: sitemap_paths(lambda path, h=h: src.get(h, path), site.get("sitemap", "/sitemap.xml")) or ["/"]
            for h in hosts}


def per_host(site: Site, pages) -> dict[str, list[str]]:
    return pages if isinstance(pages, dict) else {h["name"]: list(pages) for h in site.hosts}


def seo(site: Site, src: Source, pages) -> dict:
    pages = per_host(site, pages)
    out = {"source": "live" if src.live else src.server, "hosts": {}}
    for h in site.hosts:
        host = h["name"]
        entry = {"pages": {}, "brand": {}}
        for p in pages.get(host, []):
            r = src.get(host, p)
            facts = page_facts(r)
            alt = other_slash(p)
            if alt:
                ra = src.get(host, alt)
                facts["other_slash"] = {"path": alt, "status": ra["status"], "location": ra["headers"].get("location")}
            entry["pages"][p] = facts
            if r["status"] == 200:
                body = r["body"].decode("utf-8", "replace")
                missing = [s for s in h.get("expect", []) if s not in body]
                present = [s for s in h.get("absent", []) if s in body]
                if missing or present:
                    entry["brand"][p] = {"expect_missing": missing, "absent_present": present}
        rb = src.get(host, "/robots.txt")
        entry["robots_txt"] = {"status": rb["status"], "sha256": hashlib.sha256(rb["body"]).hexdigest(),
                               "sitemaps": re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rb["body"].decode("utf-8", "replace"))}
        sm, files = site.get("sitemap", "/sitemap.xml"), {}
        paths = sitemap_paths(lambda path, h=host: src.get(h, path), sm, files=files)
        entry["sitemap"] = {"path": sm, "status": files.get(sm, [None])[0], "files": files, "paths": sorted(paths)}
        out["hosts"][host] = entry
    return out


def diff_facts(a: dict, b: dict, label_a: str, label_b: str) -> list[str]:
    """Differences between two seo() results, as readable lines."""
    lines = []
    for host in sorted(set(a["hosts"]) | set(b["hosts"])):
        ha, hb = a["hosts"].get(host), b["hosts"].get(host)
        if not ha or not hb:
            lines.append(f"{host}: only in {label_a if ha else label_b}")
            continue
        for p in sorted(set(ha["pages"]) | set(hb["pages"])):
            if p not in ha["pages"] or p not in hb["pages"]:
                lines.append(f"{host}{p}: only in {label_a if p in ha['pages'] else label_b}")
                continue
            fa, fb = ha["pages"][p], hb["pages"][p]
            for k in sorted(set(fa) | set(fb)):
                if fa.get(k) != fb.get(k):
                    lines.append(f"{host}{p} {k}: {label_a} {fa.get(k)!r} / {label_b} {fb.get(k)!r}")
        for k in ("robots_txt", "sitemap"):
            if ha.get(k) != hb.get(k):
                lines.append(f"{host} {k}: differs ({label_a} {ha.get(k, {}).get('status')} / {label_b} {hb.get(k, {}).get('status')})")
    return lines


def assets_of(src: Source, host: str, pages: list[str]) -> list[str]:
    """Every same-origin asset the pages load on one side, with what their stylesheets load."""
    paths = []
    for p in pages:
        r = src.get(host, p)
        if r["status"] == 200:
            paths += [a for a in asset_urls(r["body"].decode("utf-8", "replace"), host, p) if a not in paths]
    i = 0
    while i < len(paths) and len(paths) < MAX_ASSETS:
        a, kind = paths[i], paths[i].split("?")[0].rsplit(".", 1)[-1]
        if kind in ("css", "js", "mjs"):
            r = src.get(host, a)
            if r["status"] == 200:
                body = r["body"].decode("utf-8", "replace")
                found = css_urls(body, host, a) if kind == "css" else js_urls(body, host, a)
                paths += [u for u in found if u not in paths]
        i += 1
    return paths


def compare(site: Site, pages=None, baseline: dict | None = None, stand_in: str | None = None) -> dict:
    local, live = Source(site, False), Source(site, True, stand_in)
    pages = per_host(site, pages) if pages else pages_of(site, local)
    facts_local, facts_live = seo(site, local, pages), seo(site, live, pages)
    problems = diff_facts(facts_local, facts_live, "local", "live")
    assets = {}
    for h in site.hosts:
        host = h["name"]
        for side, name in ((facts_local, "local"), (facts_live, "live")):
            for p, br in side["hosts"][host]["brand"].items():
                problems += [f"{host}{p} ({name}): brand marker missing: {s!r}" for s in br["expect_missing"]]
                problems += [f"{host}{p} ({name}): another brand's marker present: {s!r}" for s in br["absent_present"]]
        seen_local, seen_live = assets_of(local, host, pages.get(host, [])), assets_of(live, host, pages.get(host, []))
        for a in sorted(set(seen_local) ^ set(seen_live)):
            problems.append(f"{host}{a}: loaded only by the {'local build' if a in seen_local else 'live site'}")
        rows = []
        for a in seen_local + [x for x in seen_live if x not in seen_local]:
            rl, rv = local.get(host, a), live.get(host, a)
            hl, hv = hashlib.sha256(rl["body"]).hexdigest(), hashlib.sha256(rv["body"]).hexdigest()
            same = rl["status"] == rv["status"] and hl == hv  # a file missing on both sides alike is no difference
            rows.append({"path": a, "local": rl["status"], "live": rv["status"], "bytes": len(rl["body"]),
                         "sha256_local": hl, "sha256_live": hv, "identical": same})
            if not same:
                problems.append(f"{host}{a}: local {rl['status']} {hl[:12]} / live {rv['status']} {hv[:12]}")
        assets[host] = rows
    if baseline:
        problems += [f"baseline: {x}" for x in diff_facts(baseline, facts_live, "baseline", "live")]
    return {"pages": pages, "local": facts_local, "live": facts_live, "assets": assets, "problems": problems,
            "identical": not problems}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["seo", "compare"])
    ap.add_argument("--site", default="tools/site.json")
    ap.add_argument("--out")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--seo", help="a saved seo.json to compare the live facts with")
    ap.add_argument("--pages", nargs="*")
    args = ap.parse_args()
    site = Site(args.site)
    if args.command == "seo":
        src = Source(site, args.live)
        data = seo(site, src, args.pages or pages_of(site, src))
        Path(args.out or "seo.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        n = sum(len(h["pages"]) for h in data["hosts"].values())
        bad = [f"{host}{p} {f['status']}" for host, h in data["hosts"].items() for p, f in h["pages"].items()
               if f["status"] != 200]
        brand = [f"{host}{p}: {b}" for host, h in data["hosts"].items() for p, b in h["brand"].items()]
        print(f"{n} pages on {len(data['hosts'])} hosts from {data['source']} -> {args.out or 'seo.json'}"
              + (f"; not 200: {', '.join(bad)}" if bad else "") + (f"; brand problems: {'; '.join(brand)}" if brand else ""))
        return 1 if brand else 0
    baseline = json.loads(Path(args.seo).read_text()) if args.seo else None
    report = compare(site, args.pages, baseline)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    n_assets = sum(len(v) for v in report["assets"].values())
    same = sum(1 for v in report["assets"].values() for a in v if a["identical"])
    n_pages = len({p for ps in report["pages"].values() for p in ps})
    print(f"{n_pages} pages x {len(site.hosts)} hosts; {same}/{n_assets} static assets byte-identical; "
          f"{len(report['problems'])} differences")
    for p in report["problems"][:40]:
        print(f"  {p}")
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
