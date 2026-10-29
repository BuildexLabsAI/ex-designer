"""The invented test site's server: one build that picks its brand by the Host header, like a Worker, on 127.0.0.1.

alpha.invalid and every unknown host get the Alpha brand (the default brand, as on a real two-brand Worker);
beta.invalid gets Beta. `/tokens.css` is the token file itself (a browser skips Tailwind's at-rules), every other
path comes from public/, a folder path without its slash answers 308, and /assets/away.png redirects to a public
IP address (a redirect a test must see blocked), as do /assets/hop.png in two hops and /assets/slash.png through a
backslash that Chrome reads as a slash. Pages, robots.txt and the sitemap carry the
brand, title and host. Every request is logged, so a test can prove which hosts and paths were asked for.

As a command it is the invented site's own server (the newcomer test copies it to tools/serve.py):
  python3 serve.py [--root <site>] [--port 8787]   serves until stopped, on 127.0.0.1 only
"""
import argparse
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

BRANDS = {"alpha.invalid": ("alpha", "Alpha Studio"), "beta.invalid": ("beta", "Beta Labs")}
DEFAULT = "alpha.invalid"
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
         ".xml": "application/xml", ".txt": "text/plain; charset=utf-8", ".js": "text/javascript"}


def make_handler(root: Path, log: list):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            known = host if host in BRANDS else DEFAULT
            brand, title = BRANDS[known]
            path = urlsplit(self.path).path
            log.append((host, path))
            hops = {"/assets/away.png": "https://1.1.1.1/away.png", "/assets/hop.png": "/assets/hop2.png",
                    "/assets/hop2.png": "https://1.1.1.1/hop.png", "/assets/slash.png": "/\\1.1.1.1/slash.png"}
            if path in hops:  # a local answer that redirects off the machine: must be blocked
                self.send_response(302)
                self.send_header("Location", hops[path])
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/tokens.css":
                file = root / "app" / "globals.css"
            else:
                file = root / "public" / path.lstrip("/")
                if path.endswith("/"):
                    file = file / "index.html"
                elif file.is_dir():
                    self.send_response(308)
                    self.send_header("Location", path + "/")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            status = 200
            if not file.is_file():
                status, file = 404, None
            body = file.read_bytes() if file else b"<!doctype html><title>Not found</title><h1>Not found</h1>"
            ctype = TYPES.get(file.suffix if file else ".html", "application/octet-stream")
            if file and file.suffix in (".html", ".xml", ".txt"):
                body = (body.decode().replace("{{brand}}", brand).replace("{{title}}", title)
                        .replace("{{host}}", known).encode())
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    return Handler


def start(root: Path):
    """Serve the site at root on a free port of 127.0.0.1. Returns (server, base URL, request log)."""
    log = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Path(root), log))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}", log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(Path(args.root), []))
    print(f"serving {args.root} on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
