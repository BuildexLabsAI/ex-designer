"""The brand book (step 6b): read the brand's copy and files, check the book against its sources, build the kit.

  python3 brandbook.py read --work brand-work/ [--live]
      capture.json  every page of the brand's hosts as read: title, meta, headings, text, links and buttons, image
                    text, form labels; and the brand files in the site's code (logos, icons, share images,
                    manifests). The ledger's page quotes are checked against it.
      capture.md    the same, short: what to read for the voice samples
  python3 brandbook.py check --work brand-work/
      the ledger (every fact has a source, and every source resolves), the book's chapters and marks, its colours and
      fonts against the token file, the gate (em dashes, banned words) and the furniture check (no internal notes);
      exit 1 on any problem. Without book.md only the ledger is checked.
  python3 brandbook.py build --work brand-work/
      check, then the kit for makers: brand-book.md (for AI tools), brand-book.html (the book, with colour, type and
      logo specimens made from design/usage.json), brand-book.pdf, README.md and files/, made in a folder of its own
      and put in the kit's place only after the furniture check and the gate pass on every file of it. Exit 1 on a
      problem, 2 when a file of the kit cannot be checked; the kit stays as it was.

The work folder (brand.json, ledger.json, book.md, readme.md, capture.*) is internal and never handed to makers; the
kit folder is what they get. Formats and rules: references/brand-book.md.
"""
import argparse
import base64
import fnmatch
import hashlib
import html
import io
import json
import os
import posixpath
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tokens as T  # noqa: E402
from lib import color as C  # noqa: E402
from lib.site import SECRET_GLOBS, SKIP_DIRS, Site, fetch, sitemap_paths  # noqa: E402

SKILL = HERE.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CORE = ("on-a-page", "who", "voice", "logo", "colour", "type", "imagery", "in-use", "care")
OPTIONAL = ("story", "signature", "motion", "interface", "family")
OWNER_ONLY = {"who", "story"}  # the owner's own words: never inferred from the site
SPECIMENS = {"colour": "colour", "type": "type", "logo": "logo"}  # a specimen and the chapter it belongs in
KINDS = ("page", "file", "token", "finding", "answer", "shot")
STATUSES = ("confirmed", "observed")
FACT_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
GAP_ID = re.compile(r"G\d{1,3}")
ANSWER_ID = re.compile(r"A\d{1,3}")
KIT_NAME = re.compile(r"[A-Za-z0-9][\w.-]{0,80}")
MARK = re.compile(r"[ \t]*\[\[([^\[\]\n]*)\]\]")
CHAPTER_ID = re.compile(r"\s*\{#([^}\s]*)\}\s*$")
ALLOW_RE = re.compile(r"[ \t]*<!--\s*(?:gate|furniture|value)-allow\s*-->")
LINK_RE = re.compile(r"!?\[(?:[^\[\]\n]|\[[^\]\n]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
KIT_BOOK = ("README.md", "brand-book.md", "brand-book.html", "brand-book.pdf")
FENCE = re.compile(r"^\s*(?:```|~~~)")
SPECIMEN_LINE = re.compile(r"^\s*\[\[\s*specimen:\s*[\w-]+\s*\]\]\s*$")
IMAGE_LINE = re.compile(r"!\[(?:[^\[\]]|\[[^\]]*\])*\]\([^)]*\)\s*$")  # one level of [nested] text
TABLE_SEP = re.compile(r"\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
QUOTE_RE = re.compile(r'"([^"]+)"|“([^”]+)”|‘(.+?)’(?!\w)|(?<!\w)\'([^\'\n]+?)\'(?!\w)')
GATE_ALLOW = re.compile(r"<!--\s*gate-allow\s*-->")
FURNITURE_ALLOW = re.compile(r"<!--\s*furniture-allow\s*-->")
VALUE_ALLOW = re.compile(r"<!--\s*value-allow\s*-->")
CSS_COLOUR = re.compile(r"\b(?:color|background(?:-color)?|border(?:-(?:top|right|bottom|left))?(?:-color)?|fill|stroke|"
                        r"outline(?:-color)?|accent-color|caret-color|text-decoration-color)\s*:\s*([^;`'\"}\n]+)", re.I)
NOT_COLOURS = {"transparent", "currentcolor", "inherit", "initial", "unset", "revert", "none", "auto"}
REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*\S")
AUTOLINK = re.compile(r"<([A-Za-z][\w+.-]*:[^>\s]+)>")
LOGO_NAME = re.compile(r"logo|mark|lockup|symbol|monogram", re.I)
IMAGES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}

# The gate's default words: common filler of machine-written prose and empty marketing words. brand.json adds the
# brand's own never-words (`banned`).
DEFAULT_BANNED = ["delve", "tapestry", "navigate", "leverage", "landscape", "ecosystem", "realm", "multifaceted",
                  "foster", "underscore", "robust", "comprehensive", "nuanced", "paramount", "crucial", "holistic",
                  "pivotal", "streamline", "optimize", "optimise", "innovative"]

# Families a writer may name by mistake. With the families in the site's design data they make the set of names the
# check looks for, in any letter case; a name in it that is not the brand's own fails. Names that are everyday words
# (Impact, Circular, Prompt, Georgia the place) are left out: the check would stop on prose. A family outside the set
# passes this check; the writer's brief and the fact check against the ledger are what stop it.
COMMON_FONTS = [
    "Avenir", "Avenir Next", "Myriad Pro", "Minion Pro", "Papyrus", "Comic Sans", "Brush Script MT", "Franklin Gothic",
    "Libre Franklin", "Century Gothic", "Gill Sans MT", "Palatino", "Book Antiqua", "Lucida Sans", "Arial Black",
    "Aktiv Grotesk", "Neue Montreal", "Apercu", "Basier", "GT Walsheim", "GT Sectra", "Tiempos Text", "Tiempos Headline",
    "Canela", "Recoleta", "Fraunces", "Literata", "Heebo", "Chivo", "Kanit", "Inconsolata", "Red Hat Display",
    "Red Hat Text", "Atkinson Hyperlegible", "Public Sans", "Be Vietnam Pro", "Josefin Sans", "Titillium Web", "Exo 2",
    "Sohne", "Circular Std", "Suisse Int'l",
    "Arial", "Helvetica", "Helvetica Neue", "Verdana", "Tahoma", "Trebuchet MS", "Times New Roman", "Courier New",
    "Segoe UI", "Calibri", "Cambria", "Garamond", "EB Garamond", "Baskerville", "Libre Baskerville", "Didot", "Bodoni",
    "Futura", "Optima", "Gill Sans", "Frutiger", "Univers", "Akzidenz-Grotesk", "Neue Haas Grotesk", "Proxima Nova",
    "Gotham", "Graphik", "Brandon Grotesque", "Sofia Pro", "GT America", "Söhne", "Tiempos", "Styrene", "SF Pro",
    "SF Pro Display", "SF Pro Text", "SF Mono", "Menlo", "Consolas", "Lucida Grande", "Comic Sans MS", "Inter", "Roboto",
    "Roboto Mono", "Open Sans", "Lato", "Poppins", "Raleway", "Nunito", "Rubik", "Mulish", "Manrope", "DM Sans",
    "Work Sans", "Space Grotesk", "Space Mono", "IBM Plex Sans", "IBM Plex Serif", "IBM Plex Mono", "JetBrains Mono",
    "Fira Sans", "Fira Code", "Source Sans Pro", "Source Sans 3", "Source Serif Pro", "Source Code Pro", "Noto Sans",
    "Noto Serif", "PT Sans", "PT Serif", "Playfair Display", "Merriweather", "Archivo", "Instrument Sans",
    "Instrument Serif", "General Sans", "Plus Jakarta Sans", "Lexend", "Figtree", "Geist", "Geist Mono",
    "Bricolage Grotesque", "Hanken Grotesk", "Schibsted Grotesk", "Cormorant", "Crimson Pro", "Crimson Text",
]

DEFAULT_LABELS = {k: k for k in (
    "nav", "role", "contrast", "contrast_intro", "passes", "fails", "font_file", "font_stack", "defined_at", "scale",
    "specimen", "generated_from", "context_base", "context_dark", "band_background", "band_text", "band_muted",
    "band_accent", "g_surfaces", "g_text", "g_brand", "g_status", "g_lines", "g_charts", "g_other", "version", "open")}


def norm(s) -> str:
    return " ".join(str(s or "").split())


def match_form(s: str) -> str:
    """A text as a quote is compared: spaces collapsed, curly quotes and apostrophes straight."""
    return norm(s).translate(str.maketrans("‘’“”", "''\"\""))


def squash(s: str) -> str:
    """A page quote as it is compared with one block of the page: without spaces, because where a line breaks on a
    page (an element the stylesheet stacks) is not part of the words."""
    return re.sub(r"\s+", "", match_form(s))


def problem(rule: str, where: str, text: str) -> dict:
    return {"rule": rule, "where": where, "text": text}


def secret_name(p: Path) -> bool:
    """A secret file's name, asked for or reached through a link: such a file is never read (.env, keys, sessions)."""
    names = {p.name}
    try:
        names.add(p.resolve().name)
    except OSError:
        pass
    # In any letter case: the Mac's disk opens ".ENV" as ".env".
    return any(fnmatch.fnmatchcase(n.casefold(), s.casefold()) for n in names for s in SECRET_GLOBS)


def read_input(p: Path, what: str) -> str:
    """Every file the step reads besides the site's code (Site guards that one), never a secret file."""
    if secret_name(p):
        raise SystemExit(f"{what}: {p.name} has a secret file's name; secret files are never read")
    return p.read_text()


# ---------- the work folder ------------------------------------------------------------------------------------

class Work:
    """One brand's work folder and what its brand.json points at. Paths in brand.json are relative to the folder."""

    def __init__(self, folder):
        self.dir = Path(folder).resolve()
        cfg_file = self.dir / "brand.json"
        if not cfg_file.is_file():
            raise SystemExit(f"{cfg_file}: missing; start from <skill>/templates/brand.json")
        self.cfg = json.loads(read_input(cfg_file, "brand.json"))
        missing = [k for k in ("brand", "site", "design", "contexts", "kit") if not self.cfg.get(k)]
        if missing:
            raise SystemExit(f"brand.json: {', '.join(missing)} missing")
        self.brand = str(self.cfg["brand"])
        site_file = self.path(self.cfg["site"])
        if secret_name(site_file):
            raise SystemExit(f"brand.json site: {site_file.name} has a secret file's name")
        self.site = Site(site_file)
        self.design = self.path(self.cfg["design"])
        self.kit = self.path(self.cfg["kit"])
        if self.kit == self.dir or self.kit.is_relative_to(self.dir) or self.dir.is_relative_to(self.kit):
            raise SystemExit("brand.json: the kit and the work folder must not hold each other, because the work "
                             "folder (ledger, answers, capture) is never handed to makers")
        usage = self.design / "usage.json"
        if not usage.is_file():
            raise SystemExit(f"{usage}: missing; run tokens.py extract first")
        self.data = json.loads(read_input(usage, "brand.json design"))
        self.contexts = [str(c) for c in self.cfg["contexts"]]
        unknown = [c for c in self.contexts if c not in self.data["contexts"]]
        if unknown:
            raise SystemExit(f"brand.json contexts: {', '.join(unknown)} not in usage.json "
                             f"({', '.join(self.data['contexts'])})")
        self.hosts = self.cfg.get("hosts") or [h["name"] for h in self.site.hosts if h.get("brand") == self.brand]
        if not self.hosts:
            raise SystemExit(f"no host in site.json carries the brand {self.brand!r}: name them in brand.json hosts")
        self.lang = self.cfg.get("lang", "en")
        self.files = dict(self.cfg.get("files") or {})
        self.examples = dict(self.cfg.get("examples") or {})
        self.people = [norm(p) for p in self.cfg.get("people", []) if norm(p)]
        self.banned = DEFAULT_BANNED + [norm(b) for b in self.cfg.get("banned", []) if norm(b)]
        self.shots = self.path(self.cfg["shots"]) if self.cfg.get("shots") else None
        self.findings = None
        if self.cfg.get("audit"):
            audit_file = self.path(self.cfg["audit"])
            if not audit_file.is_file():
                raise SystemExit(f"brand.json audit: {audit_file} is not a file (the audit's findings.json)")
            audit = json.loads(read_input(audit_file, "brand.json audit"))
            self.findings = {str(f.get("id")) for f in audit.get("findings", []) + audit.get("dropped", [])}
        self.ledger = self.json_file("ledger.json")
        self.capture = self.json_file("capture.json")
        self.book = self.text_file("book.md")
        self.readme = self.text_file("readme.md")
        self.facts, self.gaps, self.answers = {}, {}, {}
        names = self.cfg.get("context_names") or self.site.get("context_names") or {}
        self.labels = dict(DEFAULT_LABELS)
        for f in (SKILL / "templates" / "ui-labels.json",
                  self.path(self.cfg["labels"]) if self.cfg.get("labels") else SKILL / "templates" / "brand-book-labels.json"):
            if f.is_file():
                d = json.loads(read_input(f, "brand.json labels"))
                self.labels.update(d.get(self.lang) or d.get("en") or {})
        self.names = {c: names.get(c) or (self.labels["context_base"] if c == "base" else self.labels["context_dark"]
                                          if c == "dark" else c) for c in self.data["contexts"]}
        roles = self.path(self.cfg["roles"]) if self.cfg.get("roles") else self.design / "roles.json"
        self.roles = json.loads(read_input(roles, "brand.json roles")) if roles.is_file() else {}

    def path(self, rel) -> Path:
        raw = self.dir / str(rel)
        if secret_name(raw):  # the name as written too, not only the file a link leads to
            raise SystemExit(f"brand.json: {raw.name} has a secret file's name; secret files are never read")
        return raw.resolve()

    def json_file(self, name):
        p = self.dir / name
        return json.loads(read_input(p, name)) if p.is_file() else None

    def text_file(self, name):
        p = self.dir / name
        return read_input(p, name) if p.is_file() else None

    def role(self, token: str):
        r = self.roles.get(token)
        return (r.get(self.lang) or r.get("en")) if isinstance(r, dict) else r

    def hex_in(self, token: str, ctx: str):
        i = self.data["tokens"].get(token, {}).get("contexts", {}).get(ctx)
        return i["hex"] if i and i.get("type") == "color" and i.get("hex") else None

    def stack(self, ctx: str) -> list:
        return (self.data["fonts"].get("page", {}).get(ctx) or {}).get("families") or []

    def kit_files(self) -> set:
        """The files the build puts into the kit, relative to it."""
        return set(KIT_BOOK) | {f"files/{n}" for n in list(self.files) + list(self.examples)}


# ---------- read: the brand's copy and files as they are -------------------------------------------------------

class Copy(HTMLParser):
    """The words of one page as a visitor reads them: each block of text once, in page order, plus the head's title and
    meta, every link and button, image text and form labels. Scripts, styles, SVG and media hold no copy."""
    BLOCK = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "figcaption", "label", "td", "th", "dt", "dd",
             "summary", "legend", "caption", "button", "a", "option"}
    SKIP = {"script", "style", "noscript", "template", "svg", "iframe", "canvas", "video", "audio", "object", "math"}
    BREAK = {"div", "section", "article", "main", "header", "footer", "nav", "aside", "form", "ul", "ol", "table", "tr",
             "tbody", "thead", "figure", "details", "dl", "body", "br", "hr", "picture", "fieldset", "select"}
    CLOSES_P = BLOCK - {"a", "button", "label", "option"}
    META = {"description", "og:title", "og:description", "og:site_name", "og:image", "og:image:alt", "twitter:title",
            "twitter:description", "twitter:image", "application-name", "apple-mobile-web-app-title", "theme-color"}
    ICONS = {"icon", "shortcut icon", "apple-touch-icon", "apple-touch-icon-precomposed", "mask-icon", "manifest"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.lang, self.meta, self.links = "", "", {}, []
        self.blocks, self.actions, self.images, self.fields = [], [], [], []
        self.stack, self.loose, self.open_actions = [], [], []
        self.skip, self.in_title, self.edge, self.hide = 0, False, False, None

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
    IMPLIED = {"p", "li", "dt", "dd", "option", "td", "th", "tr"}  # closed by the next one of their kind
    P_ENDS = {"div", "section", "article", "main", "header", "footer", "nav", "aside", "form", "ul", "ol", "dl",
              "table", "figure", "details", "fieldset", "address", "pre", "hr", "blockquote", "h1", "h2", "h3", "h4",
              "h5", "h6", "p"}  # a block that starts closes an open <p>
    PARENT_ENDS = {"li": {"ul", "ol", "menu"}, "dt": {"dl"}, "dd": {"dl"}, "option": {"select", "datalist", "optgroup"},
                   "td": {"tr", "tbody", "thead", "tfoot", "table"}, "th": {"tr", "tbody", "thead", "tfoot", "table"},
                   "tr": {"tbody", "thead", "tfoot", "table"}, "p": {"div", "section", "article", "main", "header",
                                                                     "footer", "aside", "nav", "li", "td", "th",
                                                                     "blockquote", "form", "body", "figure", "details"}}

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def emit(self, tag: str, words: list):
        text = norm("".join(words))
        if text:
            self.blocks.append({"tag": tag, "text": text})

    def flush(self):
        if self.loose:
            self.emit("text", self.loose)
            self.loose = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self.edge = True
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag in ("title", "meta", "link") and not self.skip:
            # The head's data, also where a framework streams it inside a hidden element before moving it to <head>
            if tag == "title":
                self.in_title = not self.title  # the first title is the page's
            elif tag == "meta":
                key = (a.get("name") or a.get("property") or "").lower()
                if key in self.META and norm(a.get("content")):
                    self.meta.setdefault(key, norm(a["content"]))
            else:
                rel = " ".join(a.get("rel", "").lower().split())
                if rel in self.ICONS and a.get("href"):
                    self.links.append({"rel": rel, "href": a["href"],
                                       **({"sizes": a["sizes"]} if a.get("sizes") else {})})
            return
        if self.hide:  # inside an element with the hidden attribute: count its own tag to find its end
            if not (self.hide[1] == 1 and (tag == self.hide[0] in self.IMPLIED
                                           or self.hide[0] == "p" and tag in self.CLOSES_P | self.P_ENDS)):
                self.hide[1] += tag == self.hide[0]
                return
            self.hide = None  # HTML closed the hidden <p> or <li> when this element began
        if "hidden" in a and tag != "html":
            if tag not in self.VOID:
                self.hide = [tag, 1]
            return  # never shown to a visitor, a hidden image's text included
        if self.skip or tag in self.SKIP:
            self.skip += tag in self.SKIP
            return
        if tag == "img":
            if norm(a.get("alt")):
                self.images.append({"alt": norm(a["alt"]), "src": a.get("src", "")})
        elif tag in ("input", "textarea"):
            f = {k: norm(a[k]) for k in ("placeholder", "aria-label") if norm(a.get(k))}
            if a.get("type") in ("submit", "button") and norm(a.get("value")):
                f["value"] = norm(a["value"])
            if f:
                self.fields.append(f)
        else:
            if tag in ("a", "button"):
                self.open_actions.append([tag, [], a.get("href", ""), norm(a.get("aria-label"))])
            if tag in self.BLOCK:
                if tag in ("a", "button") and self.stack:
                    return  # a link inside a block is part of the block's text
                if self.stack and (self.stack[-1][0] == tag in ("p", "li", "dt", "dd", "td", "th", "option")
                                   or self.stack[-1][0] == "p" and tag in self.CLOSES_P):
                    self.emit(*self.stack.pop())  # HTML closes these on their own
                self.flush()
                self.stack.append([tag, []])
            elif tag in self.BREAK:
                if tag == "br" and self.stack:
                    self.stack[-1][1].append(" ")
                else:
                    self.flush()

    def handle_endtag(self, tag):
        self.edge = True
        if tag == "title":
            self.in_title = False
        if self.hide:
            if self.hide[1] == 1 and tag in self.PARENT_ENDS.get(self.hide[0], ()):
                self.hide = None  # the parent's end closed the hidden <li> or <p>: read this end tag as usual
            else:
                self.hide[1] -= tag == self.hide[0]
                if not self.hide[1]:
                    self.hide = None
                return
        if self.skip:
            self.skip -= tag in self.SKIP
            return
        if tag in ("a", "button"):
            for i in range(len(self.open_actions) - 1, -1, -1):
                if self.open_actions[i][0] == tag:
                    _, words, href, label = self.open_actions.pop(i)
                    if norm("".join(words)) or label:
                        self.actions.append({"tag": tag, "text": norm("".join(words)), "href": href,
                                             **({"label": label} if label else {})})
                    break
        if tag in self.BLOCK and any(t == tag for t, _ in self.stack):
            while self.stack:
                t, words = self.stack.pop()
                self.emit(t, words)
                if t == tag:
                    break
        elif tag in self.BREAK:
            self.flush()

    def handle_data(self, data):
        if self.in_title:
            self.title += data
            return
        if self.skip or self.hide:
            return
        buf = self.stack[-1][1] if self.stack else self.loose
        # Sites break a heading into lines with elements the stylesheet stacks ("deals<span>deserve"): a visitor
        # reads a space there. A tag between a non-space and a letter, digit or opening quote reads as one.
        if self.edge and buf and buf[-1][-1:].strip() and re.match(r"[\w\"'(“‘]", data):
            data = " " + data
        self.edge = False
        for act in self.open_actions:
            act[1].append(data)
        buf.append(data)

    def result(self) -> dict:
        while self.stack:
            self.emit(*self.stack.pop())
        self.flush()
        return {"title": norm(self.title), "lang": self.lang, "meta": self.meta, "links": self.links,
                "blocks": self.blocks, "actions": self.actions, "images": self.images, "fields": self.fields}


def page_text(page: dict) -> str:
    """Every word of a captured page, one block per line, as quotes are compared."""
    parts = [page.get("title", "")] + list(page.get("meta", {}).values())
    parts += [b["text"] for b in page.get("blocks", [])]
    parts += [x for a in page.get("actions", []) for x in (a.get("text"), a.get("label")) if x]
    parts += [i["alt"] for i in page.get("images", [])] + [v for f in page.get("fields", []) for v in f.values()]
    return "\n".join(match_form(p) for p in parts if p)


BRAND_FILE = re.compile(r"logo|wordmark|lockup|brandmark|favicon|apple-touch|apple-icon|^icon(?![a-z])|opengraph|"
                        r"og-image|^og[-_.]|twitter-image|social|share|manifest", re.I)
BRAND_EXT = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".ico", ".json", ".webmanifest"}


