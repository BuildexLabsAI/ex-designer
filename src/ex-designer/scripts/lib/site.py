"""The site file (site.json) every takeover script reads, and the one way they fetch a page over HTTP.

site.json lives in the project's tools/ folder. Paths in it are relative to `root`, which is relative to the file:
{
  "root": "..",
  "tokens": {"file": "app/globals.css", "sources": ["app/**/*.tsx", "components/**/*.tsx"],
             "exclude": ["app/report/**"], "docs": ["*.md", "docs/**/*.md"], "fonts": ["app/fonts/**"]},
  "oneoffs": {"#1b3559": "dark ::selection highlight"},
  "serve": {"url": "http://127.0.0.1:8787", "start": "npx wrangler dev --ip 127.0.0.1 --port 8787"},
  "hosts": [{"name": "example.com", "brand": "Example", "expect": ["<title>Example"], "absent": ["Other Brand"]}],
  "pages": ["/", "/about/"],
  "sitemap": "/sitemap.xml",
  "sizes": ["390x844", "1440x900"],
  "modes": ["light"],
  "mask": ["video", "canvas", "iframe"],
  "checks": ["npm run lint", "npm test"]
}
"""
import fnmatch
import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from html import unescape as html_unescape
from pathlib import Path
from urllib.parse import urlsplit

# Never read, whatever a glob says: secrets and sessions stay the owner's.
SECRET_GLOBS = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.session", ".dev.vars", ".dev.vars.*", "id_rsa*",
                "*.keystore", ".npmrc", ".netrc")
SKIP_DIRS = {"node_modules", ".git", ".next", "dist", "build", ".wrangler", ".claude", ".turbo", ".vercel",
             "coverage", "__pycache__", ".venv", "outputs", "baseline"}
UA = "ex-designer-livecheck/1"


class Site:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.data = json.loads(self.path.read_text())
        self.root = (self.path.parent / self.data.get("root", ".")).resolve()

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def hosts(self) -> list[dict]:
        return self.data.get("hosts", [])

    @property
    def sizes(self) -> list[tuple[int, int]]:
        return [tuple(int(v) for v in s.split("x")) for s in self.data.get("sizes", ["390x844", "1440x900"])]

    def readable(self, p: Path) -> bool:
        """A file a script may read: inside root once links are followed, and neither its own name nor its target's
        is a secret file's."""
        try:
            target = p.resolve(strict=True)
            target.relative_to(self.root)
        except (OSError, ValueError):
            return False
        names = {p.name, target.name}
        return target.is_file() and not any(fnmatch.fnmatchcase(n.casefold(), s.casefold())  # the Mac opens .ENV as .env
                                            for n in names for s in SECRET_GLOBS)

    def file(self, rel: str) -> Path:
        """One named file (the token file); refuses a secret file or a path outside root."""
        p = self.root / rel
        if not self.readable(p):
            raise SystemExit(f"{rel}: not a readable file inside {self.root} (secret files are never read)")
        return p

    def files(self, globs: list[str], exclude: list[str] = ()) -> list[Path]:
        """Files under root matching any glob, minus excluded globs, skipped folders and secret files."""
        out = []
        for g in globs:
            for p in sorted(self.root.glob(g)):
                rel = p.relative_to(self.root).as_posix()
                if any(part in SKIP_DIRS for part in p.relative_to(self.root).parts[:-1]) or not self.readable(p):
                    continue
                if any(fnmatch.fnmatch(rel, e) for e in exclude):
                    continue
                if p not in out:
                    out.append(p)
        return out

    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _tls() -> ssl.SSLContext:
    """The default TLS context, or, when this Python has no CA certificates (a python.org build on macOS before its
    certificate step), certifi's bundle or the system's /etc/ssl/cert.pem."""
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats()["x509_ca"]:
        return ctx
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    if Path("/etc/ssl/cert.pem").exists():
        return ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    return ctx


_OPENER = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=_tls()))
# Local requests never go through a proxy from the environment (HTTP_PROXY would carry them off the machine).
_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def fetch(base: str, path: str, host: str | None = None, timeout: float = 20, method: str = "GET") -> dict:
    """One request, redirects not followed. base is a URL ("http://127.0.0.1:8787" for a local build, or
    "https://example.com" live); host, when given, goes in the Host header (a local build that picks the brand by Host).
    Returns status, headers (lower-case keys), body bytes and the URL asked."""
    if not path.startswith("/") or path.startswith("//") or re.search(r"[\\\x00-\x20\x7f]", path):
        raise ValueError(f"not a plain path: {path[:80]!r}")
    url = base.rstrip("/") + path
    b, u = urlsplit(base), urlsplit(url)
    if (u.scheme, u.hostname, u.port) != (b.scheme, b.hostname, b.port):  # a path never moves the request elsewhere
        raise ValueError(f"{path[:80]!r} leaves {base}")
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    if host:
        req.add_header("Host", host)
    try:
        with (_LOCAL if is_local(url) else _OPENER).open(req, timeout=timeout) as r:
            return {"status": r.status, "headers": {k.lower(): v for k, v in r.headers.items()}, "body": r.read(),
                    "url": url}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "headers": {k.lower(): v for k, v in (e.headers or {}).items()},
                "body": e.read() if e.fp else b"", "url": url}


def is_local(url: str) -> bool:
    return bool(re.match(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(/|$)", url))


def sitemap_paths(get, path: str, limit: int = 2000, files: dict | None = None) -> list[str]:
    """Page paths from a sitemap, following a sitemap index into its child sitemaps (same host, no loops).
    get(path) returns a fetch() result. `files`, when given, collects {sitemap path: [status, sha256]}."""
    out, seen, queue = [], set(), [path]
    while queue and len(out) < limit:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        r = get(sm)
        if files is not None:
            files[sm] = [r["status"], hashlib.sha256(r["body"]).hexdigest()]
        if r["status"] != 200:
            continue
        body = r["body"].decode("utf-8", "replace")
        # A sitemap may name another host (one host's sitemap listing the other brand's URLs): its path is taken and
        # asked of this host. Only plain paths are kept; fetch() refuses anything that would leave the host anyway.
        locs = [urlsplit(html_unescape(x)).path or "/" for x in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)]
        locs = [x for x in locs if x.startswith("/") and not x.startswith("//") and not re.search(r"[@\\\x00-\x20\x7f]", x)]
        if re.search(r"<sitemapindex\b", body):
            queue += locs
            continue
        for p in locs:
            if p not in out:
                out.append(p)
    return out