def image_size(p: Path, data: bytes):
    if p.suffix.lower() == ".svg":
        head = data[:4000].decode("utf-8", "replace")
        tag = re.search(r"<svg\b[^>]*>", head)
        if tag:
            w, h = (re.search(rf'\b{k}="([\d.]+)(?:px)?"', tag.group(0)) for k in ("width", "height"))
            if w and h:
                return f"{float(w.group(1)):g}x{float(h.group(1)):g}"
            vb = re.search(r'viewBox="[\d.-]+[ ,]+[\d.-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', tag.group(0))
            if vb:
                return f"{float(vb.group(1)):g}x{float(vb.group(2)):g}"
        return None
    if p.suffix.lower() in (".json", ".webmanifest"):
        return None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            return f"{im.size[0]}x{im.size[1]}"
    except Exception:
        return None


def brand_files(site: Site, limit: int = 300) -> list:
    """Logos, icons, share images and web manifests in the site's code, by name, with their size and hash."""
    out = []
    for dirpath, dirnames, filenames in os.walk(site.root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            ext = p.suffix.lower()
            if ext not in BRAND_EXT or not BRAND_FILE.search(p.stem) or not site.readable(p):
                continue
            if ext == ".json" and "manifest" not in p.stem.lower():
                continue
            data = p.read_bytes()
            item = {"path": site.rel(p), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            size = image_size(p, data)
            if size:
                item["size"] = size
            out.append(item)
            if len(out) >= limit:
                return out
    return out


def read(work, live: bool = False, base: str | None = None) -> dict:
    """capture.json and capture.md: the copy of every page of the brand's hosts, and the brand files in the code."""
    w = Work(work)
    local = None if live else (base or (w.site.get("serve") or {}).get("url"))
    if not live and not local:
        raise SystemExit("site.json has no serve.url for the local build: serve it, or read the live site with --live")
    cap = {"brand": w.brand, "date": date.today().isoformat(), "mode": "live" if live else "local", "hosts": {}}
    for host in w.hosts:
        src = f"https://{host}" if live else local
        get = (lambda p, s=src: fetch(s, p)) if live else (lambda p, s=src, h=host: fetch(s, p, h))
        paths = w.cfg.get("pages") or w.site.get("pages") or sitemap_paths(get, w.site.get("sitemap", "/sitemap.xml"))
        pages = {}
        for path in paths:
            r = get(path)
            ctype = r["headers"].get("content-type", "")
            if r["status"] != 200 or "html" not in ctype:
                pages[path] = {"status": r["status"], **({"location": r["headers"]["location"]}
                                                         if "location" in r["headers"] else {})}
                continue
            parser = Copy()
            parser.feed(r["body"].decode("utf-8", "replace"))
            parser.close()
            pages[path] = {"status": 200, **parser.result()}
        cap["hosts"][host] = {"pages": pages}
    cap["files"] = brand_files(w.site)
    (w.dir / "capture.json").write_text(json.dumps(cap, indent=1, ensure_ascii=False) + "\n")
    (w.dir / "capture.md").write_text(digest(cap))
    return cap


def digest(cap: dict) -> str:
    """capture.md: per page its title, meta, headings, first paragraphs, links and buttons, image text and form labels."""
    out = [f"# The copy of {cap['brand']} as read ({cap['mode']}, {cap['date']})", ""]
    for host, h in cap["hosts"].items():
        out += [f"## {host}", ""]
        for path, pg in h["pages"].items():
            if pg.get("status") != 200:
                out += [f"### {path}: HTTP {pg.get('status')} {pg.get('location', '')}".rstrip(), ""]
                continue
            out += [f"### {path}", "", f"- title: {pg['title']}"]
            out += [f"- {k}: {v}" for k, v in pg["meta"].items()]
            out += [f"- {b['tag']}: {b['text']}" for b in pg["blocks"] if b["tag"] in ("h1", "h2", "h3")]
            out += [f"- p: {b['text'][:300]}" for b in [b for b in pg["blocks"] if b["tag"] == "p"][:4]]
            acts = list(dict.fromkeys(a["text"] or a.get("label", "") for a in pg["actions"]))[:24]
            if acts:
                out.append("- links and buttons: " + " · ".join(f'"{x}"' for x in acts if x))
            alts = list(dict.fromkeys(i["alt"] for i in pg["images"]))[:12]
            if alts:
                out.append("- image text: " + " · ".join(f'"{x}"' for x in alts))
            fields = list(dict.fromkeys(v for f in pg["fields"] for v in f.values()))[:12]
            if fields:
                out.append("- form text: " + " · ".join(f'"{x}"' for x in fields))
            out.append("")
    out += ["## Brand files in the code", ""]
    out += [f"- {f['path']} ({f['bytes']} bytes{', ' + f['size'] if f.get('size') else ''})" for f in cap["files"]]
    return "\n".join(out) + "\n"


# ---------- check: the ledger ----------------------------------------------------------------------------------

def resolve(w: Work, s: dict, answers: dict, cache: dict):
    """Why a source does not resolve, or None when it does."""
    if not isinstance(s, dict):
        return "a source must be an object with a kind"
    kind, ref, quote = s.get("kind"), str(s.get("ref", "")), s.get("quote")
    if kind not in KINDS:
        return f"source kind {kind!r} is not one of {', '.join(KINDS)}"
    if kind == "page":
        if w.capture is None:
            return "a page source needs capture.json: run brandbook.py read"
        host, path = s.get("host"), s.get("path")
        page = ((w.capture.get("hosts") or {}).get(host) or {}).get("pages", {}).get(path)
        if not page or page.get("status") != 200:
            return f"{host}{path} is not a page in capture.json"
        if not norm(quote):
            return "a page source needs the quote, word for word"
        blocks = cache.setdefault((host, path), [squash(b) for b in page_text(page).split("\n")])
        if not any(squash(quote) in b for b in blocks):  # within one block: a quote never joins two of them
            return f"the quote is not on {host}{path} as read: {norm(quote)[:90]!r}"
    elif kind == "file":
        m = re.fullmatch(r"(.+?)(?::(\d+))?", ref)
        if not m:
            return "a file source needs ref: <path> or <path>:<line>"
        p = w.site.root / m.group(1)
        if not w.site.readable(p):
            return f"{m.group(1)} is not a file in the site's code (secret files are never read)"
        if m.group(2) or quote:
            lines = p.read_text(errors="replace").split("\n") if p.stat().st_size < 4_000_000 else []
            line = int(m.group(2) or 0)
            if m.group(2) and not 1 <= line <= len(lines):
                return f"{ref}: no such line (the file has {len(lines)})"
            if quote and match_form(quote) not in match_form(lines[line - 1] if line else "\n".join(lines)):
                return f"the quote is not in {ref}: {norm(quote)[:90]!r}"
    elif kind == "token":
        t = w.data["tokens"].get(ref)
        if not t:
            return f"token {ref!r} is not in usage.json"
        if not any(c in t["contexts"] for c in w.contexts):
            return f"token {ref!r} has no value for {w.brand} ({', '.join(w.contexts)})"
    elif kind == "finding":
        if w.findings is None:
            return "a finding source needs audit in brand.json (the audit's findings.json)"
        if ref not in w.findings:
            return f"finding {ref!r} is not in the audit"
    elif kind == "answer":
        a = answers.get(ref)
        if not a:
            return f"answer {ref!r} is not in the ledger's answers"
        if quote and match_form(quote) not in match_form(a.get("answer")):
            return f"the quote is not in the owner's answer {ref}: {norm(quote)[:90]!r}"
    elif kind == "shot":
        if w.shots is None:
            return "a shot source needs shots in brand.json (the baseline's screenshot folder)"
        p = (w.shots / ref).resolve()
        if not p.is_relative_to(w.shots) or not p.is_file():
            return f"shot {ref!r} is not in the baseline"
    return None


def check_ledger(w: Work) -> list:
    led = w.ledger
    w.facts, w.gaps, w.answers = {}, {}, {}
    if not isinstance(led, dict):
        return [problem("ledger", "ledger.json", "missing or not a JSON object")]
    out, cache = [], {}
    chapters = CORE + OPTIONAL
    for i, a in enumerate(led.get("answers", [])):
        aid = str(a.get("id", "")) if isinstance(a, dict) else ""
        where = f"ledger.json answer {aid or i}"
        if not ANSWER_ID.fullmatch(aid):
            out.append(problem("ledger", where, "needs an id such as A1"))
        elif aid in w.answers:
            out.append(problem("ledger", where, "the id is used twice"))
        elif not norm(a.get("question")) or not norm(a.get("answer")):
            out.append(problem("ledger", where, "needs the question and the owner's answer, word for word"))
        else:
            w.answers[aid] = a
    for i, g in enumerate(led.get("gaps", [])):
        gid = str(g.get("id", "")) if isinstance(g, dict) else ""
        where = f"ledger.json gap {gid or i}"
        if not GAP_ID.fullmatch(gid):
            out.append(problem("ledger", where, "needs an id such as G1"))
        elif gid in w.gaps:
            out.append(problem("ledger", where, "the id is used twice"))
        elif g.get("chapter") not in chapters or not norm(g.get("question")):
            out.append(problem("ledger", where, "needs a chapter id and the question for the owner"))
        elif g.get("answer") and g["answer"] not in w.answers:
            out.append(problem("ledger", where, f"its answer {g['answer']} is not in the ledger's answers"))
        else:
            w.gaps[gid] = g
    for i, f in enumerate(led.get("facts", [])):
        fid = str(f.get("id", "")) if isinstance(f, dict) else ""
        where = f"ledger.json fact {fid or i}"
        if not FACT_ID.fullmatch(fid):
            out.append(problem("ledger", where, "needs an id of lower-case letters, digits and hyphens"))
            continue
        if fid in w.facts:
            out.append(problem("ledger", where, "the id is used twice"))
            continue
        w.facts[fid] = f
        if f.get("chapter") not in chapters:
            out.append(problem("ledger", where, f"chapter {f.get('chapter')!r} is not one of {', '.join(chapters)}"))
        if not norm(f.get("fact")):
            out.append(problem("ledger", where, "needs the fact in one sentence"))
        if f.get("status") not in STATUSES:
            out.append(problem("status", where, f"status {f.get('status')!r} is not confirmed or observed"))
        sources = f.get("sources") or []
        if not isinstance(sources, list) or not sources:
            out.append(problem("source", where, "has no source"))
            continue
        for s in sources:
            why = resolve(w, s, w.answers, cache)
            if why:
                out.append(problem("source", where, why))
        kinds = {s.get("kind") for s in sources if isinstance(s, dict)}
        if f.get("status") == "confirmed" and "answer" not in kinds:
            out.append(problem("status", where, "is confirmed, but no answer of the owner backs it"))
        if f.get("status") == "observed" and not kinds - {"answer"}:
            out.append(problem("status", where, "cites only the owner's answers, so it is confirmed"))
        if f.get("chapter") in OWNER_ONLY and f.get("status") != "confirmed":
            out.append(problem("status", where, f"belongs to {f['chapter']}, which holds only the owner's own words: "
                                                f"ask the owner (a gap), never infer it from the site"))
    sample = w.cfg.get("sample")
    if sample and sample not in w.facts:
        out.append(problem("ledger", "brand.json sample", f"fact {sample!r} is not in the ledger"))
    return out


# ---------- check: the book ------------------------------------------------------------------------------------

def parse_book(text: str):
    """(title line, chapters, lines). A chapter is a '## ' heading with its id ({#colour}); it runs to the next one."""
    lines = text.split("\n")
    titles, chapters, fence = [], [], False
    for n, line in enumerate(lines, 1):
        if FENCE.match(line):
            fence = not fence
            continue
        m = None if fence else re.match(r"^(#{1,2})\s+(.+?)\s*$", line)
        if not m:
            continue
        if m.group(1) == "#":
            titles.append(n)
            continue
        idm = CHAPTER_ID.search(m.group(2))
        chapters.append({"id": idm.group(1) if idm else None, "title": CHAPTER_ID.sub("", m.group(2)).strip(),
                         "line": n})
    for i, c in enumerate(chapters):
        c["end"] = chapters[i + 1]["line"] - 1 if i + 1 < len(chapters) else len(lines)
    return titles, chapters, lines


def mark_items(inner: str) -> list:
    return [x.strip() for x in inner.split(",") if x.strip()]


def chapter_at(chapters: list, n: int):
    return next((c["id"] for c in reversed(chapters) if c["line"] <= n), None)


def prose(line: str) -> str:
    """A book line as its reader sees the words: marks, allow markers and heading ids gone."""
    return CHAPTER_ID.sub("", ALLOW_RE.sub("", MARK.sub("", line)))


def prose_blocks(lines: list) -> list:
    """(first line, text) of each paragraph, list item and table body row: the blocks a claim lives in. Headings, code,
    a picture or a specimen mark on its own line, rules and a table's head row hold none."""
    out, cur, fence, row = [], None, False, 0
    for n, line in enumerate(lines, 1):
        bare = ALLOW_RE.sub("", line).strip()
        if FENCE.match(line):
            fence = not fence
        if fence or FENCE.match(line) or not bare or re.match(r"#{1,6}\s", bare) or SPECIMEN_LINE.match(line) \
                or IMAGE_LINE.match(bare) or re.fullmatch(r"[-*_ ]{3,}", bare):
            cur, row = None, 0
            continue
        if bare.startswith("|"):
            cur = None
            if not TABLE_SEP.fullmatch(bare):
                row += 1
                if row > 1:  # the first row is the table's head
                    out.append([n, line])
            continue
        row = 0
        if LIST_ITEM.match(line) or cur is None:
            cur = [n, line]
            out.append(cur)
        else:
            cur[1] += "\n" + line
    return out


def quoted(text: str) -> list:
    """The words a book block puts in quotation marks, its code left out (code quotes CSS, not a source)."""
    plain = re.sub(r"`[^`]*`|<[^>]*>", " ", html.unescape(" ".join(prose(x) for x in text.split("\n"))))
    # a tag's attribute in quotation marks is not a quotation (the link check refuses raw HTML anyway)
    found = [norm(next(g for g in m.groups() if g is not None)) for m in QUOTE_RE.finditer(plain)]
    return [q for q in found if q]


def source_words(w: Work, ids: list) -> list:
    """What the cited facts' sources say: their quotes, and the whole answer for the owner's words."""
    out = []
    for i in ids:
        for s in w.facts[i].get("sources", []):
            if isinstance(s, dict):
                out += [s.get("quote") or ""]
                if s.get("kind") == "answer" and s.get("ref") in w.answers:
                    out.append(w.answers[s["ref"]].get("answer", ""))
    return [x for x in out if x]


def check_book(w: Work) -> list:
    out = []
    titles, chapters, lines = parse_book(w.book)
    if len(titles) != 1:
        out.append(problem("chapter", "book.md", f"needs exactly one title line ('# '), found {len(titles)}"))
    ids = []
    for c in chapters:
        where = f"book.md:{c['line']}"
        if not c["id"]:
            out.append(problem("chapter", where, "a chapter heading needs its id, such as {#colour}"))
        elif c["id"] not in CORE + OPTIONAL:
            out.append(problem("chapter", where, f"{c['id']!r} is not a chapter id ({', '.join(CORE + OPTIONAL)})"))
        elif c["id"] in ids:
            out.append(problem("chapter", where, f"chapter {c['id']} appears twice"))
        else:
            ids.append(c["id"])
    out += [problem("chapter", "book.md", f"core chapter {c} is missing") for c in CORE if c not in ids]
    order = [c for c in ids if c in CORE]
    if order != [c for c in CORE if c in order]:
        out.append(problem("chapter", "book.md", f"core chapters out of order: {', '.join(order)}"))
    cited = {}
    for n, line in enumerate(lines, 1):
        chap = chapter_at(chapters, n)
        for m in MARK.finditer(line):
            items = mark_items(m.group(1))
            if not items:
                out.append(problem("mark", f"book.md:{n}", "an empty mark"))
            for item in items:
                kind, _, arg = item.partition(":")
                arg = arg.strip()
                if kind == "open" and arg:
                    if arg not in w.gaps:
                        out.append(problem("mark", f"book.md:{n}", f"open question {arg} is not in the ledger's gaps"))
                        continue
                    if w.gaps[arg].get("answer"):
                        out.append(problem("mark", f"book.md:{n}", f"gap {arg} has the owner's answer "
                                                                   f"{w.gaps[arg]['answer']}: write it in"))
                    cited.setdefault(chap, []).append(("open", arg))
                elif kind == "specimen" and arg:
                    if arg not in SPECIMENS:
                        out.append(problem("mark", f"book.md:{n}", f"no specimen {arg!r} ({', '.join(SPECIMENS)})"))
                    elif SPECIMENS[arg] != chap:
                        out.append(problem("mark", f"book.md:{n}", f"the {arg} specimen belongs in chapter "
                                                                   f"{SPECIMENS[arg]}"))
                    elif not SPECIMEN_LINE.match(line):
                        out.append(problem("mark", f"book.md:{n}", "a specimen mark stands on its own line"))
                elif FACT_ID.fullmatch(item):
                    if item not in w.facts:
                        out.append(problem("mark", f"book.md:{n}", f"fact {item} is not in the ledger"))
                        continue
                    cited.setdefault(chap, []).append(("fact", item))
                    if chap in OWNER_ONLY and w.facts[item].get("status") != "confirmed":
                        out.append(problem("status", f"book.md:{n}", f"fact {item} sits in {chap}, which holds only "
                                                                     f"what the owner confirmed"))
                else:
                    out.append(problem("mark", f"book.md:{n}", f"unreadable mark [[{m.group(1)}]]: a fact id, "
                                                               f"open: <gap id> or specimen: <name>"))
    for c in chapters:
        # A chapter counts as filled by its own facts and gaps only: another chapter's fact cited here is fine, but
        # it does not stand in for this chapter's material.
        own = {k for k, i in cited.get(c["id"], []) if ((w.facts if k == "fact" else w.gaps).get(i) or {})
               .get("chapter") == c["id"]}
        if c["id"] in ("colour", "type") or c["id"] == "logo" and spec_logo_md(w):
            own.add("specimen")  # its values come from the token file and the logo files, so it is never empty
        if c["id"] in CORE and not own:
            out.append(problem("chapter", f"book.md:{c['line']}", f"chapter {c['id']} holds neither a fact of its own "
                                                                  f"nor its open question"))
        if c["id"] in OPTIONAL and "fact" not in own:
            out.append(problem("chapter", f"book.md:{c['line']}", f"optional chapter {c['id']} has no fact of its "
                                                                  f"own: leave it out until the brand has the material"))
    for first, text in prose_blocks(lines):
        items = [i for m in MARK.finditer(text) for i in mark_items(m.group(1))]
        facts = [i for i in items if i in w.facts]
        if items and not shown(" ".join(prose(x) for x in text.split("\n"))).strip():
            out.append(problem("mark", f"book.md:{first}", "a mark alone: it follows the words it supports"))
        if not facts and not any(i.startswith("open:") for i in items):
            out.append(problem("mark", f"book.md:{first}", "a paragraph without a fact mark: every claim about the "
                                                           "brand names its source"))
        said = [squash(s) for s in source_words(w, facts)]
        for q in quoted(text):
            if not any(squash(q) in s for s in said):
                out.append(problem("quote", f"book.md:{first}", f'"{q[:80]}" is not in the sources of the facts '
                                                                f"this paragraph cites: a quotation is word for word"))
    out += check_values(w, chapters, lines)
    return out


def allowed_colours(w: Work, contexts) -> set:
    return {i["hex"].lower() for t in w.data["tokens"].values() if t["type"] == "color"
            for c in contexts if (i := t["contexts"].get(c)) and i.get("hex")}


def allowed_fonts(w: Work, contexts) -> set:
    """The brand's families as norm_font keys: its font tokens and page font in these contexts, and the family names
    of the font files those families load (a file of Instrument Sans under a family the site named itself)."""
    fams = {f for t in w.data["tokens"].values() if t["type"] == "fontFamily" for c in contexts
            if (i := t["contexts"].get(c)) for f in i.get("families", [])}
    fams |= {f for c in contexts for f in w.stack(c)}
    keys = {T.norm_font(f) for f in fams}
    for face in w.data["fonts"].get("faces", []):
        if T.norm_font(face["family"]) in keys:
            keys.add(T.norm_font(T.font_stem(face["src"].split("?")[0])))
    return keys


def font_names(w: Work) -> list:
    f = w.data["fonts"]
    names = set(COMMON_FONTS) | {x for fs in f.get("tokens", {}).values() for x in fs}
    names |= {x["family"] for x in f.get("faces", []) + f.get("hardcoded", [])} | set(f.get("docs", {}))
    names |= {x for p in f.get("page", {}).values() for x in (p or {}).get("families") or []}
    return sorted({n for n in names if len(n) > 2 and n.lower() not in T.GENERIC_FONTS}, key=len, reverse=True)


def value_units(lines: list) -> list:
    """(first line, text, is code) of what the value check reads: each paragraph, item and row joined into one, and
    every other line alone (headings, a table's head row, code)."""
    units, covered, fence = [], set(), False
    for first, text in prose_blocks(lines):
        covered.update(range(first, first + text.count("\n") + 1))
        units.append((first, text, False))
    for n, line in enumerate(lines, 1):
        if FENCE.match(line):
            fence = not fence
        elif n not in covered and line.strip():
            units.append((n, line, fence))
    return sorted(units)


def check_values(w: Work, chapters: list, lines: list) -> list:
    """Every colour and font the book names is the brand's own in the token file, read from the words a reader sees
    (emphasis marks gone, entities decoded, a paragraph's lines joined). The brand family chapter may name the other
    brands' values too. A paragraph marked <!-- value-allow --> may name a value the brand never uses, when a fact it
    cites quotes it (the design doc's "never Comic Sans")."""
    out = []
    own_c, all_c = allowed_colours(w, w.contexts), allowed_colours(w, w.data["contexts"])
    own_f, all_f = allowed_fonts(w, w.contexts), allowed_fonts(w, w.data["contexts"])
    rxs = [(name, re.compile(r"(?<![\w-])" + re.escape(name).replace(r"\ ", r"\s+") + r"(?![\w-])", re.I))
           for name in font_names(w)]
    source = w.data.get("token_file", "the token file")
    for n, raw, code in value_units(lines):
        family = chapter_at(chapters, n) == "family"
        quoted_here = None
        if VALUE_ALLOW.search(raw):
            ids = [i for m in MARK.finditer(raw) for i in mark_items(m.group(1)) if i in w.facts]
            quoted_here = squash(" ".join(source_words(w, ids))).lower()
        joined = " ".join(prose(x) for x in raw.split("\n"))
        joined = re.sub(r"\]\([^)]*\)", "]()", joined)  # a link's target is not a colour: (#colour)
        line = html.unescape(joined if code else shown(joined))
        found = [m.group(0) for m in C.HEX_RE.finditer(line) if not line[max(0, m.start() - 1):m.start()].isalnum()]
        for m in C.FUNC_RE.finditer(line):
            end = C.call_span(line, m.start())
            found.append(line[m.start():end] if end > 0 else line[m.start():])
        for part in [joined] if code else re.findall(r"`([^`]*)`", joined):  # code: a named colour in a declaration
            for m in CSS_COLOUR.finditer(html.unescape(part)):
                found += [t for t in re.findall(r"[A-Za-z]+", m.group(1)) if t.lower() not in NOT_COLOURS and C.parse(t)]
        for lit in found:
            col = C.parse(lit)
            if not col:
                out.append(problem("colour", f"book.md:{n}", f"{lit} cannot be read as a colour"))
            elif C.hex(col).lower() not in (all_c if family else own_c) and not (
                    quoted_here and squash(lit).lower() in quoted_here):
                out.append(problem("colour", f"book.md:{n}", f"{lit} is not a colour of {w.brand} in {source}"
                                   + (", and no fact the paragraph cites quotes it" if quoted_here is not None else "")))
        rest = line
        for name, rx in rxs:
            for m in rx.finditer(rest):
                if T.norm_font(name) not in (all_f if family else own_f) and not (
                        quoted_here and squash(m.group(0)).lower() in quoted_here):
                    out.append(problem("font", f"book.md:{n}", f"{m.group(0)} is not a font of {w.brand} in {source}"))
            rest = rx.sub(lambda m: " " * len(m.group(0)), rest)
    return out


def banned_res(words: list) -> list:
    out = []
    for word in dict.fromkeys(w.lower() for w in words):
        stem = re.escape(word).replace(r"\ ", r"\s+")
        forms = stem + r"(?:s|es|d|ed|ing)?" + (f"|{re.escape(word[:-1])}ing" if word.endswith("e") else "")
        out.append((word, re.compile(rf"(?<![\w-])(?:{forms})(?![\w-])", re.I)))
    return out


def check_gate(w: Work, name: str, text: str) -> list:
    """The gate on the words a reader sees (emphasis marks gone, entities decoded). A line with <!-- gate-allow --> is
    skipped: the voice chapter has to spell its never-words out, and a quote keeps the site's own punctuation."""
    words = banned_res(w.banned)
    return [problem("gate", f"{name}:{n}", why) for n, raw in enumerate(text.split("\n"), 1)
            if not GATE_ALLOW.search(raw) for why in gate_hits(shown(prose(raw)), words)]


def link_problem(picture: bool, target: str, have: set):
    """Why a link or a picture may not stand in the kit, or None."""
    scheme = re.match(r"([A-Za-z][\w+.-]*):", target)
    if scheme or target.startswith("//"):
        if picture:
            return f"{target}: a picture comes from the kit's files, never from the network"
        if not scheme or scheme.group(1).lower() not in ("http", "https", "mailto"):
            return f"{target}: only http, https and mailto links"
        return None
    if target.startswith("#") and not picture:
        return None
    path = target.split("#")[0].split("?")[0]
    rel = posixpath.normpath(path) if path else ""
    if path.startswith("/") or rel.startswith("..") or rel not in have:
        return f"{target} is not a file of the kit"
    return None


def raw_html_in(text: str) -> list:
    """The raw HTML a book text holds, as Markdown itself finds it: a tag across lines and a comment included, code
    spans and the HTML a fenced code block becomes left out."""
    import markdown
    conv = markdown.Markdown(extensions=["tables", "sane_lists", "fenced_code"])
    fenced, mine = conv.preprocessors["fenced_code_block"], set()
    run = fenced.run

    def tracked(lines):  # the stash entries the fenced code step itself makes, by their place in the stash
        before = len(conv.htmlStash.rawHtmlBlocks)
        result = run(lines)
        mine.update(range(before, len(conv.htmlStash.rawHtmlBlocks)))
        return result
    fenced.run = tracked
    conv.convert("\n".join(prose(x) for x in text.split("\n")))
    return [h for i, h in enumerate(map(str, conv.htmlStash.rawHtmlBlocks))
            if i not in mine and not re.fullmatch(r"&#?\w+;", h)]  # an entity is not HTML


def rendered_targets(text: str) -> list:
    """(picture?, target) of every link and picture as Markdown renders the text, nested brackets included."""
    import markdown
    conv = markdown.Markdown(extensions=["tables", "sane_lists", "fenced_code"])
    conv.preprocessors.deregister("html_block")
    conv.inlinePatterns.deregister("html")
    out = conv.convert("\n".join(prose(x) for x in text.split("\n")))
    return [(m.group(1) == "img", html.unescape(m.group(2)))
            for m in re.finditer(r'<(a|img)\b[^>]*?\b(?:href|src)="([^"]*)"', out)]


def check_links(w: Work, name: str, text: str) -> list:
    """Every link and picture of the book or the front page: a picture is a file of the kit, a link a file of the kit,
    a place in the page, or an http, https or mailto address, and the text holds no raw HTML (the kit's Markdown files
    are shown as HTML where makers open them). Nothing else runs or loads when a maker opens the book."""
    out, have, seen = [], w.kit_files() | {"files"}, set()
    for n, raw in enumerate(text.split("\n"), 1):
        line, where = prose(raw), f"{name}:{n}"
        if REF_DEF.match(line):
            out.append(problem("link", where, "write the link where it stands, as [text](target)"))
        targets = [(m.group(0).startswith("!"), m.group(1)) for m in LINK_RE.finditer(line)]
        targets += [(False, m.group(1)) for m in AUTOLINK.finditer(line)]
        for picture, target in targets:
            seen.add((picture, target))
            why = link_problem(picture, target, have)
            if why:
                out.append(problem("link", where, why))
    for picture, target in rendered_targets(text):
        why = link_problem(picture, target, have)
        if why and (picture, target) not in seen:
            out.append(problem("link", name, why))
    lines = text.split("\n")
    for h in raw_html_in(text):
        n = next((i for i, x in enumerate(lines, 1) if h.split("\n")[0][:30] in x), None)
        out.append(problem("link", f"{name}:{n}" if n else name, f"raw HTML {' '.join(h.split())[:40]}: write it in "
                                                                  f"Markdown"))
    return out


def check(work) -> list:
    """Every problem of the ledger and, when it exists, of the book and its front page."""
    w = work if isinstance(work, Work) else Work(work)
    out = check_ledger(w)
    for name, rel in list(w.files.items()) + list(w.examples.items()):
        if not KIT_NAME.fullmatch(name):
            out.append(problem("files", f"brand.json files {name!r}", "a kit file name is one plain file name"))
    for name, rel in w.files.items():
        p = (w.site.root / str(rel)).resolve()
        if p.is_relative_to(w.dir) or p.is_relative_to(w.kit):
            out.append(problem("files", f"brand.json files {name!r}", "points into the work folder or the kit: the "
                                                                      "ledger and the owner's answers never ship"))
    known = known_paths(w) if w.book is not None or w.readme is not None else set()
    for name, text in (("book.md", w.book), ("readme.md", w.readme)):
        if text is None:
            continue
        if name == "book.md":
            out += check_book(w)
        out += check_gate(w, name, text) + check_links(w, name, text)
        hits, _ = furniture_text(name, "\n".join(MARK.sub("", line) for line in text.split("\n")),
                                 known, furniture_rules(w.people), [])
        out += [problem("furniture", where, f"{'; '.join(why)}: {line[:120]}") for where, why, line in hits]
    return out


# ---------- the furniture check: no internal working note reaches a maker ---------------------------------------

MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December"
          r"|(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?")
KUUT = r"(?:tammi|helmi|maalis|huhti|touko|kesä|heinä|elo|syys|loka|marras|joulu)kuu(?:ta|ssa|lla|n)?"


def furniture_rules(people: list) -> list:
    """What marks a working note. Every space in a pattern becomes \\s+, so a note broken across lines is still found.
    A standing rule ("changes must be approved by the brand owner") is not a note; a record of one decision is."""
    rules = [
        ("a date", r"\b\d{4}-\d{2}-\d{2}(?!\d)"),
        ("a date", r"(?<![\d.])\d{1,2}\.\d{1,2}\.\d{4}\b"),
        ("a date", r"(?<![\d/])\d{1,2}/\d{1,2}/\d{2,4}\b"),
        ("a date", rf"(?<!\d)\d{{1,2}}(?:st|nd|rd|th)?(?: of)?\s*(?i:{MONTHS})\b"),
        ("a date", rf"\b(?i:{MONTHS}),? \d{{4}}\b"),
        ("a date", rf"\b(?i:{MONTHS}) \d{{1,2}}(?:st|nd|rd|th)?\b"),
        ("a date", rf"(?i:\d{{1,2}}\. ?{KUUT}|\b{KUUT} \d{{4}})"),
        ("a date", r"(?i:\blast updated\b|\bupdated on\b)"),
        ("a person deciding", r"(?i:\b(?:his|her|their) (?:call|yes|word|decision)\b|\b(?:was|were|been) (?:approved|"
                              r"decided|chosen|signed off) by\b)|(?m:^)[>*_\s-]*(?:Approved|Decided|Chosen|Signed off) "
                              r"by\b|(?<=[.!?]\s)(?:Approved|Decided|Chosen|Signed off) by\b"),
        ("a decision note", r"(?i:\bdecided on\b)|\b(?:Decided|DECIDED|Decisions?|DECISIONS?):"),
        ("an approval note", r"(?i:\bstatus:)|\bAPPROVED\b"),
        ("a draft note", r"(?i:\bdraft (?:\d+|v\d+|for review|version)\b|\bfor review\b|\bwork in progress\b|"
                         r"\b(?:was|were|been) rejected\b)|\bWIP\b|\bREJECTED\b"),
        ("the decision log", r"\bDECISIONS\b"),
        ("an agent's notes", r"\bCLAUDE\b|\bAGENTS\.md\b|handoff\.md"),
        ("a working tool", r"\b[Cc]laude\b|GPT\b|\bCodex\b|\b[Ss]natcher\b|brand-skill|copywriting skill"),
        ("a working note", r"(?i:\bTODO\b|\bTBD\b|\bFIXME\b|lorem ipsum|edit here first|internal (?:document|note))"),
        ("an internal file", r"\bbrand-work\b|\b(?:ledger|capture|brand)\.json\b|\bcapture\.md\b"),
        ("a path a maker cannot open", r"~/|/Users/|/home/|/tmp/|/private/|/var/folders/|\b[A-Z]:\\"),
    ]
    if people:  # re.escape writes a space as "\ ": put the space back, so the line below makes it \s+
        rules.append(("a person deciding", r"\b(?:" + "|".join(re.escape(p).replace("\\ ", " ") for p in people)
                      + r")\b"))
    return [(why, re.compile(rx.replace(" ", r"\s+"))) for why, rx in rules]


def unspaced(people: list) -> re.Pattern:
    """The words of a note that hold no space: the PDF's text can come out with a word split by letter spacing."""
    return re.compile(r"\d{4}-\d{2}-\d{2}|DECISIONS|CLAUDE|Claude|GPT|Codex|[Ss]natcher|APPROVED|Status:|[Dd]ecided|"
                      r"Decision:|REJECTED|brand-skill|handoff\.md|brand-work|ledger\.json|TODO|TBD|FIXME|WIP"
                      + "".join("|" + re.escape(p.replace(" ", "")) for p in people))


CODE = re.compile(r"`([^`]+)`|<code[^>]*>([^<]+)</code>")
FILE_NAME = re.compile(r"^[\w@.-]*[\w@-]\.[A-Za-z][A-Za-z0-9]{0,11}$")
PATH = re.compile(r"^(?:/|(?:\.{1,2}/)*)[\w@.][\w@.-]*(?:/[\w@.-]+)*/?$")
TAG = re.compile(r"<!--.*?-->|<[^>]*>", re.S)
PNG = b"\x89PNG\r\n\x1a\n"
TEXT_KIT = {".md", ".html", ".css", ".svg", ".txt", ".js", ".json", ".webmanifest"}
# A licence text ships as its authors wrote it, dates and names included (the SIL OFL asks for its notice with every
# copy of the font): known by its name in the site's code, it is held to the bytes there instead of the note rules.
LICENCE_FILE = re.compile(r"(?i)(?:OFL|LICEN[CS]E|COPYING)(?:\.(?:txt|md))?")  # LICENSE-notes.md is a note
# Files without words are still opened: the bytes must be what the name says, and a picture's metadata is read.
MAGIC = {".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".gif": (b"GIF87a", b"GIF89a"),
         ".ico": (b"\x00\x00\x01\x00",), ".woff2": (b"wOF2",), ".woff": (b"wOFF",), ".ttf": (b"\x00\x01\x00\x00", b"true"),
         ".otf": (b"OTTO",), ".webp": (b"RIFF",), ".avif": (b"",)}


def shown(text: str) -> str:
    """The words a reader sees: tags, comments and emphasis marks gone, entities decoded, lines in place."""
    blanked = TAG.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    marks = re.compile(r"^\s*(?:>\s*)+|[*`]|(?<!\w)_+|_+(?!\w)")
    return "\n".join(" ".join(marks.sub("", html.unescape(line)).split()) for line in blanked.split("\n"))


def missing_paths(code: str, here: str, known: set):
    """The words in code type that name a file or folder that is neither in the kit nor in the site's code. Code type
    also holds commands, CSS, formats and domains, so a word is judged as a path only when it has a folder in it and
    ends in a file name or a slash. Yields each one with its offset in the code."""
    for m in re.finditer(r"\S+", code):
        word = m.group(0).strip("\"'").rstrip(".,;:)").lstrip("(")
        if "://" in word or "/" not in word or not PATH.match(word):
            continue
        if not (word.endswith("/") or FILE_NAME.match(word.rsplit("/", 1)[-1])):
            continue
        rel = word.rstrip("/")
        if rel not in known and os.path.normpath(os.path.join(here, rel)) not in known:
            yield m.start() + m.group(0).find(word), word


def allowance(texts, marker: re.Pattern) -> list:
    """What a marker in the book's source lets through in the built files: the visible words of the marked line's
    paragraph (of the row, in a table), squashed. A hit is let through only with its neighbouring words, so the
    marker never frees the same word elsewhere."""
    out = []
    for text in texts:
        lines = (text or "").split("\n")
        for i, line in enumerate(lines):
            if not marker.search(line):
                continue
            a = b = i
            if not line.lstrip().startswith("|"):
                def inside(k):
                    return lines[k].strip() and not lines[k].lstrip().startswith(("|", "#"))
                while a > 0 and inside(a - 1):
                    a -= 1
                while b + 1 < len(lines) and inside(b + 1):
                    b += 1
            words = "\n".join(prose(x) for x in lines[a:b + 1])
            words = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", words)  # a picture shows no words
            words = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", words).replace("|", " ")  # a link shows its text
            out.append(squash(shown(words)))
    return out


class Allowed:
    """Where the marked source paragraphs stand in a built text (its words compared without spaces and with straight
    quotes): a hit inside one of them passes, the same words anywhere else do not."""

    def __init__(self, text: str, scopes: list):
        self.spans = []
        keep = [i for i, c in enumerate(text) if not c.isspace()]
        flat = "".join(text[i] for i in keep).translate(str.maketrans("‘’“”", "''\"\""))
        for s in filter(None, scopes):
            k = flat.find(s)
            while k >= 0:
                self.spans.append((keep[k], keep[k + len(s) - 1] + 1))
                k = flat.find(s, k + 1)

    def covers(self, start: int, end: int) -> bool:
        return any(a <= start and end <= b for a, b in self.spans)


def furniture_text(path: str, text: str, known: set, rules: list, scopes: list, markers: bool = True):
    """(hits, lines): each line of a text file that holds a working note, in its source or in the words it shows. In
    the book's source a line with <!-- furniture-allow --> is skipped; a built file never grants itself that, and only
    the words of a marked source paragraph pass in it."""
    lines = text.split("\n")
    found = {}

    def add(version, allowed, start, end, why):
        first = version.count("\n", 0, start) + 1
        last = first + version.count("\n", start, end)
        if markers and any(FURNITURE_ALLOW.search(lines[k - 1]) for k in range(first, min(len(lines), last) + 1)):
            return
        if allowed.covers(start, end):
            return
        found.setdefault(first, set()).add(why)

    for version in (text, shown(text)):
        allowed = Allowed(version, scopes)
        for why, rx in rules:
            for m in rx.finditer(version):
                add(version, allowed, m.start(), m.end(), why)
    here = os.path.dirname(path)
    for m in CODE.finditer(text):
        group = 1 if m.group(1) is not None else 2
        code = html.unescape(m.group(group))
        for offset, word in missing_paths(code, here, known):
            line = text.count("\n", 0, m.start(group)) + code.count("\n", 0, offset) + 1
            if not (markers and FURNITURE_ALLOW.search(lines[line - 1])):
                found.setdefault(line, set()).add(f"a path a maker cannot open ({word})")
    return [(f"{path}:{n}", sorted(found[n]), lines[n - 1].strip()) for n in sorted(found)], lines


def flat_hits(where: str, flat: str, rules: list, scopes: list) -> list:
    allowed = Allowed(flat, scopes)
    spans = sorted((m.start(), m.end(), why) for why, rx in rules for m in rx.finditer(flat)
                   if not allowed.covers(m.start(), m.end()))
    groups = []
    for start, end, why in spans:  # matches close together are one note, reported once
        if groups and start <= groups[-1][1] + 40:
            groups[-1][1] = max(groups[-1][1], end)
            groups[-1][2].add(why)
        else:
            groups.append([start, end, {why}])
    return [(where, sorted(why), "..." + flat[max(0, s - 60):e + 60] + "...") for s, e, why in groups]


def pdf_parts(data: bytes) -> list:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    parts = [("info", " ".join(str(v) for v in (reader.metadata or {}).values()))]
    return parts + [(f"page {i}", " ".join((page.extract_text() or "").split())) for i, page in enumerate(reader.pages, 1)]


def pdf_hits(path: str, parts: list, rules: list, scopes: list, people: list) -> list:
    out, squeeze = [], unspaced(people)
    for where, flat in parts:
        out += flat_hits(f"{path} {where}", flat, rules, scopes)
        allowed = Allowed(flat, scopes)
        squeezed = flat.replace(" ", "")
        place = [i for i, c in enumerate(flat) if c != " "]
        for m in squeeze.finditer(squeezed):
            start, end = place[m.start()], place[m.end() - 1] + 1
            if " " not in flat[start:end]:
                continue  # whole in the text, so the rules above have judged it
            if (start and flat[start - 1].isalnum()) or (end < len(flat) and flat[end].isalnum()):
                continue  # it runs into a neighbouring word: "CSS print" is not "Sprint"
            if not allowed.covers(start, end):
                out.append((f"{path} {where}", ["a note split by the PDF's letter spacing"],
                            "..." + flat[max(0, start - 60):end + 60] + "..."))
    return out


def gate_spots(text: str, words: list) -> list:
    """(start, end, why) of each place a visible text breaks the gate: an em dash, an en dash anywhere but between
    two letters or digits (3–5), a banned word."""
    out = [(m.start(), m.end(), "an em dash") for m in re.finditer("[—―]", text)]
    out += [(m.start(), m.end(), "an en dash used as a dash") for m in re.finditer("–", text)
            if not (text[m.start() - 1:m.start()].isalnum() and text[m.end():m.end() + 1].isalnum())]
    return out + [(m.start(), m.end(), f"the banned word {word!r}") for word, rx in words for m in rx.finditer(text)]


def gate_hits(text: str, words: list) -> list:
    return sorted({why for _, _, why in gate_spots(text, words)})


def gate_built(where: str, text: str, words: list, scopes: list) -> list:
    """The gate on a built file's visible words, by line; the words of a gate-allow paragraph of the source pass."""
    text = shown(re.sub(r"<(style|script)\b.*?</\1>", " ", text, flags=re.S | re.I))
    allowed, lines, out = Allowed(text, scopes), {}, []
    for s, e, why in gate_spots(text, words):
        if not allowed.covers(s, e):
            lines.setdefault(text.count("\n", 0, s) + 1, set()).add(why)
    rows = text.split("\n")
    return [(f"{where}:{n}", [f"gate: {x}" for x in sorted(lines[n])], rows[n - 1].strip()) for n in sorted(lines)]


def gate_flat(where: str, flat: str, words: list, scopes: list) -> list:
    allowed = Allowed(flat, scopes)
    why = sorted({x for s, e, x in gate_spots(flat, words) if not allowed.covers(s, e)})
    return [(where, [f"gate: {x}" for x in why], flat[:160])] if why else []


def png_text(data: bytes) -> str:
    """The words a PNG carries in its text chunks, where an image tool can leave a prompt or a note."""
    if not data.startswith(PNG):
        raise ValueError("not a PNG inside")
    words, i = [], len(PNG)
    while i + 8 <= len(data):
        size, kind = struct.unpack(">I4s", data[i:i + 8])
        body, i = data[i + 8:i + 8 + size], i + 12 + size
        if kind == b"tEXt":
            words.append(body.replace(b"\0", b" ").decode("latin-1"))
        elif kind == b"zTXt":
            key, _, rest = body.partition(b"\0")
            words.append(key.decode("latin-1") + " " + zlib.decompress(rest[1:]).decode("latin-1"))
        elif kind == b"iTXt":
            key, _, rest = body.partition(b"\0")
            packed, rest = rest[0], rest[2:]
            _, _, rest = rest.partition(b"\0")
            title, _, text = rest.partition(b"\0")
            text = zlib.decompress(text) if packed else text
            words.append(" ".join(part.decode("utf-8", "replace") for part in (key, title, text)))
        elif kind == b"IEND":
            return " ".join(" ".join(words).split())
    raise ValueError("the file ends before its last chunk")


def real_format(ext: str, data: bytes) -> bool:
    if ext == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext == ".avif":
        return data[4:8] == b"ftyp" and b"avif" in data[8:32]
    return data.startswith(MAGIC[ext])


def image_words(data: bytes) -> str:
    """The words a JPEG, WebP, GIF or AVIF carries beside its pixels: comments, EXIF text (the Exif and GPS folders
    included), XMP. A camera or an image tool leaves names, dates and notes there. A file that does not decode
    raises: it cannot be checked, so it cannot ship."""
    from PIL import Image
    words = [m.group(0).decode("utf-8", "replace") for m in re.finditer(rb"<x:xmpmeta.*?</x:xmpmeta>", data, re.S)]

    def text_of(v):
        if isinstance(v, bytes):
            if v.startswith(b"UNICODE\0"):
                return v[8:].decode("utf-16", "replace")
            return v.replace(b"\0", b" ").decode("utf-8", "replace")
        return v if isinstance(v, str) else ""
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        words += [text_of(v) for k, v in im.info.items() if k in ("comment", "xmp")]
        exif = im.getexif()
        values = list(exif.values())
        for folder in (0x8769, 0x8825, 0xA005):  # Exif (UserComment lives here), GPS, interoperability
            try:
                values += list(exif.get_ifd(folder).values())
            except Exception:
                pass  # the folder is not there
        words += [text_of(v) for v in values]
    return " ".join(" ".join(words).split())


def known_paths(w: Work, root: Path | None = None) -> set:
    """Paths a maker can open: the kit's files and the site's code (a developer has the repository)."""
    root = root or w.kit
    known = set(w.kit_files()) | {"."}
    if root.is_dir():
        known |= {p.relative_to(root).as_posix() for p in root.rglob("*")}
    if w.design.is_dir():  # the generated design files, which sit in the project's design/ folder
        known |= {f"design/{p.name}" for p in w.design.iterdir() if p.is_file()} | {"design"}
    for dirpath, dirnames, filenames in os.walk(w.site.root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        rel = Path(dirpath).relative_to(w.site.root).as_posix()
        known |= {f if rel == "." else f"{rel}/{f}" for f in filenames + dirnames}
        if len(known) > 50_000:
            break
    for p in list(known):
        d = os.path.dirname(p)
        while d:
            known.add(d)
            d = os.path.dirname(d)
    return known


def inspect_kit(w: Work, root: Path | None = None):
    """(hits, broken, files) over every file of a kit: the furniture check on text files read whole, the PDF's text,
    PNG text chunks and other pictures' metadata, and the gate on the words the book shows. Every file must be what
    its name says; a file this check cannot read stops the build."""
    root = root or w.kit
    rules, known, words = furniture_rules(w.people), known_paths(w, root), banned_res(w.banned)
    f_scopes = allowance((w.book, w.readme), FURNITURE_ALLOW)
    g_scopes = allowance((w.book, w.readme), GATE_ALLOW)
    licences = {f"files/{name}": rel for name, rel in w.files.items()  # a link named LICENSE may lead to a note
                if LICENCE_FILE.fullmatch(Path(str(rel)).name) and LICENCE_FILE.fullmatch(w.site.file(rel).resolve().name)}
    hits, broken, seen = [], [], 0
    for p in sorted(root.rglob("*")):
        rel, ext = p.relative_to(root).as_posix(), p.suffix.lower()
        if p.is_symlink():
            broken.append(f"{rel}: a link, not a file")
            continue
        if not p.is_file() or p.name == ".DS_Store":
            continue
        seen += 1
        data = p.read_bytes()
        try:
            if rel in licences:
                data.decode("utf-8")
                if data != w.site.file(licences[rel]).read_bytes():
                    broken.append(f"{rel}: differs from the licence {licences[rel]} in the site's code")
            elif ext in TEXT_KIT:
                text = data.decode("utf-8")
                hits += furniture_text(rel, text, known, rules, f_scopes, markers=False)[0]
                hits += gate_built(rel, text, words, g_scopes)
            elif ext == ".pdf":
                parts = pdf_parts(data)
                hits += pdf_hits(rel, parts, rules, f_scopes, w.people)
                for where, flat in parts:
                    hits += gate_flat(f"{rel} {where}", flat, words, g_scopes)
            elif ext == ".png":
                words_in = png_text(data)
                hits += flat_hits(f"{rel} text inside the image", words_in, rules, [])
                hits += gate_flat(f"{rel} text inside the image", words_in, words, [])
            elif ext in MAGIC:
                if not real_format(ext, data):
                    broken.append(f"{rel}: not a {ext} file inside")
                elif ext not in (".woff2", ".woff", ".ttf", ".otf", ".ico"):
                    words_in = image_words(data)
                    hits += flat_hits(f"{rel} metadata (strip it before shipping)", words_in, rules, [])
                    hits += gate_flat(f"{rel} metadata", words_in, words, [])
            else:
                broken.append(f"{rel}: this check cannot read a {ext or 'extensionless'} file, and a maker receives it")
        except UnicodeDecodeError:
            broken.append(f"{rel}: not UTF-8 text")
        except Exception as e:  # pypdf and a broken PNG raise their own errors
            broken.append(f"{rel}: cannot be read ({type(e).__name__}: {e})")
    return hits, broken, seen


# ---------- build: the kit -------------------------------------------------------------------------------------

def key_colours(w: Work, ctx: str) -> list:
    """The colours a brand is known by: page, text, quiet text and up to three brand colours (the most used opaque
    ones that differ from the others)."""
    picks = [(n, k) for n, k in (("background", "band_background"), ("foreground", "band_text"),
                                 ("muted-foreground", "band_muted")) if w.hex_in(n, ctx)]
    seen = {w.hex_in(n, ctx) for n, _ in picks}
    toks = w.data["tokens"]
    for n in sorted((n for n, t in toks.items() if t["type"] == "color" and not n.startswith("color-")
                     and t.get("uses_all") and (T.group_of(n) == "brand" or n == "accent")),
                    key=lambda n: (-len(toks[n]["uses_all"]), n)):
        h = w.hex_in(n, ctx)
        if h and len(h) == 7 and h not in seen and len(picks) < 6:
            picks.append((n, "band_accent"))
            seen.add(h)
    return picks


def colour_rows(w: Work) -> list:
    """(group, [token...]) of every colour the code uses that has a value for the brand, the most used first."""
    toks = w.data["tokens"]
    names = sorted((n for n, t in toks.items() if t["type"] == "color" and not n.startswith("color-")
                    and t.get("uses_all") and any(w.hex_in(n, c) for c in w.contexts)),
                   key=lambda n: (-len(toks[n]["uses_all"]), n))
    groups = {}
    for n in names:
        groups.setdefault(T.group_of(n), []).append(n)
    return [(g, groups[g]) for g in ("surfaces", "text", "brand", "status", "lines", "charts", "other") if g in groups]


def text_pairs(w: Work, ctx: str) -> list:
    """Each text colour the code uses, on its own surface and on the page, with its WCAG ratio."""
    toks = w.data["tokens"]
    page = tuple(toks["background"]["contexts"][ctx]["rgba"]) if w.hex_in("background", ctx) else (1.0, 1.0, 1.0, 1.0)
    rows = []
    for t in sorted(toks, key=lambda n: (n != "foreground", -len(toks[n]["uses_all"]), n)):
        if not (t == "foreground" or t.endswith("-foreground")) or t.startswith("color-") or not toks[t]["uses_all"] \
                or not w.hex_in(t, ctx):
            continue
        x = "background" if t == "foreground" else t[: -len("-foreground")]
        bgs = [x] if x in toks and toks[x]["uses_all"] and w.hex_in(x, ctx) else []
        if x != "background" and (x not in toks or T.group_of(x) == "surfaces") and w.hex_in("background", ctx):
            bgs.append("background")
        for b in bgs:
            r = C.contrast(tuple(toks[t]["contexts"][ctx]["rgba"]), tuple(toks[b]["contexts"][ctx]["rgba"]), page)
            rows.append({"fg": t, "bg": b, "ratio": round(r, 2), "ok": r >= 4.5})
    return rows


def raw_in(w: Work, ctx: str):
    """A token's CSS value as the brand's context sets it (its own block, else the base it inherits)."""
    def get(name):
        ctxs = w.data["tokens"].get(name.lstrip("-"), {}).get("contexts") or {}
        i = ctxs.get(ctx) or ctxs.get("base") or next(iter(ctxs.values()), None)
        return i.get("css") if i else None
    return get


def families_in(w: Work, token: str, ctx: str) -> list:
    i = w.data["tokens"].get(token, {}).get("contexts", {}).get(ctx) or {}
    return i.get("families") or []


def mono_stack(w: Work, ctx: str) -> list:
    """The brand's monospace stack in its context: the first font token named mono that has a value there."""
    return next((fs for n in sorted(w.data["tokens"]) if "mono" in n and (fs := families_in(w, n, ctx))), [])


def split_size(s: str):
    """'var(--x) (width >= 48rem)' -> ('var(--x)', '(width >= 48rem)'): the media part a utility size carries starts at
    the first ' (' outside the value's own parentheses."""
    level = 0
    for k, ch in enumerate(s):
        if ch == "(":
            if level == 0 and k and s[k - 1] == " ":
                return s[:k - 1].strip(), s[k:]
            level += 1
        elif ch == ")":
            level -= 1
    return s.strip(), ""


def size_steps(w: Work) -> list:
    """(utility, px or None, css size, [media sizes]) of every text size the code uses, as the brand's main context
    resolves them, the largest first."""
    out, raw = [], raw_in(w, w.contexts[0])
    for u, v in w.data.get("utilities", {}).items():
        if not v.get("font-size") or not v.get("uses"):
            continue
        base, wide = None, []
        for s in v["font-size"]:
            value, media = split_size(s)
            value = T.resolve_vars(value, raw).strip()
            d = T.DIMENSION_RE.match(value)
            px = (float(d.group(1)) * (16 if d.group(2) in ("rem", "em") else 1)
                  if d and d.group(2) in ("px", "rem", "em") else None)
            if media:
                wide.append(f"{media} {value}")
            elif base is None:
                base = (px, value if T.SAFE_SIZE.fullmatch(value) else None)
        if base:
            out.append((u, base[0], base[1], wide))
    return sorted(out, key=lambda x: -(x[1] or 0))


def sample_text(w: Work) -> str:
    fact = w.facts.get(w.cfg.get("sample") or "")
    quote = next((s.get("quote") for s in (fact or {}).get("sources", []) if s.get("quote")), None)
    return norm(quote) or w.labels["specimen"]


def face_file(w: Work, face: dict):
    """The font file of an @font-face rule, in the site's code: woff2, woff, ttf or otf, under 3 MB, never a secret."""
    url = face["src"].split("?")[0].split("#")[0]
    if re.match(r"[a-z][\w+.-]*:", url, re.I):
        return None
    token_dir = (w.site.root / w.data["token_file"]).parent
    paths = (w.site.root / "public" / url.lstrip("/"), w.site.root / url.lstrip("/")) if url.startswith("/") \
        else (token_dir / url,)
    for p in paths:
        p = p.resolve()
        if (p.is_relative_to(w.site.root) and p.suffix.lower() in (".woff2", ".woff", ".ttf", ".otf") and p.is_file()
                and p.stat().st_size < 3_000_000 and w.site.readable(p)):
            return p
    return None


def font_faces(w: Work, embed: bool) -> str:
    """@font-face rules for the brand's fonts. The PDF embeds each font file; the kit's page uses a file only when
    brand.json `files` ships it (its licence allows sharing), and otherwise names the family."""
    used = {T.norm_font(f) for c in w.contexts for f in w.stack(c)}
    shipped = {(w.site.root / rel).resolve(): name for name, rel in w.files.items()}
    css = []
    for f in w.data["fonts"].get("faces", []):
        if T.norm_font(f["family"]) not in used or not re.fullmatch(r"[\w .-]{1,60}", f["family"]):
            continue
        p = face_file(w, f)
        if not p or not (embed or p in shipped):
            continue
        ext = p.suffix.lower()[1:]
        fmt = {"ttf": "truetype", "otf": "opentype"}.get(ext, ext)
        src = (f"url(data:font/{ext};base64,{base64.b64encode(p.read_bytes()).decode()})" if embed
               else f'url("files/{shipped[p]}")')
        style, weight = T.face_descriptors(f["style"], f["weight"])
        css.append(f"@font-face{{font-family:{T.css_family(f['family'])};src:{src} format(\"{fmt}\");"
                   f"font-style:{style};font-weight:{weight};font-display:block}}")
    return "".join(css)


def ink_on(hexv: str) -> str:
    col = C.parse(hexv)
    return "#ffffff" if C.contrast((1, 1, 1, 1), col) >= C.contrast((0, 0, 0, 1), col) else "#111111"


def spec_colour_html(w: Work) -> str:
    e, L = html.escape, w.labels
    out = ["<div class=spec>"]
    for c in w.contexts:
        out.append(f"<figure class=bands><figcaption>{e(w.names[c])}</figcaption><div class=row>")
        for n, k in key_colours(w, c):
            h = w.hex_in(n, c)
            out.append(f"<div class=band style='background:{e(h)};color:{ink_on(h)}'><b>{e(w.role(n) or L[k])}</b>"
                       f"<span>{e(h.upper())} <code>--{e(n)}</code></span></div>")
        out.append("</div></figure>")
    for g, names in colour_rows(w):
        out.append(f"<h4>{e(L['g_' + g])}</h4><table class=palette><thead><tr><th scope=col>{e(L['role'])}</th>"
                   + "".join(f"<th scope=col>{e(w.names[c])}</th>" for c in w.contexts) + "</tr></thead><tbody>")
        for n in names:
            role = w.role(n)
            out.append(f"<tr><th scope=row>{f'<span class=role>{e(role)}</span>' if role else ''}<code>--{e(n)}</code>"
                       "</th>" + "".join(f"<td><span class=chip style='background:{e(h)}'></span>{e(h.upper())}</td>"
                                         if (h := w.hex_in(n, c)) else "<td></td>" for c in w.contexts) + "</tr>")
        out.append("</tbody></table>")
    out.append(f"<h4>{e(L['contrast'])}</h4><p class=note>{e(L['contrast_intro'])}</p><div class=pairs>")
    for c in w.contexts:
        out.append(f"<div><p class=ctx>{e(w.names[c])}</p><ul>")
        for p in text_pairs(w, c):
            fg, bg = w.hex_in(p["fg"], c), w.hex_in(p["bg"], c)
            out.append(f"<li><span class=pair style='color:{e(fg)};background:{e(bg)}'>Aa</span><span class=names>"
                       f"<code>--{e(p['fg'])}</code><code>--{e(p['bg'])}</code></span><span class='ratio "
                       f"{'ok' if p['ok'] else 'bad'}'>{p['ratio']}:1 <small>{e(L['passes'] if p['ok'] else L['fails'])}"
                       "</small></span></li>")
        out.append("</ul></div>")
    out.append(f"</div><p class=source>{e(L['generated_from'])}: <code>{e(w.data['token_file'])}</code></p></div>")
    return "".join(out)


def spec_type_html(w: Work) -> str:
    e, L = html.escape, w.labels
    sample = sample_text(w)
    out, seen = ["<div class=spec>"], set()
    for c in w.contexts:
        fams = w.stack(c)
        if not fams or tuple(fams) in seen:
            continue
        seen.add(tuple(fams))
        stack = T.css_stack(fams)
        file = next((p.name for f in w.data["fonts"].get("faces", []) if T.norm_font(f["family"]) == T.norm_font(fams[0])
                     and (p := face_file(w, f))), None)
        line = (w.data["fonts"].get("page", {}).get(c) or {}).get("line")
        out.append(f"<figure class=face><figcaption>{e(w.names[c])}</figcaption><p class=aa style='font-family:"
                   f"{e(stack)}'>Aa</p><p class=fam style='font-family:{e(stack)}'>{e(fams[0])}</p><dl>"
                   + (f"<div><dt>{e(L['font_file'])}</dt><dd>{e(file)}</dd></div>" if file else "")
                   + f"<div><dt>{e(L['font_stack'])}</dt><dd>{e(', '.join(fams))}</dd></div>"
                   + (f"<div><dt>{e(L['defined_at'])}</dt><dd>{e(w.data['token_file'])}:{line}</dd></div>" if line else "")
                   + "</dl></figure>")
    steps = size_steps(w)
    if steps:
        first = T.css_stack(w.stack(w.contexts[0])) or "inherit"
        out.append(f"<h4>{e(L['scale'])}</h4><ol class=scale>")
        for u, px, css, wide in steps:
            out.append(f"<li><p class=step style='{e(f'font-size:{css};' if css else '')}font-family:{e(first)}'>"
                       f"{e(sample)}</p><p class=meta><code>.{e(u)}</code> {e(f'{px:g} px' if px else css or '')} "
                       + " ".join(f"<span>{e(x)}</span>" for x in wide) + "</p></li>")
        out.append("</ol>")
    out.append(f"<p class=source>{e(L['generated_from'])}: <code>{e(w.data['token_file'])}</code></p></div>")
    return "".join(out)


def spec_logo_html(w: Work) -> str:
    e = html.escape
    c = w.contexts[0]
    grounds = [w.hex_in("background", c) or "var(--bg)"]  # the ground the site shows it on; another one is a guess
    out = ["<div class=spec><div class=logos>"]
    for name in w.files:
        if Path(name).suffix.lower() in IMAGES and LOGO_NAME.search(name):
            tiles = "".join(f"<div class=tile style='background:{e(g)}'><img src='files/{e(name)}' alt=''></div>"
                            for g in grounds)
            out.append(f"<figure>{tiles}<figcaption><code>files/{e(name)}</code></figcaption></figure>")
    out.append("</div></div>")
    return "".join(out)


def spec_colour_md(w: Work) -> list:
    L = w.labels
    out = [f"{L['generated_from']}: `{w.data['token_file']}`", "",
           f"| {L['role']} | " + " | ".join(w.names[c] for c in w.contexts) + " |",
           "|---|" + "---|" * len(w.contexts)]
    for _, names in colour_rows(w):
        for n in names:
            role = w.role(n)
            out.append(f"| {role + ' ' if role else ''}`--{n}` | "
                       + " | ".join((w.hex_in(n, c) or "").upper() for c in w.contexts) + " |")
    out += ["", f"{L['contrast']}:", ""]
    for c in w.contexts:
        out += [f"- {w.names[c]}: " + "; ".join(f"`--{p['fg']}` / `--{p['bg']}` {p['ratio']}:1 "
                                                 f"({L['passes'] if p['ok'] else L['fails']})" for p in text_pairs(w, c))]
    return out


def spec_type_md(w: Work) -> list:
    L = w.labels
    out, stacks = [f"{L['generated_from']}: `{w.data['token_file']}`", "", f"{L['font_stack']}:", ""], {}
    for c in w.contexts:
        if w.stack(c):
            stacks.setdefault(tuple(w.stack(c)), []).append(w.names[c])
    out += [f"- {', '.join(names)}: {', '.join(fams)}" for fams, names in stacks.items()]
    steps = size_steps(w)
    if steps:
        out += ["", f"{L['scale']}:", ""]
        out += [f"- `.{u}` " + "; ".join([f"{px:g} px" if px else css or ""] + wide) for u, px, css, wide in steps]
    return out


def spec_logo_md(w: Work) -> list:
    return [f"- `files/{n}`" for n in w.files if Path(n).suffix.lower() in IMAGES and LOGO_NAME.search(n)]


def kit_markdown(w: Work) -> str:
    """brand-book.md for AI tools: the book's words without marks, with the specimens as tables of exact values."""
    _, chapters, lines = parse_book(w.book)
    spec_md = {"colour": spec_colour_md, "type": spec_type_md, "logo": spec_logo_md}
    placed = {m.group(1).strip() for line in lines for m in re.finditer(r"\[\[\s*specimen:\s*([\w-]+)\s*\]\]", line)}
    heads = {c["line"]: c["id"] for c in chapters}
    out, pending = [], None  # a chapter without a specimen mark gets its specimen at its end
    for n, line in enumerate(lines + [None], 1):
        if (n in heads or line is None) and pending:
            out += [""] + spec_md[pending](w) + [""]
            pending = None
        if line is None:
            break
        spec = re.fullmatch(r"\s*\[\[\s*specimen:\s*([\w-]+)\s*\]\]\s*", line)
        if spec:
            out += spec_md[spec.group(1)](w)
            continue
        out.append(prose(line).rstrip())
        if heads.get(n) in spec_md and heads[n] not in placed:
            pending = heads[n]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


PAGE_CSS = """
*{box-sizing:border-box}
html{background:var(--bg);color:var(--fg);font-family:var(--font);-webkit-print-color-adjust:exact;
 print-color-adjust:exact}
body{margin:0;font-size:17px;line-height:1.6}
.wrap{max-width:1040px;margin:0 auto;padding:56px 24px 96px}
a{color:var(--link)}
code{font-family:var(--mono);font-size:.88em}
header.cover{min-height:70vh;display:flex;flex-direction:column;justify-content:flex-end;padding-bottom:32px;
 border-bottom:1px solid var(--line)}
header.cover h1{font-size:clamp(44px,7vw,88px);line-height:1.02;letter-spacing:-.02em;margin:0 0 24px;max-width:14ch}
header.cover p{max-width:62ch;color:var(--muted);font-size:19px}
nav.toc{margin:40px 0 0}
nav.toc ol{columns:2;column-gap:40px;padding-left:1.4em;margin:0}
nav.toc li{margin:0 0 6px;break-inside:avoid}
article h2{font-size:clamp(30px,4vw,44px);line-height:1.1;letter-spacing:-.01em;margin:96px 0 20px;padding-top:24px;
 border-top:1px solid var(--line)}
article h3{font-size:22px;line-height:1.25;margin:40px 0 10px}
article h4{font-size:17px;margin:32px 0 10px}
article p,article li{max-width:68ch}
article blockquote{margin:20px 0;padding:2px 0 2px 20px;border-left:3px solid var(--accent)}
article table{border-collapse:collapse;width:100%;font-size:15px;margin:16px 0}
article th,article td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
article img{max-width:100%;height:auto}
article img.shot,article p>img{display:block;width:100%;max-height:960px;object-fit:cover;object-position:top;
 border:1px solid var(--line);border-radius:8px}
p.open{border-left:3px solid var(--accent);padding:4px 0 4px 16px}
p.open::before{content:attr(data-label);display:block;font-size:13px;letter-spacing:.06em;text-transform:uppercase;
 color:var(--muted)}
.spec{margin:28px 0 12px}
.bands{margin:0 0 20px}
.bands figcaption,.pairs .ctx,.face figcaption{font-size:13px;letter-spacing:.06em;text-transform:uppercase;
 color:var(--muted);margin:0 0 8px}
.bands .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.band{min-height:132px;padding:14px;border-radius:10px;display:flex;flex-direction:column;justify-content:space-between;
 box-shadow:inset 0 0 0 1px rgba(128,128,128,.28);font-size:15px}
.band span{font-size:13px}
.band code{opacity:.8}
.palette .chip{display:inline-block;width:18px;height:18px;border-radius:4px;vertical-align:-4px;margin-right:8px;
 box-shadow:inset 0 0 0 1px rgba(128,128,128,.35)}
.palette .role{display:block;font-weight:600}
.pairs{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}
.pairs ul{list-style:none;padding:0;margin:0}
.pairs li{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)}
.pairs .pair{display:inline-flex;align-items:center;justify-content:center;width:52px;height:40px;border-radius:6px;
 font-weight:700;box-shadow:inset 0 0 0 1px rgba(128,128,128,.28)}
.pairs .names{display:flex;flex-direction:column;flex:1;font-size:14px}
.pairs .ratio{font-weight:700;font-size:15px;text-align:right}
.pairs .ratio small{display:block;font-weight:400;color:var(--muted)}
.face{margin:0 0 24px;padding:20px;border:1px solid var(--line);border-radius:10px}
.face .aa{font-size:112px;line-height:1;margin:0}
.face .fam{font-size:28px;margin:8px 0 12px}
.face dl{display:grid;gap:4px;margin:0;font-size:15px}
.face dl div{display:flex;gap:12px}
.face dt{color:var(--muted);min-width:12ch}
.face dd{margin:0}
.scale{list-style:none;padding:0;margin:0}
.scale li{padding:10px 0;border-bottom:1px solid var(--line)}
.scale .step{margin:0;line-height:1.15;max-width:none;overflow-wrap:anywhere}
.scale .meta{margin:6px 0 0;font-size:13px;color:var(--muted)}
.scale .meta span{margin-left:10px}
.logos{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.logos figure{margin:0}
.logos .tile{display:flex;align-items:center;justify-content:center;min-height:150px;padding:28px;border-radius:10px;
 margin:0 0 8px;box-shadow:inset 0 0 0 1px rgba(128,128,128,.28)}
.logos .tile img{max-height:72px;max-width:80%}
.logos figcaption{font-size:14px;color:var(--muted)}
.source,.note{font-size:14px;color:var(--muted)}
footer.end{margin-top:96px;padding-top:16px;border-top:1px solid var(--line);font-size:14px;color:var(--muted)}
@page{size:A4;margin:16mm 15mm}
@media print{
 body{font-size:11pt}
 .wrap{max-width:none;padding:0}
 header.cover{min-height:auto;padding:30vh 0 24px}
 nav.toc{break-after:page}
 article h2{break-before:page;border-top:0;margin-top:0;padding-top:0}
 .band,.face,.logos figure,.pairs li,.scale li,tr,img{break-inside:avoid}
 article p>img{max-height:150mm}
 .spec p.source{break-before:avoid}
}
"""


def plain_stack(fams) -> str:
    """A font stack for the page's <style> element: only family names of letters, digits, spaces, dots and hyphens,
    so a name read from a site's CSS cannot close the element or add a rule."""
    return T.css_stack([f for f in fams or [] if re.fullmatch(r"[\w .-]{1,60}", f)])


def theme_css(w: Work) -> str:
    """The page's own colours and fonts: the brand's main context, with text colours that stay readable."""
    c = w.contexts[0]
    bg = w.hex_in("background", c) or "#ffffff"
    fg = w.hex_in("foreground", c) or ink_on(bg)
    ground = C.parse(bg)

    def readable(h, fallback):
        return h if h and C.contrast(C.parse(h), ground) >= 4.5 else fallback
    accents = [w.hex_in(n, c) for n, k in key_colours(w, c) if k == "band_accent"]
    accent = accents[0] if accents else fg
    mono = mono_stack(w, c)
    return (f":root{{--bg:{bg};--fg:{fg};--muted:{readable(w.hex_in('muted-foreground', c), fg)};"
            f"--line:{w.hex_in('border', c) or 'rgba(128,128,128,.3)'};--accent:{accent};--link:{readable(accent, fg)};"
            f"--font:{plain_stack(w.stack(c)) or 'system-ui, sans-serif'};"
            f"--mono:{plain_stack(mono) or 'ui-monospace, monospace'}}}"
            f"@page{{background:{bg}}}")  # the PDF's margins in the page colour too, not white around a dark book


def page_html(w: Work, embed: bool) -> str:
    """brand-book.html: the book set in the brand's own colours and type, its specimens made from the token file."""
    import markdown
    e, L = html.escape, w.labels
    titles, chapters, lines = parse_book(w.book)
    placed = {m.group(1).strip() for line in lines for m in re.finditer(r"\[\[\s*specimen:\s*([\w-]+)\s*\]\]", line)}
    src = []
    for line in lines:
        spec = re.fullmatch(r"\s*\[\[\s*specimen:\s*([\w-]+)\s*\]\]\s*", line)
        if spec:
            src += ["", f"EXDESIGNERSPECIMEN{spec.group(1).upper()}", ""]
            continue
        if any(item.startswith("open:") for m in MARK.finditer(line) for item in mark_items(m.group(1))):
            line = line + " EXDESIGNEROPEN"
        src.append(prose(line))
    first = chapters[0]["line"] - 1 if chapters else len(src)
    conv = markdown.Markdown(extensions=["tables", "sane_lists", "fenced_code"])
    conv.preprocessors.deregister("html_block")  # the book's words are text: raw HTML in them stays text
    conv.inlinePatterns.deregister("html")
    head = conv.convert("\n".join(src[:first]))
    conv.reset()
    body = conv.convert("\n".join(src[first:]))
    if body.count("<h2>") != len(chapters):
        raise SystemExit("book.md: a chapter heading the check cannot see (a heading underlined with --- or ===): "
                         "write every chapter as '## Title {#id}'")
    ids = iter(c["id"] for c in chapters)
    body = re.sub(r"<h2>", lambda m: f'<h2 id="{e(next(ids))}">', body)
    specs = {"colour": spec_colour_html, "type": spec_type_html, "logo": spec_logo_html}
    for name, make in specs.items():
        token = f"<p>EXDESIGNERSPECIMEN{name.upper()}</p>"
        head_at = body.find(f'<h2 id="{name}">')
        if token in body:
            body = body.replace(token, make(w), 1)
        elif name not in placed and head_at >= 0:  # no mark: the specimen closes its chapter
            end = body.find("<h2 ", head_at + 1)
            end = len(body) if end < 0 else end
            body = body[:end] + make(w) + body[end:]
    body = re.sub(r"<p>((?:(?!</p>).)*?)\s*EXDESIGNEROPEN((?:(?!</p>).)*)</p>",
                  lambda m: f"<p class=open data-label='{e(L['open'])}'>{m.group(1)}{m.group(2)}</p>", body, flags=re.S)
    body = body.replace(" EXDESIGNEROPEN", "").replace("EXDESIGNEROPEN", "")  # an open question in a list or a table
    head = head.replace(" EXDESIGNEROPEN", "").replace("EXDESIGNEROPEN", "")
    title = re.sub(r"<[^>]+>", "", re.search(r"<h1>(.*?)</h1>", head, re.S).group(1)) if "<h1>" in head else w.brand
    toc = "".join(f"<li><a href='#{e(c['id'])}'>{e(c['title'])}</a></li>" for c in chapters)
    version = L["version"].replace("{version}", str(w.cfg.get("version", "1")))
    return (f"<!doctype html><html lang={'fi' if w.lang == 'fi' else 'en'}><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'><title>{title}</title>"
            f"<style>{font_faces(w, embed)}{theme_css(w)}{PAGE_CSS}</style></head><body><div class=wrap>"
            f"<header class=cover>{head}</header><nav class=toc aria-label='{e(L['nav'])}'><ol>{toc}</ol></nav>"
            f"<article>{body}</article><footer class=end>{e(version)}</footer></div></body></html>\n")


def to_pdf(page: Path, pdf: Path, limit: int = 90) -> int:
    """Print the page to A4 with the Mac's Google Chrome. The PDF is replaced only once a reader has opened the new
    one and found pages in it, so a crashed run cannot leave a half-written book under the real name."""
    if not Path(CHROME).exists():
        raise SystemExit(f"Google Chrome is not at {CHROME}: it prints the PDF")
    import pypdf
    tmp = pdf.with_suffix(".pdf.part")
    tmp.unlink(missing_ok=True)
    profile = tempfile.mkdtemp(prefix="ex-designer-chrome-")
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
                             "--allow-file-access-from-files", f"--user-data-dir={profile}",
                             # Nothing loads from the network, not even 127.0.0.1: every request goes to a proxy
                             # that does not exist; the book's own files and embedded fonts are not requests.
                             "--host-resolver-rules=MAP * ~NOTFOUND", "--proxy-server=http://127.0.0.1:9",
                             "--proxy-bypass-list=<-loopback>",
                             "--virtual-time-budget=15000", f"--print-to-pdf={tmp}", page.as_uri()],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    size, stable = -1, 0
    try:
        for _ in range(limit):  # headless Chrome often never exits after writing: wait for the file to stop growing
            if proc.poll() is not None:
                break
            if tmp.exists():
                now = tmp.stat().st_size
                stable = stable + 1 if now > 0 and now == size else 0
                size = now
                if stable >= 2:
                    break
            time.sleep(1)
        else:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f"printing to PDF timed out: {pdf} was not replaced")
    finally:
        proc.kill()
        proc.wait()
        shutil.rmtree(profile, ignore_errors=True)
    try:
        pages = len(pypdf.PdfReader(tmp).pages)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"the printed PDF does not open: {pdf} was not replaced ({e})")
    if not pages:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"the printed PDF has no pages: {pdf} was not replaced")
    tmp.replace(pdf)
    return pages


def build(work) -> dict:
    """The kit, after every check passes. It is made whole in a folder of its own next to the kit, checked there (the
    furniture check and the gate on every file), and only then put in the kit's place; a failed build leaves the kit
    as it was."""
    w = work if isinstance(work, Work) else Work(work)
    missing = [n for n, t in (("book.md", w.book), ("readme.md", w.readme)) if t is None]
    problems = [problem("chapter", n, "missing: the build needs it") for n in missing] + check(w)
    if w.kit.is_symlink() or w.kit.exists() and not w.kit.is_dir():
        problems.append(problem("files", f"brand.json kit {w.kit}", "is a link or a file, not a folder"))
    elif w.kit.is_dir():
        stray = sorted(p.name for p in w.kit.iterdir() if p.name not in KIT_BOOK + ("files", ".DS_Store"))
        if stray:  # the build makes the kit whole: a folder with other things in it is the wrong folder
            problems.append(problem("files", f"brand.json kit {w.kit}", f"holds {', '.join(stray[:5])}: point the "
                                                                        f"kit to a folder of its own"))
    want = {}
    for name, rel in w.files.items():
        want[name] = w.site.file(rel)
    for name, rel in w.examples.items():
        p = (w.shots / rel).resolve() if w.shots else None
        if not p or not p.is_relative_to(w.shots) or not p.is_file() or secret_name(p) or p.is_relative_to(w.dir):
            problems.append(problem("files", f"brand.json examples {name!r}", f"{rel} is not a screenshot in the "
                                                                             f"baseline's shots"))
        else:
            want[name] = p
    if problems:
        return {"ok": False, "code": 1, "problems": problems, "written": []}
    w.kit.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{w.kit.name}-", dir=w.kit.parent))
    try:
        (stage / "files").mkdir()
        for name, p in want.items():
            shutil.copyfile(p, stage / "files" / name)
        (stage / "brand-book.md").write_text(kit_markdown(w))
        (stage / "brand-book.html").write_text(page_html(w, embed=False))
        (stage / "README.md").write_text("\n".join(prose(line).rstrip() for line in w.readme.split("\n")).strip()
                                         + "\n")
        with tempfile.TemporaryDirectory(prefix="ex-designer-book-") as tmp:
            printed = Path(tmp) / "brand-book.html"
            printed.write_text(page_html(w, embed=True))
            os.symlink(stage / "files", Path(tmp) / "files")
            pages = to_pdf(printed, stage / "brand-book.pdf")
        hits, broken, seen = inspect_kit(w, stage)
        found = [problem("gate" if all(x.startswith("gate: ") for x in why) else "furniture", where,
                         f"{'; '.join(why)}: {line[:160]}") for where, why, line in hits]
        found += [problem("files", "kit", b) for b in broken]
        if found:
            return {"ok": False, "code": 1 if hits else 2, "problems": found, "written": [], "checked": seen}
        if w.kit.exists():  # swap: the old kit holds only kit files (checked above), so it goes whole
            old = w.kit.with_name(f".{w.kit.name}-old-{stage.name[-8:]}")
            w.kit.rename(old)
            stage.rename(w.kit)
            shutil.rmtree(old)
        else:
            stage.rename(w.kit)
        written = sorted(p.relative_to(w.kit).as_posix() for p in w.kit.rglob("*") if p.is_file())
        return {"ok": True, "code": 0, "pdf_pages": pages, "problems": [], "written": written, "checked": seen}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def summary(w: Work) -> str:
    """The ledger by chapter and the open gaps: what to ask the owner next, one question per message."""
    out, facts = [], list(w.facts.values())
    conf = sum(1 for f in facts if f.get("status") == "confirmed")
    open_gaps = [g for g in w.gaps.values() if not g.get("answer")]
    out.append(f"Ledger: {len(facts)} facts ({conf} confirmed, {len(facts) - conf} observed), {len(w.answers)} answers, "
               f"{len(open_gaps)} open gaps")
    for c in CORE + OPTIONAL:
        fs = [f for f in facts if f.get("chapter") == c]
        gs = [g for g in open_gaps if g.get("chapter") == c]
        if fs or gs or c in CORE:
            out.append(f"  {c:<10} {len(fs):>3} facts ({sum(1 for f in fs if f.get('status') == 'confirmed')} "
                       f"confirmed), {len(gs)} open gaps")
    if open_gaps:
        out.append("Open gaps, in order:")
        out += [f"  {g['id']} [{g['chapter']}] {norm(g['question'])}" for g in open_gaps]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read", help="capture the brand's copy and files")
    r.add_argument("--work", required=True)
    r.add_argument("--live", action="store_true", help="read the live hosts instead of the local build")
    for name in ("check", "build"):
        sub.add_parser(name).add_argument("--work", required=True)
    a = ap.parse_args()
    if a.cmd == "read":
        cap = read(a.work, live=a.live)
        n = sum(1 for h in cap["hosts"].values() for p in h["pages"].values() if p.get("status") == 200)
        print(f"read {n} pages on {', '.join(cap['hosts'])}, {len(cap['files'])} brand files: "
              f"{Path(a.work) / 'capture.json'}, {Path(a.work) / 'capture.md'}")
        return 0
    w = Work(a.work)
    if a.cmd == "check":
        problems = check(w)
        for p in problems:
            print(f"{p['where']}: {p['text']} [{p['rule']}]")
        print(summary(w))
        print(("book.md: not written yet, so only the ledger was checked\n" if w.book is None else "")
              + (f"FAIL: {len(problems)} problems" if problems else "check: clean"))
        return 1 if problems else 0
    result = build(w)
    for p in result["problems"]:
        print(f"{p['where']}: {p['text']} [{p['rule']}]")
    if result["written"]:
        print(f"kit: {w.kit} ({', '.join(result['written'])}), the PDF {result['pdf_pages']} pages; furniture "
              f"check and gate on {result['checked']} files")
    print("build: done" if result["ok"] else "FAIL: nothing goes to makers until this is clean")
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
