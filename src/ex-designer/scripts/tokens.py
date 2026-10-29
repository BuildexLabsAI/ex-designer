"""Read a site's design values from its own token file and count where the code uses each one.

  python3 tokens.py extract --site tools/site.json --out design/
      design/tokens.json  DTCG 2025.10, generated from the token file: never edit it, edit the token file
      design/usage.json   every token per context (base, dark, each brand), its uses (file:line), the values
                          outside the tokens, near-duplicate colours (CIEDE2000 below 2), fonts, coverage
  python3 tokens.py page --site tools/site.json --design design/ [--labels ui-labels.json] [--lang fi] [--roles r.json]
      design/system.html  the design system as a document: each brand's key colours, every colour by role with
                          one column per brand, fonts, type sizes, corners, readable text and background pairs
  python3 tokens.py questions --site tools/site.json --design design/ [--labels ui-labels.json] [--lang fi]
      the owner's questions and the gaps, numbered, for the confirm step in chat (one question per message)
  python3 tokens.py check --site tools/site.json --design design/
      exit 1 when the code now holds colours or fonts outside the tokens that design/usage.json did not have

Contexts come from the token file's selectors: `:root` and `@theme` are base; `.dark`, `[data-theme="dark"]` and
`@media (prefers-color-scheme: dark)` are the dark mode; `[data-brand="x"]`, `.brand-x`, `[data-site="x"]` are brands.
Output names a value and where it is (file:line), never the source line around it, so a key in a scanned file cannot
leak into a report. Secret files (.env, *.pem, .dev.vars...) are never read, whatever the globs say.
"""
import argparse
import ast
import base64
import html
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import color as C  # noqa: E402
from lib.site import Site  # noqa: E402

COLOR_PREFIXES = ("bg|text|border|border-[trblxyse]|ring|ring-offset|outline|fill|stroke|from|via|to|decoration|"
                  "shadow|inset-shadow|caret|accent|divide|placeholder")
PALETTE = ("slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|"
           "violet|purple|fuchsia|pink|rose")
CLASS_EDGE_L = r"(?<![\w$/.-])"
CLASS_EDGE_R = r"(?![\w-])"
VARIANTS = r"(?:[\w\[\]&@*-]+:)*!?"
GENERIC_FONTS = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif",
                 "ui-monospace", "ui-rounded", "math", "emoji", "fangsong", "-apple-system", "blinkmacsystemfont",
                 "inherit", "initial", "unset", "revert", "var"}
NOT_COLORS = {"transparent", "currentcolor", "inherit", "initial", "unset", "revert", "none", "auto"}
COLOR_PROPS = (r"color|background|background-color|border|border-(?:top|right|bottom|left|block|inline)(?:-color)?|"
               r"border-color|outline|outline-color|fill|stroke|text-decoration-color|caret-color|accent-color|"
               r"stop-color|flood-color|box-shadow|text-shadow|backgroundColor|borderColor|outlineColor|caretColor|"
               r"accentColor|stopColor|textDecorationColor")
ATTR_VALUE = re.compile(r"\b(?:href|src|srcset|poster|xlink:href|action|to|id|for|name|key|data-[\w-]+)\s*=\s*\{?\s*"
                        r"[\"'`][^\"'`]*$")
URL_OPEN = re.compile(r"url\(\s*[\"']?[^)]*$")
PALETTE_RE = re.compile(CLASS_EDGE_L + VARIANTS + rf"-?(?:{COLOR_PREFIXES})-(?:({PALETTE})-(50|[1-9]00|950)|(white|black))"
                        + r"(?:/[\w.\[\]%]+)?" + CLASS_EDGE_R)
ARBITRARY_RE = re.compile(CLASS_EDGE_L + VARIANTS + rf"-?({COLOR_PREFIXES}|font|rounded(?:-[trblse]{{1,2}})?)-\[([^\]\s]+)\]")
DIMENSION_RE = re.compile(r"^(-?\d*\.?\d+)(px|rem|em|%)?$")
SURFACE = r"background|surface|card|popover|muted|secondary|sidebar|paper|canvas|panel"


# ---------- reading CSS --------------------------------------------------------------------------------------

def blank(text: str, spans) -> str:
    """Text with each span replaced by spaces (newlines kept), so offsets and line numbers stay right."""
    chars = list(text)
    for a, b in spans:
        for i in range(a, b):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def strip_comments(text: str, js: bool) -> str:
    """Comments blanked: /* */, <!-- -->, and // in code. A comment mark inside a string ("image/*", "https://") is
    text, not a comment."""
    spans, i, n, quote = [], 0, len(text), None
    while i < n:
        ch = text[i]
        if ch == "\\":  # an escaped character is never a quote or a comment mark
            i += 2
            continue
        if quote:
            if ch == quote or (ch == "\n" and quote != "`"):
                quote = None
            i += 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            spans.append((i, end))
            i = end
            continue
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            end = n if end < 0 else end + 3
            spans.append((i, end))
            i = end
            continue
        if js and text.startswith("//", i) and (i == 0 or text[i - 1] not in ":\\"):
            end = text.find("\n", i)
            end = n if end < 0 else end
            spans.append((i, end))
            i = end
            continue
        if ch in "\"'" or (js and ch == "`"):
            quote = ch
        i += 1
    return blank(text, spans)


def css_blocks(css: str):
    """(chain, declarations) for every block: chain is the tuple of preludes from the outside in; a declaration is
    (property, value, line, start, end) with offsets into css."""
    out, stack, buf_start, depth_paren, quote, i = [], [((), [])], 0, 0, None, 0
    while i < len(css):
        ch = css[i]
        if ch == "\\":  # an escaped character (Tailwind's .w-\[calc\(100\%\)\], .content-\[\'x\'\]) is never syntax
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren = max(0, depth_paren - 1)
        elif depth_paren == 0 and ch in "{};":
            seg = css[buf_start:i]
            if ch == "{":
                stack.append((stack[-1][0] + (" ".join(seg.split()),), []))
            else:
                if ":" in seg and seg.strip() and not seg.strip().startswith("@"):
                    lead = len(seg) - len(seg.lstrip())
                    prop, _, value = seg.strip().partition(":")
                    a = buf_start + lead
                    stack[-1][1].append((prop.strip(), value.strip(), css.count("\n", 0, a) + 1, a, i))
                if ch == "}" and len(stack) > 1:
                    out.append(stack.pop())
            buf_start = i + 1
        i += 1
    while len(stack) > 1:
        out.append(stack.pop())
    out.append(stack[0])
    return out


GLOBAL_PARTS = re.compile(r":root|\bhtml\b|:host|\bbody\b|\*|&|:is\(|:where\(|\)|"
                          r"\.dark\b|\.light\b|\.(?:brand|site)-[\w-]+|\[data-[\w-]+(?:=[\"']?[\w-]+[\"']?)?\]|\s|>|,")


def print_only(at: str) -> bool:
    """True for an @media rule that never applies on screen: every query in its list is a print query (`print`,
    `only print and (...)`). `not print`, `screen` or a query without a media type can apply on screen."""
    if not at.startswith("@media"):
        return False
    queries = split_selectors(at[len("@media"):].strip().lower())
    return bool(queries) and all(re.match(r"(?:only\s+)?print\b", q) for q in queries)


def context_of(chain: tuple) -> str | None:
    """'base', 'dark', '<brand>' or '<brand>/dark' for a block's selector chain; None for blocks without tokens.
    A selector of plain classes (.theme-v2, :root:has(.app)) gives '~<class>': a theme variant when its block
    redefines the site's base tokens, a component's own variables when it does not (read_tokens decides)."""
    text = " ".join(chain)
    if "@keyframes" in text or any(print_only(c) for c in chain):
        return None  # print styles never render on screen
    sel = chain[-1] if chain and not chain[-1].startswith("@") else ""
    dark = bool(re.search(r"\.dark\b|\[data-(?:theme|mode|color-scheme)=[\"']?dark|prefers-color-scheme:\s*dark", text))
    m = (re.search(r"\[data-(?:brand|site|tenant)=[\"']?([\w-]+)", text) or re.search(r"\.(?:brand|site)-([\w-]+)", text)
         or re.search(r"\[data-theme=[\"']?((?!dark|light)[\w-]+)", text))
    brand = m.group(1) if m else None
    rest = GLOBAL_PARTS.sub("", sel) if sel else ""
    if rest:
        variant = re.fullmatch(r"(?::has\()?\.([\w-]+)(?:\.[\w-]+)*", rest.replace(":has(", ":has(", 1))
        if not variant:
            return None
        brand = "~" + variant.group(1)
    if brand and dark:
        return f"{brand}/dark"
    return brand or ("dark" if dark else "base")


def applies(ctx: str) -> set[str]:
    """The contexts whose declarations reach an element in ctx: a brand in dark mode gets base, dark, the brand and
    the brand's own dark block."""
    if ctx == "base":
        return {"base"}
    if ctx == "dark":
        return {"dark", "base"}
    if ctx.endswith("/dark"):
        return {ctx, ctx.split("/")[0], "dark", "base"}
    return {ctx, "base"}


def families(value: str) -> list[str]:
    return [f.strip().strip("\"'") for f in C._split_top(value, ",") if f.strip()]


def font_stem(path: str) -> str:
    """The family part of a font file's name: Soehne-Buch.woff2 -> Soehne."""
    return re.split(r"[-_ ](?:thin|extralight|light|regular|book|buch|medium|semibold|bold|extrabold|black|heavy|"
                    r"italic|kursiv|halbfett|dreiviertelfett|fett|leicht|extraleicht|mono|\d)", Path(path).stem,
                    flags=re.I)[0]


def norm_font(name: str) -> str:
    s = name.casefold().replace("ö", "oe").replace("ä", "ae").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s)


# ---------- the token file -----------------------------------------------------------------------------------

def split_selectors(prelude: str) -> list[str]:
    """A selector list split at its commas (not those inside parentheses or brackets)."""
    out, depth, cur = [], 0, ""
    for ch in prelude:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return [x for x in out + [cur.strip()] if x]


def specificity(sel: str) -> tuple[int, int, int]:
    """CSS specificity (ids, classes/attributes/pseudo-classes, types/pseudo-elements); :where() counts nothing."""
    s = re.sub(r":where\([^()]*\)", "", sel)
    ids = len(re.findall(r"#[\w-]+", s))
    classes = len(re.findall(r"\.[\w-]+|\[[^\]]*\]|(?<!:):(?!:)[\w-]+", s))
    types = len(re.findall(r"(?:^|[\s>+~(])[a-zA-Z][\w-]*", s)) + len(re.findall(r"::[\w-]+", s))
    return ids, classes, types


def read_tokens(path: Path):
    """Tokens of a token file. Each token keeps every declaration as (context, value, line, order, important,
    specificity); `decl` holds the winner per context. A selector list declares for each of its selectors. `@theme`
    variables count as base and lose to everything else (Tailwind emits them first). Also returns the @utility
    definitions, the fonts (@font-face families and rules, and the font-family a context's own selector sets: the font
    of a theme like .theme-v2) and the file's text with token declarations blanked (scanned for uses)."""
    css = strip_comments(path.read_text(encoding="utf-8", errors="replace"), js=False)
    tokens, spans, utilities, faces = {}, [], {}, []
    face_rules, page_fonts = [], []
    utility_spans = [m.span() for m in re.finditer(r"@utility\s+[\w-]+", css)]
    spans += utility_spans
    for chain, decls in css_blocks(css):
        if any(print_only(c) for c in chain):
            utility_spans += [(a, b) for *_, a, b in decls]  # print styles: neither tokens nor on-screen uses
            spans += [(a, b) for *_, a, b in decls]
            continue
        util = next((c for c in chain if c.startswith("@utility")), None)
        if util:
            name = util.split()[1]
            media = " ".join(c[6:].strip() for c in chain if c.startswith("@media"))
            sizes = [v + (f" {media}" if media else "") for p, v, *_ in decls if p == "font-size"]
            utilities.setdefault(name, {"font-size": []})["font-size"] += sizes
        if chain and chain[-1].startswith("@font-face"):
            fams = [families(v)[0] for p, v, *_ in decls if p == "font-family" and families(v)]
            faces += fams
            src = re.search(r"url\(\s*[\"']?([^\"')\s]+)", next((v for p, v, *_ in decls if p == "src"), ""))
            if fams and src:
                face_rules.append({"family": fams[0], "src": src.group(1),
                                   "style": next((v for p, v, *_ in decls if p == "font-style"), "normal"),
                                   "weight": next((v for p, v, *_ in decls if p == "font-weight"), "400")})
            spans += [(a, b) for p, v, line, a, b in decls if p == "font-family"]  # a definition, not a use
            utility_spans += [(a, b) for p, v, line, a, b in decls if p == "font-family"]
        theme = any(c.startswith("@theme") for c in chain)
        if not chain or chain[-1].startswith("@"):
            targets = [(context_of(chain), (0, 0, 0))]
        else:
            targets = [(context_of(chain[:-1] + (sel,)), specificity(sel)) for sel in split_selectors(chain[-1])]
        targets = [(c, spec) for c, spec in targets if c is not None]
        for prop, value, line, a, b in decls:
            if prop == "font-family" and targets and chain and not chain[-1].startswith("@"):
                imp = bool(re.search(r"!\s*important\s*$", value, re.I))
                val = re.sub(r"\s*!\s*important\s*$", "", value, flags=re.I)
                page_fonts += [(c, (imp, spec, a - len(css) if theme else a), val, line) for c, spec in targets]
            if not prop.startswith("--") or not targets:
                continue
            if (a, b) not in spans:
                spans.append((a, b))
            important = bool(re.search(r"!\s*important\s*$", value, re.I))
            value = re.sub(r"\s*!\s*important\s*$", "", value, flags=re.I)
            order = a - len(css) if theme else a
            for c, spec in targets:
                tokens.setdefault(prop[2:], {"decls": []})["decls"].append((c, value, line, order, important, spec, (a, b)))
    # A class that redefines at least 3 base tokens is a theme variant of the site (a context, like a brand); a class
    # that does not holds a component's own variables, which stay in the text as values outside the tokens.
    base_names = {n for n, t in tokens.items() if any(d[0] == "base" for d in t["decls"])}
    provisional = {d[0].split("/")[0] for t in tokens.values() for d in t["decls"] if d[0].startswith("~")}
    keep = {v for v in provisional
            if len({n for n, t in tokens.items() for d in t["decls"] if d[0].split("/")[0] == v} & base_names) >= 3}
    for name in list(tokens):
        decls = []
        for d in tokens[name]["decls"]:
            root = d[0].split("/")[0]
            if root.startswith("~"):
                if root not in keep:
                    continue
                d = (d[0][1:],) + d[1:]
            decls.append(d)
        if decls:
            tokens[name]["decls"] = decls
        else:
            del tokens[name]
    kept = {d[6] for t in tokens.values() for d in t["decls"]}
    spans = [sp for sp in spans if sp in kept or sp in utility_spans]
    for t in tokens.values():
        t["decl"] = {}
        for c, value, line, order, important, spec, _ in t["decls"]:
            key = (important, spec, order)
            if c not in t["decl"] or key > t["decl"][c][2]:
                t["decl"][c] = (value, line, key)
    fonts = {"families": faces, "rules": face_rules, "page": []}
    for c, key, value, line in page_fonts:
        root = c.split("/")[0]
        if root.startswith("~"):
            if root not in keep:
                continue
            c = c[1:]
        fonts["page"].append((c, key, value, line))
    return tokens, utilities, fonts, blank(css, spans)


def resolver(tokens: dict, ctx: str):
    """raw(name) -> the value an element in ctx gets: of the declarations that reach it, the cascade's winner
    (!important first, then specificity, then the later one)."""
    reach = applies(ctx)

    def raw(name: str):
        t = tokens.get(name.lstrip("-"))
        if not t:
            return None
        found = [(important, spec, order, value) for c, value, _, order, important, spec, _ in t["decls"] if c in reach]
        return max(found)[3] if found else None
    return raw


def calc_dimension(value: str, raw, depth=0):
    """A dimension (number, unit) from a value: 0.5rem, 16px, calc(var(--radius) * 0.6); None when it is not one."""
    if depth > 10:
        return None
    v = value.strip()
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)", v)
    if m:
        r = raw(m.group(1))
        return calc_dimension(r, raw, depth + 1) if r else None
    m = DIMENSION_RE.match(v)
    if m:
        return float(m.group(1)), m.group(2) or ""
    m = re.fullmatch(r"calc\((.*)\)", v, re.S)
    if not m:
        return None
    unit, expr = None, m.group(1)

    def sub(mm):
        nonlocal unit
        d = calc_dimension(mm.group(0), raw, depth + 1)
        if not d:
            raise ValueError
        if d[1]:
            if unit and unit != d[1]:
                raise ValueError
            unit = d[1]
        return repr(d[0])
    try:
        expr = re.sub(r"var\([^()]*\)|-?\d*\.?\d+(?:px|rem|em|%)", sub, expr)
        return arith(ast.parse(expr.strip(), mode="eval").body), unit or ""
    except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
        return None


def arith(node) -> float:
    """The value of a parsed expression of numbers and + - * / only; anything else raises ValueError."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = arith(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a, b = arith(node.left), arith(node.right)
        return {ast.Add: a + b, ast.Sub: a - b, ast.Mult: a * b}.get(type(node.op)) if not isinstance(node.op, ast.Div) \
            else a / b
    raise ValueError("not arithmetic")


def resolve_vars(value: str, raw, depth: int = 0) -> str:
    """value with each var(--x) and var(--x, fallback) replaced by the variable's value where it is set (raw), else its
    fallback, resolved the same way. Parentheses and commas inside quotes count as text. A cycle stops at depth 10."""
    if depth > 10 or "var(" not in value:
        return value
    out, i = [], 0
    while (j := value.find("var(", i)) >= 0:
        k, level, quote = j + 4, 1, None
        while k < len(value) and level:
            ch = value[k]
            if quote:
                if ch == "\\":
                    k += 1
                elif ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "(":
                level += 1
            elif ch == ")":
                level -= 1
            k += 1
        if level:  # unbalanced: leave the rest as it is
            break
        name, _, fallback = value[j + 4: k - 1].partition(",")
        got = raw(name.strip())
        out += [value[i:j], resolve_vars(got if got else fallback.strip(), raw, depth + 1)]
        i = k
    return "".join(out) + value[i:]


def typed(name: str, raw_value: str, raw) -> dict:
    """The DTCG type and value of one token in one context."""
    if name.startswith("font-") and not name.startswith(("font-size", "font-weight")) or (
            "," in raw_value and any(f.lower() in GENERIC_FONTS for f in families(raw_value))):
        return {"type": "fontFamily", "families": families(resolve_vars(raw_value, raw))}
    col = C.parse(raw_value, raw)
    if col is not None:
        return {"type": "color", "rgba": [round(x, 5) for x in col], "hex": C.hex(col)}
    d = calc_dimension(raw_value, raw)
    if d is not None and (d[1] or d[0] == 0):
        return {"type": "dimension", "value": round(d[0], 4), "unit": d[1] or "px"}
    return {"type": "other"}


# ---------- scanning the code --------------------------------------------------------------------------------

def line_of(text: str, i: int) -> int:
    return text.count("\n", 0, i) + 1


def utility_map(tokens: dict, utilities: dict) -> dict:
    """Class name -> (token, role), for the utilities Tailwind makes from theme variables, and @utility names. The
    role is "text" or "bg" for colour utilities that set text or background colour, else None."""
    out = {}
    for name in tokens:
        if name.startswith("color-"):
            for p in COLOR_PREFIXES.replace("border-[trblxyse]", "border-t|border-r|border-b|border-l|border-x|"
                                            "border-y|border-s|border-e").split("|"):
                out[f"{p}-{name[6:]}"] = (name, {"text": "text", "bg": "bg"}.get(p))
        elif name.startswith("font-") and not name.startswith(("font-size", "font-weight")):
            out[name] = (name, None)
        elif name.startswith("radius-"):
            for p in ("rounded", "rounded-t", "rounded-r", "rounded-b", "rounded-l", "rounded-tl", "rounded-tr",
                      "rounded-br", "rounded-bl", "rounded-s", "rounded-e"):
                out[f"{p}-{name[7:]}"] = (name, None)
        elif name.startswith("shadow-"):
            out[name] = (name, None)
        elif name.startswith("text-") and not name.endswith(("--line-height", "--letter-spacing")):
            out[name] = (name, None)
    for u in utilities:
        out[u] = ("@utility " + u, None)
    return out


def literal_colors(expr: str) -> list[str]:
    """Colours written as literals inside an expression that also holds var(): hex, colour functions without var()
    and named colours. var() parts are tokens, so they are left out."""
    spans, i = [], 0
    while True:
        i = expr.lower().find("var(", i)
        if i < 0:
            break
        end = C.call_span(expr, i)
        spans.append((i, end if end > 0 else len(expr)))
        i = spans[-1][1]
    rest = blank(expr, spans)
    out = [C.hex(C.parse(m.group(0))) for m in C.HEX_RE.finditer(rest)]
    for m in C.FUNC_RE.finditer(rest):
        if m.group(0).lower().startswith("color-mix"):
            continue
        end = C.call_span(rest, m.start())
        col = C.parse(rest[m.start():end]) if end > 0 else None
        if col is not None:
            out.append(C.hex(col))
    for w in re.finditer(r"(?<![\w#-])([a-zA-Z]+)(?![\w(-])", rest):
        name = w.group(1).lower()
        if name in C.NAMED and name not in NOT_COLORS:
            out.append(C.hex(C.parse(name)))
    return out


def opacity(mod: str | None) -> float:
    """A Tailwind opacity modifier as a fraction: /50 -> 0.5, /[0.37] -> 0.37, /[37%] -> 0.37; none -> 1."""
    if not mod:
        return 1.0
    m = re.fullmatch(r"\[?(\d*\.?\d+)(%)?\]?", mod)
    if not m:
        return 1.0
    v = float(m.group(1))
    return max(0.0, min(1.0, v / 100 if m.group(2) or (not mod.startswith("[") and v > 1) else v))


def var_role(text: str, pos: int) -> str | None:
    """text or bg when the var() at pos is the value of a text-colour or background property."""
    line = text[text.rfind("\n", 0, pos) + 1:pos]
    m = re.search(r"([\w-]+)\s*:\s*[\"'`]?[^:;{}]*$", line)
    prop = m.group(1).lower() if m else ""
    if prop in ("color", "fill", "-webkit-text-fill-color", "caret-color"):
        return "text"
    if prop in ("background", "background-color", "backgroundcolor"):
        return "bg"
    return None


def class_regions(text: str, js: bool) -> list[tuple[int, int]]:
    """Where class names can stand: string literals in code and markup, @apply statements in CSS. A utility name
    elsewhere (a CSS property called display, a word in prose) is not a use."""
    if js:
        pat = r"\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`"
    else:
        pat = r"@apply\b[^;}]*|\bclass(?:Name)?\s*=\s*(?:\"[^\"]*\"|'[^']*')"
    return [m.span() for m in re.finditer(pat, text)]


def scan(text: str, js: bool, umap: dict, theme_names: set):
    """Every token use and every value outside the tokens in one file's text (comments and token declarations
    already blanked). Returns (token_uses, offtoken) as lists of (offset, ...)."""
    uses, off, taken = [], [], []
    regions = class_regions(text, js)

    def free(a, b):
        return not any(x <= a and b <= y for x, y in taken)

    def in_class(a):
        return any(x <= a < y for x, y in regions)

    for m in ARBITRARY_RE.finditer(text):
        prefix, val = m.group(1), m.group(2).replace("_", " ")
        taken.append(m.span())
        role = {"text": "text", "bg": "bg"}.get(prefix)
        vm = re.fullmatch(r"(?:color:)?var\(\s*--([\w-]+)\s*(?:,[^)]*)?\)", val)
        if vm:
            uses.append((m.start(), vm.group(1), role))
        elif prefix == "font":
            off.append((m.start(), "font", val.strip("\"'"), "arbitrary"))
        elif prefix.startswith("rounded"):
            off.append((m.start(), "dimension", val, "arbitrary"))
        else:
            inner = re.sub(r"^color:", "", val)
            col = C.parse(inner)
            if col is not None:
                off.append((m.start(), "color", C.hex(col), "arbitrary"))
            for vm2 in re.finditer(r"var\(\s*--([\w-]+)", inner):
                uses.append((m.start(), vm2.group(1), role))
            if col is not None:
                pass
            elif re.search(r"#|\(|^[a-zA-Z]+$", inner) and (literal_colors(inner) or "var(" not in inner):
                found = literal_colors(inner)
                off += [(m.start(), "color", v, "arbitrary") for v in found] or (
                    [(m.start(), "color", "unresolved arbitrary value", "arbitrary")] if re.search(r"#|\(", inner) else [])
            elif prefix == "text" and DIMENSION_RE.match(inner.strip()):
                off.append((m.start(), "dimension", val, "arbitrary"))
    for m in re.finditer(r"var\(\s*--([\w-]+)", text):
        if free(m.start(), m.end()):
            uses.append((m.start(), m.group(1), var_role(text, m.start())))
    for m in re.finditer(CLASS_EDGE_L + VARIANTS + r"(-?[a-z][a-z0-9-]*)(?:/([\w.\[\]%]+))?" + CLASS_EDGE_R, text):
        word = m.group(1).lstrip("-")
        if word in umap and free(*m.span()) and in_class(m.start()):
            name, role = umap[word]
            alpha = opacity(m.group(2))
            uses.append((m.start(), name, f"{role}@{alpha:g}" if role and alpha < 1 else role))
            taken.append(m.span())
    for m in PALETTE_RE.finditer(text):
        if not free(*m.span()) or not in_class(m.start()):
            continue
        name = f"{m.group(1)}-{m.group(2)}" if m.group(1) else m.group(3)
        if f"color-{name}" in theme_names:
            continue
        val = C.hex(C.parse(name)) if m.group(3) else f"tailwind:{name}"
        off.append((m.start(), "color", val, "palette class"))
        taken.append(m.span())
    for m in C.FUNC_RE.finditer(text):
        if not free(m.start(), m.end()):
            continue
        end = C.call_span(text, m.start())
        if end < 0:
            continue
        body = text[m.start():end]
        col = C.parse(body)
        taken.append((m.start(), end))
        if col is not None:
            off.append((m.start(), "color", C.hex(col), "function"))
            continue
        found = literal_colors(body)
        if found:
            off += [(m.start(), "color", v, "function") for v in found]
        elif "var(" not in body:  # a colour function the scan cannot read: named, never copied
            off.append((m.start(), "color", f"unresolved {m.group(0)[:-1].lower()}()", "function"))
    for m in C.HEX_RE.finditer(text):
        a = m.start()
        if not free(a, m.end()):
            continue
        prev = text[a - 1] if a else " "
        if prev.isalnum() or prev in "&/.-_#?":
            continue
        line_start = text.rfind("\n", 0, a) + 1
        before = text[line_start:a]
        if ATTR_VALUE.search(before) or URL_OPEN.search(before):
            continue
        if m.group(0)[1:].isdigit() and len(m.group(0)) <= 5 and not re.search(r"[:(\[,=]\s*[\"'`]?$", before):
            continue  # "#123" or "#2024" in a sentence is a number, not a colour
        off.append((a, "color", C.hex(C.parse(m.group(0))), "hex"))
    for m in re.finditer(rf"(?<![\w-])(?:{COLOR_PROPS})\s*:\s*[\"'`]?([^;{{}}\n\"'`]*)", text):
        value = re.sub(r"url\([^)]*\)", "", m.group(1))
        for w in re.finditer(r"(?<![\w#-])([a-zA-Z]+)(?![\w-])", value):
            name = w.group(1).lower()
            if name in C.NAMED and name not in NOT_COLORS:
                pos = m.start(1) + w.start()
                if free(pos, pos + len(name)):
                    off.append((pos, "color", C.hex(C.parse(name)), "named"))
    return uses, off


# One family in a list: quoted, a var() with its fallback, or a bare name. The list needs commas between families,
# so a quote that ends an HTML attribute (style="font-family: Arial" data-x="...") ends the match.
FAMILY = r"(?:\"[^\"\n]{1,60}\"|'[^'\n]{1,60}'|var\([^()]{0,80}\)|-?[A-Za-z][A-Za-z0-9 _-]{0,59})"
FONT_SIZE = (r"(?:-?[\d.]+(?:px|rem|em|%|pt|vw|vh|ch|ex)|xx-small|x-small|small|medium|large|x-large|xx-large|"
             r"xxx-large|smaller|larger)")


def literal_families(value: str) -> list[str]:
    """The families a font-family value names itself: the literal ones and the fallbacks inside var()."""
    fallbacks = [m.group(1) for m in re.finditer(r"var\(\s*--[\w-]+\s*,\s*([^()]+)\)", value)]
    rest = re.sub(r"var\([^()]*\)", "", value)
    return [f for part in [rest, *fallbacks] for f in families(part) if f and not f.startswith("--")]


def shorthand_families(value: str) -> list[str]:
    """The families at the end of a font shorthand ("italic 700 16px/1.4 Inter, sans-serif")."""
    m = re.search(rf"(?:^|\s){FONT_SIZE}(?:\s*/\s*\S+)?\s+(.+)$", value.strip())
    return families(m.group(1)) if m and "var(" not in m.group(1) else []


def scan_fonts(text: str, js: bool):
    """Hard-coded font families (font-family, the font shorthand, fontFamily, next/font imports) as
    (offset, family, how)."""
    out = []
    for m in re.finditer(rf"(?<![\w-])font-family\s*:\s*({FAMILY}(?:\s*,\s*{FAMILY})*)", text):
        for f in literal_families(m.group(1)):
            out.append((m.start(), f, "font-family"))
    for m in re.finditer(r"(?<![\w-])font\s*:\s*[\"'`]?([^;{}\n\"'`]+)", text):
        for f in shorthand_families(m.group(1)):
            out.append((m.start(), f, "font shorthand"))
    if js:
        for m in re.finditer(r"fontFamily\s*:\s*([\"'`])(.+?)\1", text):
            for f in literal_families(m.group(2)):
                out.append((m.start(), f, "fontFamily"))
        for m in re.finditer(r"import\s*\{([^}]+)\}\s*from\s*[\"']next/font/google[\"']", text):
            for name in m.group(1).split(","):
                name = name.split(" as ")[0].strip()
                if name:
                    out.append((m.start(), name.replace("_", " "), "next/font"))
        if re.search(r"from\s*[\"']next/font/local[\"']", text):
            for m in re.finditer(r"(\w+)\s*=\s*localFont\(\s*\{(.*?)\}\s*\)", text, re.S):
                src = re.search(r"[\"'`]([^\"'`]+\.(?:woff2?|ttf|otf))[\"'`]", m.group(2))
                out.append((m.start(), font_stem(src.group(1)) if src else m.group(1), "next/font/local"))
    return out


# ---------- extract ------------------------------------------------------------------------------------------

def git_commit(root: Path) -> str | None:
    p = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() or None if p.returncode == 0 else None


def extract(site: Site) -> dict:
    cfg = site.get("tokens", {})
    token_file = site.file(cfg["file"])
    tokens, utilities, font_decls, token_text = read_tokens(token_file)
    faces = font_decls["families"]
    declared = {c for t in tokens.values() for c in t["decl"]} | {c for c, *_ in font_decls["page"]}
    brands = sorted({c.split("/")[0] for c in declared if c not in ("base", "dark")})
    contexts = ["base"] + (["dark"] if "dark" in declared else [])
    for b in brands:
        contexts += [b] + ([f"{b}/dark"] if "dark" in declared or f"{b}/dark" in declared else [])
    parent = {c: (None if c == "base" else "dark" if c.endswith("/dark") else "base") for c in contexts}
    for name, t in tokens.items():
        t["contexts"] = {}
        for ctx in contexts:
            raw = resolver(tokens, ctx)
            value = raw(name)
            if value is None:
                continue
            info = typed(name, value, raw)
            up = t["contexts"].get(parent[ctx]) if parent[ctx] else None
            moved = up is not None and (info.get("hex"), info.get("families"), info.get("value")) != (
                up.get("hex"), up.get("families"), up.get("value"))
            info.update({"css": value if info["type"] != "other" else None, "line": t["decl"].get(ctx, (None, None))[1],
                         "own": ctx in t["decl"] or moved})
            t["contexts"][ctx] = info
        base = t["contexts"].get("base") or next(iter(t["contexts"].values()))
        t["type"] = base["type"]
        m = re.fullmatch(r"var\(\s*--([\w-]+)\s*\)", (resolver(tokens, "base")(name) or "").strip())
        t["alias"] = m.group(1) if m and m.group(1) in tokens else None
        t["uses"], t["roles"] = [], set()
    theme_names = set(tokens)
    umap = utility_map(tokens, utilities)
    sources = site.files(cfg.get("sources", []), cfg.get("exclude", []))
    files = [(token_file, token_text, False)] + [
        (p, None, p.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".mdx"))
        for p in sources if p != token_file]
    off, font_uses, util_uses = {}, [], {}
    for path, text, js in files:
        if text is None:
            text = strip_comments(path.read_text(encoding="utf-8", errors="replace"), js)
        rel = site.rel(path)
        uses, found = scan(text, js, umap, theme_names)
        for pos, name, role in uses:
            where = f"{rel}:{line_of(text, pos)}"
            if name.startswith("@utility "):
                util_uses.setdefault(name[9:], []).append(where)
            elif name in tokens:
                tokens[name]["uses"].append(where)
                if role:
                    tokens[name]["roles"].add(role)
        for pos, kind, value, how in found:
            key = (kind, value)
            off.setdefault(key, {"kind": kind, "value": value, "how": set(), "uses": []})
            off[key]["how"].add(how)
            off[key]["uses"].append(f"{rel}:{line_of(text, pos)}")
        for pos, fam, how in scan_fonts(text, js):
            font_uses.append({"family": fam, "how": how, "where": f"{rel}:{line_of(text, pos)}"})

    # A theme alias (--color-x: var(--x)) is used through its class; the raw token gets those uses too.
    def root(name):
        seen = set()
        while tokens[name]["alias"] and name not in seen:
            seen.add(name)
            name = tokens[name]["alias"]
        return name
    for name, t in tokens.items():
        t["uses_all"] = list(t["uses"])
    for name, t in tokens.items():
        if t["alias"] and root(name) != name:
            tokens[root(name)]["uses_all"] += t["uses"]

    oneoffs = {k.lower(): v for k, v in (site.get("oneoffs") or {}).items()}
    token_colors = {}
    for name, t in tokens.items():
        for ctx, info in t["contexts"].items():
            if info["type"] == "color" and info["rgba"][3] >= 0.999:
                token_colors.setdefault(info["hex"], set()).add(name)
    offtoken = []
    for (kind, value), o in sorted(off.items(), key=lambda kv: (-len(kv[1]["uses"]), kv[0])):
        item = {"kind": kind, "value": value, "how": sorted(o["how"]), "uses": o["uses"],
                "oneoff": oneoffs.get(value.lower())}
        if kind == "color" and value.startswith("#"):
            col = C.parse(value)
            item["equals_token"] = sorted(token_colors.get(value, ()))
            if not item["equals_token"] and col[3] >= 0.999:
                near = sorted((C.delta_e(col, C.parse(h)), min(n, key=lambda x: (x.startswith("color-"), x)), h)
                              for h, n in token_colors.items())
                item["near_token"] = ({"token": near[0][1], "hex": near[0][2], "delta_e": round(near[0][0], 2)}
                                      if near and near[0][0] < 2 else None)
        offtoken.append(item)

    # Near-duplicate colours, the questions an owner can answer: two tokens of one context closer than CIEDE2000 2
    # (merge them?), and each hard-coded colour within 2 of a token (use the token?), against its nearest token only.
    near = []
    for ctx in contexts:
        vals = {}
        for name, t in tokens.items():
            info = t["contexts"].get(ctx)
            if info and info["type"] == "color" and info["rgba"][3] >= 0.999 and not t["alias"]:
                vals.setdefault(info["hex"], set()).add(f"--{name}")
        hexes = sorted(vals)
        for i, a in enumerate(hexes):
            for b in hexes[i + 1:]:
                d = C.delta_e(C.parse(a), C.parse(b))
                if d < 2:
                    near.append({"a": a, "b": b, "delta_e": round(d, 2), "context": ctx, "a_names": sorted(vals[a]),
                                 "b_names": sorted(vals[b])})
    for o in offtoken:
        if o["kind"] == "color" and o["value"].startswith("#") and len(o["value"]) == 7 and o.get("near_token"):
            nt = o["near_token"]
            near.append({"a": o["value"], "b": nt["hex"], "delta_e": nt["delta_e"], "context": None,
                         "a_names": [f"{o['value']} ({o['uses'][0]})"], "b_names": [f"--{nt['token']}"]})
    same = [{"value": h, "tokens": sorted({root(x) for x in n})} for h, n in sorted(token_colors.items())
            if len({root(x) for x in n}) > 1]

    # Fonts: token stacks, hard-coded families, @font-face, font files on disk, and what the docs name.
    token_fonts = {name: t["contexts"][next(iter(t["contexts"]))]["families"] for name, t in tokens.items()
                   if t["type"] == "fontFamily"}
    in_tokens = {norm_font(f) for fs in token_fonts.values() for f in fs}
    font_off = {}
    for u in font_uses:
        fam = u["family"]
        if norm_font(fam) and fam.lower() not in GENERIC_FONTS:
            font_off.setdefault(fam, {"family": fam, "how": set(), "uses": [], "in_tokens": norm_font(fam) in in_tokens,
                                      "oneoff": oneoffs.get(fam.lower())})
            font_off[fam]["how"].add(u["how"])
            font_off[fam]["uses"].append(u["where"])
    for o in offtoken:
        if o["kind"] == "font":
            for fam in families(o["value"]):
                if fam.lower() not in GENERIC_FONTS:
                    font_off.setdefault(fam, {"family": fam, "how": set(), "uses": [],
                                              "in_tokens": norm_font(fam) in in_tokens, "oneoff": oneoffs.get(fam.lower())})
                    font_off[fam]["how"].add("arbitrary")
                    font_off[fam]["uses"] += o["uses"]
    font_globs = cfg.get("fonts") or ["**/*.woff2", "**/*.woff", "**/*.ttf", "**/*.otf"]
    font_files = [site.rel(p) for p in site.files(font_globs) if p.suffix.lower() in (".woff2", ".woff", ".ttf", ".otf")]
    candidates = {norm_font(f): f for fs in token_fonts.values() for f in fs if f.lower() not in GENERIC_FONTS}
    candidates |= {norm_font(f): f for f in list(font_off) + faces}
    for ff in font_files:
        stem = font_stem(ff)
        if norm_font(stem):
            candidates.setdefault(norm_font(stem), stem)
    docs_mentions = {}
    for p in site.files(cfg.get("docs", [])):
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            low = norm_font(line)
            for key, name in candidates.items():
                if len(key) >= 4 and key in low:
                    docs_mentions.setdefault(name, []).append(f"{site.rel(p)}:{n}")

    def count(kind):
        return sum(len(t["uses"]) for t in tokens.values() if t["type"] == kind)  # each use once, at its alias
    color_off = sum(len(o["uses"]) for o in offtoken if o["kind"] == "color")
    color_named = sum(len(o["uses"]) for o in offtoken if o["kind"] == "color" and o["oneoff"])
    font_hard = sum(len(f["uses"]) for f in font_off.values())
    coverage = {
        "color_token_uses": count("color"), "color_offtoken_uses": color_off, "color_oneoff_uses": color_named,
        "color_in_tokens_pct": round(100 * count("color") / max(1, count("color") + color_off), 2),
        "color_unexplained_values": sorted({o["value"] for o in offtoken if o["kind"] == "color" and not o["oneoff"]}),
        "font_token_uses": count("fontFamily"), "font_hardcoded_uses": font_hard,
        "font_in_tokens_pct": round(100 * count("fontFamily") / max(1, count("fontFamily") + font_hard), 2),
        "font_unexplained": sorted(f for f, v in font_off.items() if not v["in_tokens"] and not v["oneoff"]),
    }
    for f in font_off.values():
        f["how"] = sorted(f["how"])
    # The font a page in each context gets: the font-family a context's own selector sets (the cascade's winner of
    # those that reach it), else the font-sans token there.
    page_font = {}
    for ctx in contexts:
        raw = resolver(tokens, ctx)
        found = [(key, value, line) for c, key, value, line in font_decls["page"] if c in applies(ctx)]
        value, line = (max(found)[1:]) if found else (raw("font-sans"), None)
        if value:
            fams = typed("font-page", value, raw)["families"]
            if fams:
                page_font[ctx] = {"families": fams, "line": line}
    return {
        "generated": date.today().isoformat(), "token_file": site.rel(token_file), "commit": git_commit(site.root),
        "contexts": contexts, "files_scanned": len(files),
        "tokens": {n: {**{k: t[k] for k in ("type", "alias", "contexts", "uses", "uses_all")}, "roles": sorted(t["roles"])}
                   for n, t in tokens.items()},
        "utilities": {u: {"font-size": v["font-size"], "uses": util_uses.get(u, [])} for u, v in utilities.items()},
        "offtoken": offtoken, "near_duplicates": near, "same_value": same,
        "fonts": {"tokens": token_fonts, "hardcoded": list(font_off.values()), "font_face": sorted(set(faces)),
                  "faces": font_decls["rules"], "page": page_font, "files": font_files, "docs": docs_mentions},
        "coverage": coverage,
    }


def dtcg(data: dict) -> dict:
    """design/tokens.json in the DTCG 2025.10 format: the base value as $value, the other contexts in $extensions."""
    out = {"$description": f"Generated by ex-designer tokens.py from {data['token_file']}"
                           f"{' at ' + data['commit'] if data['commit'] else ''} on {data['generated']}. "
                           "Never edit this file: edit the token file and extract again."}
    for name, t in sorted(data["tokens"].items()):
        if t["type"] not in ("color", "dimension", "fontFamily"):
            continue
        ctxs = t["contexts"]
        base_ctx = "base" if "base" in ctxs else next(iter(ctxs))
        b = ctxs[base_ctx]
        if t["alias"] and data["tokens"].get(t["alias"], {}).get("type") == t["type"]:
            value = "{" + t["alias"] + "}"
        elif t["type"] == "color":
            value = {"colorSpace": "srgb", "components": [round(x, 4) for x in b["rgba"][:3]], "alpha": round(b["rgba"][3], 4),
                     "hex": b["hex"][:7]}
        elif t["type"] == "dimension":
            value = {"value": b["value"], "unit": b["unit"] if b["unit"] in ("px", "rem") else "px"}
        else:
            value = b["families"]
        ext = {"css": b["css"], "context": base_ctx, "uses": len(t["uses_all"])}
        others = {c: {"css": i["css"], **({"hex": i["hex"]} if "hex" in i else {})} for c, i in ctxs.items()
                  if c != base_ctx and i["own"]}
        if others:
            ext["contexts"] = others
        out[name] = {"$type": t["type"], "$value": value, "$extensions": {"ex-designer": ext}}
    return out


# ---------- the design system page ---------------------------------------------------------------------------

COMPLETENESS = [
    ("error", r"destructive|error|danger"), ("focus", r"ring|focus"), ("disabled", r"disabled"),
    ("success", r"success|positive"), ("warning", r"warning|caution"), ("border", r"border|outline|divider"),
    ("muted text", r"muted|subtle|secondary-foreground|tertiary"), ("link", r"link"),
    ("surface", r"background|surface|card"), ("on-primary", r"primary-foreground|on-primary"),
]


def root_name(toks: dict, name: str) -> str:
    seen = set()
    while toks.get(name, {}).get("alias") and name not in seen:
        seen.add(name)
        name = toks[name]["alias"]
    return name


def contrast_pairs(data: dict, ctx: str, all_fills: bool = False) -> list[dict]:
    """Text/background token pairs in one context, with their WCAG ratio ("ratio_exact" unrounded, for checks).
    Named pairs: X-foreground on X and on background, foreground on background. Used pairs ("used": True): every
    token the code uses as a text colour, at every opacity it is used with (text-foreground/50), on every token it
    uses as a background: the surfaces only for the page, every fill (accent, primary) with all_fills, for checks.
    A superset of what renders, so a change that makes such a pair unreadable is caught."""
    toks = data["tokens"]

    def col(n, alpha=1.0):
        i = toks.get(n, {}).get("contexts", {}).get(ctx)
        if not i or i["type"] != "color":
            return None
        r, g, b, a = i["rgba"]
        return (r, g, b, a * alpha)
    pairs = [("foreground", "background", 1.0)]
    for n in sorted(toks):
        if n.endswith("-foreground") and not n.startswith("color-"):
            bg = n[: -len("-foreground")]
            pairs += [(n, b, 1.0) for b in ([bg] if bg in toks else []) + (["background"] if bg != "background" else [])]
    named = len(pairs)
    texts, fills = set(), set()
    for n, t in toks.items():
        for r in t.get("roles", []):
            kind, _, alpha = r.partition("@")
            if kind == "text":
                texts.add((root_name(toks, n), float(alpha or 1)))
            elif kind == "bg":
                fills.add(root_name(toks, n))
    bgs = sorted(b for b in fills if all_fills or re.search(SURFACE, b))
    pairs += [(fg, bg, a) for fg, a in sorted(texts) for bg in bgs if fg != bg]
    out, seen = [], set()
    base = col("background") or (1.0, 1.0, 1.0, 1.0)
    for i, (fg, bg, a) in enumerate(pairs):
        if (fg, bg, a) in seen or not col(fg) or not col(bg):
            continue
        seen.add((fg, bg, a))
        r = C.contrast(col(fg, a), col(bg), base)
        out.append({"fg": fg if a == 1 else f"{fg}/{round(a * 100)}", "bg": bg, "ratio": round(r, 2),
                    "ratio_exact": r, "used": i >= named})
    return out


DEFAULT_LABELS = {k: k for k in (
    "title", "intro", "generated_from", "commit", "date", "nav", "colours", "colours_intro", "type", "type_intro",
    "families", "scale", "specimen", "shape", "shape_intro", "contrast", "contrast_intro", "passes", "fails",
    "gap_missing", "context_base", "context_dark", "role", "g_surfaces", "g_text", "g_brand", "g_status", "g_lines",
    "g_charts", "g_other", "e_surfaces", "e_text", "e_brand", "e_status", "e_lines", "e_charts", "e_other",
    "q_near_duplicate", "q_same_value", "q_docs_font", "q_font_files", "q_unexplained_color", "q_unexplained_font",
    "band_background", "band_text", "band_muted", "band_accent", "font_file", "font_stack", "defined_at")}

# Token groups, by the role a name tells (shadcn, Tailwind and most hand-made token files name roles this way).
GROUPS = [
    ("text", r"(^|-)foreground$|^text($|-)|^ink$"),
    ("status", r"destructive|error|danger|success|warning|caution|info|unresolved|^route-|^signal-(high|med|pass)"),
    ("lines", r"border|^input$|^ring$|ring$|outline|divider|stroke"),
    ("charts", r"^chart-"),
    ("brand", r"^primary$|^signal|^brand|^cobalt|^highlight"),
    ("surfaces", r"background|^card$|^popover$|^muted$|^secondary$|^accent$|^sidebar|^paper|^surface|^ink-|^canvas|^panel"),
]


def group_of(name: str) -> str:
    return next((g for g, pat in GROUPS if re.search(pat, name)), "other")


SAFE_SIZE = re.compile(r"(?:clamp|min|max|calc)\([\w\s.,%+*/()-]*\)|[\d.]+(?:px|rem|em|%|vw|vh|ch|ex)", re.I)
FONT_STYLE = re.compile(r"normal|italic|oblique(?:\s+-?\d+(?:\.\d+)?deg){0,2}", re.I)
FONT_WEIGHT = re.compile(r"normal|bold|\d{1,4}(?:\.\d+)?(?:\s+\d{1,4}(?:\.\d+)?)?", re.I)


def css_family(name: str) -> str:
    """A font family as CSS: a generic keyword as it is, any other name as a quoted and escaped string, so a name from
    a site's CSS cannot add a declaration to the page."""
    if name.lower() in GENERIC_FONTS:
        return name.lower()
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    return '"' + re.sub(r'[\\"]', lambda m: "\\" + m.group(0), name) + '"'


def css_stack(fams) -> str:
    return ", ".join(css_family(f) for f in fams)


def face_descriptors(style: str, weight: str) -> tuple[str, str]:
    """An @font-face rule's font-style and font-weight when they are valid CSS, else the defaults: the page writes
    them into its own stylesheet."""
    style, weight = style.strip(), weight.strip()
    return (style if FONT_STYLE.fullmatch(style) else "normal", weight if FONT_WEIGHT.fullmatch(weight) else "400")


def shown_contexts(site: Site, data: dict) -> list:
    """The contexts the owner named in site.json (one per brand), else every context."""
    names = site.get("context_names") or {}
    return [c for c in names if c in data["contexts"]] or data["contexts"]


def page(site: Site, design: Path, labels: dict, roles: dict | None = None, lang: str = "en") -> str:
    """design/system.html: the site's design system as a document a new maintainer reads once and keeps open. Each
    section opens like a brand book page, the brands side by side and large, and then lists every value in a table.
    Only the system itself: values outside the tokens, unused tokens and the coverage go to the audit report, and the
    owner's questions are asked in chat (`questions`)."""
    data = json.loads((design / "usage.json").read_text())
    L = {**DEFAULT_LABELS, **labels}
    e = html.escape
    toks = data["tokens"]
    names = site.get("context_names") or {}
    shown = shown_contexts(site, data)
    roles = roles or {}
    fonts = data["fonts"]

    def ctx_name(ctx):
        if ctx in names:
            return names[ctx]
        if ctx == "base":
            return L["context_base"]
        if ctx == "dark":
            return L["context_dark"]
        return ctx.replace("/dark", " + " + L["context_dark"])

    def role_of(n):
        r = roles.get(n)
        return (r.get(lang) or r.get("en")) if isinstance(r, dict) else r

    def hex_in(n, c):
        i = toks.get(n, {}).get("contexts", {}).get(c)
        return i["hex"] if i and i["type"] == "color" else None

    def ink_on(hexv):  # black or white text, whichever reads better on the colour
        col = C.parse(hexv)
        return "#ffffff" if C.contrast((1, 1, 1, 1), col) >= C.contrast((0, 0, 0, 1), col) else "#14161b"

    def chip(hexv):
        return f"<span class=chip style='--c:{e(hexv)}'></span>"

    def stack_of(c):
        return (fonts.get("page", {}).get(c) or {}).get("families") or []

    raw = sorted((n for n, t in toks.items() if t["type"] == "color" and not n.startswith("color-")),
                 key=lambda n: (-len(toks[n]["uses_all"]), n))  # the most used first in each group
    by_group = {}
    for n in raw:
        if toks[n]["uses_all"]:  # a colour no code uses is not part of the system (the audit lists it)
            by_group.setdefault(group_of(n), []).append(n)
    order = [g for g in ("surfaces", "text", "brand", "status", "lines", "charts", "other") if g in by_group]

    def key_colours(c):
        """The colours a brand is recognised by: page, text, quiet text and its accent (the most used brand colour
        that is opaque and differs from the others)."""
        picks = [(n, k) for n, k in (("background", "band_background"), ("foreground", "band_text"),
                                     ("muted-foreground", "band_muted")) if hex_in(n, c)]
        seen = {hex_in(n, c) for n, _ in picks}
        for n in sorted((n for n in by_group.get("brand", [])), key=lambda n: -len(toks[n]["uses_all"])):
            h = hex_in(n, c)
            if h and len(h) == 7 and h not in seen:
                picks.append((n, "band_accent"))
                break
        return picks

    # The brands' own font files, embedded so the specimens show the real typeface.
    used_fams = {norm_font(f) for c in shown for f in stack_of(c)}
    face_css, face_file = [], {}
    for f in fonts.get("faces", []):
        if norm_font(f["family"]) not in used_fams or not re.fullmatch(r"[\w .-]{1,60}", f["family"]):
            continue
        url = f["src"].split("?")[0].split("#")[0]
        if re.match(r"[a-z][\w+.-]*:", url, re.I):  # http:, data: and other schemes: not a file of the site
            continue
        token_dir = (site.root / data["token_file"]).parent
        paths = ((site.root / "public" / url.lstrip("/"), site.root / url.lstrip("/")) if url.startswith("/")
                 else (token_dir / url,))
        for p in paths:
            p = p.resolve()
            ext = p.suffix.lower()[1:]
            if (p.is_relative_to(site.root) and ext in ("woff2", "woff", "ttf", "otf") and p.is_file()
                    and p.stat().st_size < 3_000_000 and site.readable(p)):
                fmt = {"ttf": "truetype", "otf": "opentype"}.get(ext, ext)
                style, weight = face_descriptors(f["style"], f["weight"])
                face_css.append(f"@font-face{{font-family:{css_family(f['family'])};src:url(data:font/{ext};base64,"
                                f"{base64.b64encode(p.read_bytes()).decode()}) format(\"{fmt}\");font-style:{style};"
                                f"font-weight:{weight};font-display:block}}")
                face_file.setdefault(norm_font(f["family"]), p.name)
                break

    sections = [("colours", L["colours"]), ("type", L["type"]), ("shape", L["shape"]), ("contrast", L["contrast"])]
    out = [f"<!doctype html><html lang={'fi' if lang == 'fi' else 'en'}><head><meta charset=utf-8><meta name=viewport "
           f"content='width=device-width,initial-scale=1'><title>{e(L['title'])}</title><style>{''.join(face_css)}"
           f"{PAGE_CSS}</style></head><body>",
           f"<nav class=bar aria-label='{e(L['nav'])}'><ol>"
           + "".join(f"<li><a href='#{k}'>{e(t)}</a></li>" for k, t in sections) + "</ol></nav><div class=wrap>",
           "<header class=cover>",
           f"<p class=brands>{''.join(f'<span>{e(ctx_name(c))}</span>' for c in shown)}</p>",
           f"<h1>{e(L['title'])}</h1><p class=lede>{e(L['intro'])}</p>",
           f"<dl class=source><div><dt>{e(L['generated_from'])}</dt><dd>{e(data['token_file'])}</dd></div>"
           + (f"<div><dt>{e(L['commit'])}</dt><dd>{e(data['commit'])}</dd></div>" if data["commit"] else "")
           + f"<div><dt>{e(L['date'])}</dt><dd>{e(data['generated'])}</dd></div></dl></header><main>"]

    # Colours: the brands' key colours as bands, then every colour by role, one column per brand.
    out.append(f"<section id=colours><div class=opener><div><h2>{e(L['colours'])}</h2><p>{e(L['colours_intro'])}</p>"
               "</div><div class=brand-cols>")
    for c in shown:
        out.append(f"<figure class=brand-col><figcaption>{e(ctx_name(c))}</figcaption><div class=stack>")
        for n, k in key_colours(c):
            h = hex_in(n, c)
            out.append(f"<div class=band style='background:{e(h)};color:{ink_on(h)}'><b>{e(role_of(n) or L[k])}</b>"
                       f"<span>{e(h.upper())}<code>--{e(n)}</code></span></div>")
        out.append("</div></figure>")
    out.append("</div></div>")
    for g in order:
        out.append(f"<div class=group><h3>{e(L['g_' + g])}</h3><p class=note>{e(L['e_' + g])}</p>"
                   f"<table class=palette><thead><tr><th scope=col>{e(L['role'])}</th>"
                   + "".join(f"<th scope=col>{e(ctx_name(c))}</th>" for c in shown) + "</tr></thead><tbody>")
        for n in by_group[g]:
            cells = []
            for c in shown:
                h = hex_in(n, c)
                cells.append(f"<td data-label='{e(ctx_name(c))}'>{chip(h)}<span class=hex>{e(h.upper())}</span></td>"
                             if h else f"<td class=empty data-label='{e(ctx_name(c))}'>–</td>")
            role = role_of(n)
            out.append(f"<tr><th scope=row>{f'<span class=role>{e(role)}</span>' if role else ''}"
                       f"<code>--{e(n)}</code></th>{''.join(cells)}</tr>")
        out.append("</tbody></table></div>")
    out.append("</section>")

    # Type: each brand's page font large, then the other font families and the size steps.
    out.append(f"<section id=type><div class=opener><div><h2>{e(L['type'])}</h2><p>{e(L['type_intro'])}</p></div>"
               "<div class=brand-cols>")
    for c in shown:
        fams = stack_of(c)
        if not fams:
            continue
        line = fonts["page"][c].get("line")
        file = face_file.get(norm_font(fams[0]))
        out.append(f"<figure class=face><figcaption>{e(ctx_name(c))}</figcaption><p class=aa style='font-family:"
                   f"{e(css_stack(fams))}'>Aa</p><p class=fam style='font-family:{e(css_stack(fams))}'>{e(fams[0])}</p>"
                   "<dl class=facts>"
                   + (f"<div><dt>{e(L['font_file'])}</dt><dd>{e(file)}</dd></div>" if file else "")
                   + f"<div><dt>{e(L['font_stack'])}</dt><dd>{e(', '.join(fams))}</dd></div>"
                   + (f"<div><dt>{e(L['defined_at'])}</dt><dd>{e(data['token_file'])}:{line}</dd></div>" if line else "")
                   + "</dl></figure>")
    out.append("</div></div>")
    page_stacks = {css_stack(stack_of(c)) for c in shown}
    others = []
    for n, fs in sorted(fonts["tokens"].items(), key=lambda kv: -len(toks[kv[0]]["uses_all"])):
        stack = css_stack(fs)
        if stack not in page_stacks and stack not in {s for s, _, _ in others} and toks[n]["uses_all"]:
            others.append((stack, n, fs))
    if others:
        out.append(f"<h3>{e(L['families'])}</h3><div class=families>")
        for stack, n, fs in others:
            out.append(f"<figure class=family><p class=sample style='font-family:{e(stack)}'>{e(L['specimen'])}</p>"
                       f"<figcaption><b>{e(fs[0] if fs else n)}</b><code>--{e(n)}</code></figcaption></figure>")
        out.append("</div>")
    def raw_base(name):
        ctxs = toks.get(name.lstrip("-"), {}).get("contexts") or {}
        i = ctxs.get("base") or next(iter(ctxs.values()), None)
        return i.get("css") if i else None

    def split_size(s):
        """'var(--x) (width >= 48rem)' -> ('var(--x)', '(width >= 48rem)'): the media part a utility size carries
        starts at the first ' (' outside the value's own parentheses."""
        level = 0
        for k, ch in enumerate(s):
            if ch == "(":
                if level == 0 and k and s[k - 1] == " ":
                    return s[:k - 1].strip(), s[k:]
                level += 1
            elif ch == ")":
                level -= 1
        return s.strip(), ""

    def size_of(value):
        """(px, css) of a size: px through its tokens and var() fallbacks; css the size as the specimen's font-size,
        also for a fluid clamp()/min()/max()/calc() of lengths; None where neither holds."""
        v = resolve_vars(value, raw_base).strip()
        d = DIMENSION_RE.match(v)
        if d and d.group(2) in ("px", "rem", "em"):
            px = float(d.group(1)) * (16 if d.group(2) in ("rem", "em") else 1)
            return px, f"{px:g}px"
        return None, (v if "var(" not in v and SAFE_SIZE.fullmatch(v) else None)

    steps = {u: v for u, v in data["utilities"].items() if v["font-size"] and v["uses"]}
    first = css_stack(stack_of(shown[0])) if shown and stack_of(shown[0]) else "inherit"
    if steps:
        out.append(f"<h3>{e(L['scale'])}</h3><ol class=scale>")
        rows = {}
        for u, v in steps.items():
            entries = []
            for s in v["font-size"]:
                value, media = split_size(s)
                m = re.search(r"\(\s*(?:width\s*>=?|min-width\s*:)\s*([\d.]+\w*)\s*\)", media)
                entries.append((media, rem(m.group(1)) * 16 if m else None, value, *size_of(value)))
            rows[u] = entries
        for u, entries in sorted(rows.items(), key=lambda kv: -max(x[3] or 0 for x in kv[1])):
            media, _, value, px, css = next((x for x in entries if not x[0]), entries[0])
            wide = sorted((bp, w_px) for m, bp, _, w_px, _ in entries if m and bp and w_px)
            steps_px = [f"{px:g} px" if px else value] + [f"≥ {w:g} px: {r:g} px" for w, r in wide]
            size_css = f"font-size:{css};" if css else ""
            out.append(f"<li><p class=step style='{e(size_css)}font-family:{e(first)}'>{e(L['specimen'])}</p>"
                       f"<p class=meta><code>.{e(u)}</code>{''.join(f'<span>{e(x)}</span>' for x in steps_px)}</p></li>")
        out.append("</ol>")
    out.append("</section>")

    # Shape: corner radii as boxes.
    radii = sorted(((n, t["contexts"].get("base") or next(iter(t["contexts"].values()))) for n, t in toks.items()
                    if t["type"] == "dimension" and n.startswith("radius") and t["uses_all"]),
                   key=lambda x: x[1]["value"])
    out.append(f"<section id=shape><div class=opener><div><h2>{e(L['shape'])}</h2><p>{e(L['shape_intro'])}</p></div>"
               "<div class=radii>")
    for n, i in radii:
        px = f" ({i['value'] * 16:g} px)" if i["unit"] == "rem" else ""
        out.append(f"<figure><span class=box style='border-radius:{i['value']}{i['unit']}'></span><figcaption>"
                   f"<code>--{e(n)}</code><span class=quiet>{i['value']:g} {e(i['unit'])}{px}</span></figcaption></figure>")
    out.append("</div></div></section>")

    # Contrast: each text colour the code uses, on the surface it is named for and on the page (a surface's own text
    # also sits on the page; a fill's text, like primary-foreground, only on its fill). Tokens no code uses are left
    # out: their pairs never render. (verify.py checks the wider set of contrast_pairs.)
    def doc_pairs(c):
        base = tuple(toks["background"]["contexts"][c]["rgba"]) if hex_in("background", c) else (1.0, 1.0, 1.0, 1.0)
        rows = []
        for t in sorted(toks, key=lambda n: (n != "foreground", -len(toks[n]["uses_all"]), n)):
            if (not (t == "foreground" or t.endswith("-foreground")) or t.startswith("color-")  # @theme aliases
                    or not toks[t]["uses_all"] or not hex_in(t, c)):
                continue
            x = "background" if t == "foreground" else t[: -len("-foreground")]
            bgs = [x] if x in toks and toks[x]["uses_all"] and hex_in(x, c) else []
            if x != "background" and (x not in toks or group_of(x) == "surfaces") and hex_in("background", c):
                bgs.append("background")
            for b in bgs:
                r = C.contrast(tuple(toks[t]["contexts"][c]["rgba"]), tuple(toks[b]["contexts"][c]["rgba"]), base)
                rows.append({"fg": t, "bg": b, "ratio": round(r, 2), "ratio_exact": r})
        return rows

    out.append(f"<section id=contrast><div class=opener><div><h2>{e(L['contrast'])}</h2><p>{e(L['contrast_intro'])}</p>"
               "</div></div><div class=contrast>")
    for c in shown:
        out.append(f"<div><h3>{e(ctx_name(c))}</h3><ul>")
        for p in doc_pairs(c):
            fg = toks[p["fg"]]["contexts"][c]["hex"]
            bg = toks[p["bg"]]["contexts"][c]["hex"]
            ok = p["ratio_exact"] >= 4.5
            out.append(f"<li><span class=sample-pair style='color:{e(fg)};background:{e(bg)}'>Aa</span>"
                       f"<span class=pair-names><code>--{e(p['fg'])}</code><code>--{e(p['bg'])}</code></span>"
                       f"<span class='ratio {'ok' if ok else 'bad'}'>{p['ratio']}:1<small>"
                       f"{e(L['passes'] if ok else L['fails'])}</small></span></li>")
        out.append("</ul></div>")
    out.append("</div></section>")

    out.append("</main></div></body></html>")
    return "\n".join(out) + "\n"


def owner_questions(site: Site, design: Path, labels: dict) -> str:
    """The confirm step's questions and gaps, numbered, for the agent to ask in chat: one question per message, the
    gaps as one list."""
    data = json.loads((design / "usage.json").read_text())
    L = {**DEFAULT_LABELS, **labels}
    questions, gaps = questions_and_gaps(data, L, shown_contexts(site, data))
    return "\n".join([f"Questions for the owner ({len(questions)}), one per message:"]
                     + [f"{i}. {q}" for i, q in enumerate(questions, 1)]
                     + [f"Gaps ({len(gaps)}), one list in one message:"]
                     + [f"- {L['gap_missing'].format(role=g)}" for g in gaps])


def rem(size: str) -> float:
    m = re.match(r"([\d.]+)(rem|px|em)?", size.strip())
    if not m:
        return 0.0
    return float(m.group(1)) / (16 if m.group(2) == "px" else 1)


def questions_and_gaps(data: dict, L: dict, shown: list) -> tuple[list, list]:
    toks = data["tokens"]
    questions, asked = [], set()
    for n in data["near_duplicates"]:
        if n["context"] is not None and n["context"] not in shown:
            continue
        a = [x for x in n["a_names"] if not x.startswith("--") or toks.get(x[2:], {}).get("uses_all")]
        b = [x for x in n["b_names"] if not x.startswith("--") or toks.get(x[2:], {}).get("uses_all")]
        pair = frozenset((tuple(a), tuple(b)))  # the same two sides in either order are one question
        if a and b and pair not in asked:  # a pair with an unused token is no merge question
            asked.add(pair)
            questions.append(L["q_near_duplicate"].format(a=", ".join(a), b=", ".join(b), de=n["delta_e"]))
    used = {norm_font(f) for fs in data["fonts"]["tokens"].values() for f in fs}
    token_stack = ", ".join(sorted({next((f for f in fs if f.lower() not in GENERIC_FONTS), fs[0])
                                    for fs in data["fonts"]["tokens"].values() if fs}))
    for name, where in sorted(data["fonts"]["docs"].items()):
        if norm_font(name) not in used:
            questions.append(L["q_docs_font"].format(font=name, where=", ".join(where[:3]), tokens=token_stack))
    in_docs = {norm_font(n) for n in data["fonts"]["docs"]}
    for f in data["fonts"]["files"]:
        stem = font_stem(f)
        if norm_font(stem) and norm_font(stem) not in used and norm_font(stem) not in in_docs:
            questions.append(L["q_font_files"].format(font=stem, where=f, tokens=token_stack))
            in_docs.add(norm_font(stem))
    groups = {}
    for o in data["offtoken"]:
        # An owner's question only: not a value equal to a token or next to a used one (a cleanup, asked above as
        # a near pair), not a value the scan could not read (the table lists it).
        near_used = o.get("near_token") and toks.get(o["near_token"]["token"], {}).get("uses_all")
        if (o["kind"] == "color" and not o["oneoff"] and not o.get("equals_token") and not near_used
                and not o["value"].startswith("unresolved")):
            key = o["value"][:7] if o["value"].startswith("#") else o["value"]
            groups.setdefault(key, []).append(o)
    for key, items in groups.items():
        alphas = sorted({round(int(o["value"][7:9], 16) / 2.55) for o in items if len(o["value"]) == 9})
        value = key + (f" @ {', '.join(f'{a} %' for a in alphas)}" if alphas else "")
        uses = [u for o in items for u in o["uses"]]
        where = list(dict.fromkeys(uses))[:3]  # a line holding the value twice is named once
        questions.append(L["q_unexplained_color"].format(value=value, count=len(uses), where=", ".join(where)))
    for f in data["fonts"]["hardcoded"]:
        if not f["in_tokens"] and not f["oneoff"]:
            questions.append(L["q_unexplained_font"].format(font=f["family"], where=", ".join(f["uses"][:3])))
    role_names = L.get("roles") or {}
    gaps = [role_names.get(label, label) for label, pat in COMPLETENESS if not any(re.search(pat, n) for n in toks)]
    return questions, gaps


PAGE_CSS = """
:root{--paper:#f6f7f9;--panel:#fff;--ink:#14161b;--quiet:#5a6170;--rule:#e1e4e9;--ok:#1d6b45;--bad:#a8261d;
--edge:rgba(20,22,27,.14);color-scheme:light}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-padding-top:64px}
body{margin:0;background:var(--paper);color:var(--ink);font:400 17px/1.6 "Avenir Next","Segoe UI Variable Text","Noto Sans",
system-ui,sans-serif;font-variant-numeric:tabular-nums}
a:focus-visible,summary:focus-visible{outline:3px solid var(--ink);outline-offset:3px;border-radius:4px}
.bar{position:sticky;top:0;z-index:2;background:rgba(246,247,249,.96);border-bottom:1px solid var(--rule)}
.bar ol{max-width:1200px;margin:0 auto;padding:0 32px;list-style:none;display:flex;flex-wrap:wrap;gap:0 28px}
.bar a{display:block;padding:14px 0;color:var(--quiet);text-decoration:none;font-weight:600;font-size:15px}
.bar a:hover{color:var(--ink)}
.wrap{max-width:1200px;margin:0 auto;padding:0 32px 96px}
.cover{padding:72px 0 56px}
.brands{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}
.brands span{border:1px solid var(--rule);background:var(--panel);border-radius:999px;padding:4px 14px;font-weight:600;font-size:15px}
h1{font-size:60px;line-height:1.04;letter-spacing:-.02em;font-weight:700;margin:0 0 20px;max-width:15ch}
.lede{font-size:21px;line-height:1.55;color:var(--quiet);max-width:58ch;margin:0 0 32px}
.source{display:flex;flex-wrap:wrap;gap:8px 40px;margin:0 0 10px;font-size:15px}.source div{display:flex;gap:8px}
.source dt{color:var(--quiet)}.source dd{margin:0;font-weight:600}
section{padding:72px 0 32px;border-top:1px solid var(--rule)}
.opener{display:grid;grid-template-columns:minmax(0,4fr) minmax(0,7fr);gap:48px;align-items:start;margin-bottom:48px}
h2{font-size:68px;line-height:1;letter-spacing:-.03em;font-weight:700;margin:0 0 18px}
.opener>div:first-child>p{font-size:19px;line-height:1.55;color:var(--quiet);max-width:38ch;margin:0}
h3{font-size:24px;line-height:1.25;font-weight:700;margin:48px 0 6px}
.note{color:var(--quiet);max-width:64ch;margin:0 0 16px;font-size:16px}
code{font:inherit;font-size:14px;color:var(--quiet)}
.brand-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px}
.brand-col,.face{margin:0}
.brand-col figcaption,.face figcaption{font-size:20px;font-weight:700;margin:0 0 12px}
.stack{border-radius:14px;overflow:hidden;border:1px solid var(--edge)}
.band{display:flex;flex-direction:column;justify-content:space-between;gap:12px;min-height:112px;padding:16px 18px}
.band b{font-size:16px;font-weight:600}.band span{display:flex;justify-content:space-between;gap:8px;font-size:15px}
.band code{color:inherit;opacity:.75}
table{width:100%;border-collapse:separate;border-spacing:0;background:var(--panel);border:1px solid var(--rule);
border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:12px 16px;border-top:1px solid var(--rule);vertical-align:middle}
thead th{border-top:0;font-size:14px;font-weight:600;color:var(--quiet);background:#fafbfc}
tbody th{font-weight:400}.role{display:block;font-weight:600;font-size:16px}
.chip{display:inline-block;width:52px;height:34px;border-radius:8px;background:var(--c);
box-shadow:inset 0 0 0 1px var(--edge);vertical-align:middle;margin-right:12px}
.hex{font-size:15px}.empty{color:var(--quiet)}.quiet{display:block;color:var(--quiet);font-size:14px}
.face{background:var(--panel);border:1px solid var(--rule);border-radius:14px;padding:24px}
.aa{font-size:128px;line-height:1;margin:0 0 12px;letter-spacing:-.02em}
.fam{font-size:26px;line-height:1.2;margin:0 0 16px}
.facts{margin:0;display:grid;gap:6px;font-size:15px}.facts div{display:grid;grid-template-columns:120px 1fr;gap:12px}
.facts dt{color:var(--quiet)}.facts dd{margin:0;overflow-wrap:anywhere}
.families{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(320px,100%),1fr))}
.family{margin:0;background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:24px}
.family .sample{font-size:30px;line-height:1.2;margin:0 0 16px}.family code{display:block}
.scale{list-style:none;margin:0;padding:0;background:var(--panel);border:1px solid var(--rule);border-radius:12px}
.scale li{padding:22px 24px;border-top:1px solid var(--rule)}.scale li:first-child{border-top:0}
.step{margin:0 0 10px;line-height:1.1;overflow-wrap:anywhere}
.meta{margin:0;font-size:15px;display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline}.meta .quiet{display:inline}
.radii{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(130px,1fr))}
.radii figure{margin:0;background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:20px}
.box{display:block;width:72px;height:72px;border:2px solid var(--ink);margin-bottom:12px}.radii code{display:block}
.contrast{display:grid;gap:24px;grid-template-columns:repeat(auto-fit,minmax(min(360px,100%),1fr))}
.contrast h3{margin-top:0}
.contrast ul{list-style:none;margin:0;padding:0;background:var(--panel);border:1px solid var(--rule);border-radius:12px}
.contrast li{display:flex;align-items:center;gap:16px;padding:12px 16px;border-top:1px solid var(--rule)}
.contrast li:first-child{border-top:0}
.sample-pair{flex:none;width:56px;height:42px;border-radius:8px;display:grid;place-items:center;font-weight:600;
font-size:19px;box-shadow:inset 0 0 0 1px var(--edge)}
.pair-names{flex:1;min-width:0;display:grid}.pair-names code{overflow-wrap:anywhere}
.ratio{flex:none;display:grid;text-align:right;font-weight:700;font-size:16px}.ratio small{font-size:13px;font-weight:600}
.ok{color:var(--ok)}.bad{color:var(--bad)}
@media (max-width:900px){.wrap{padding:0 16px 64px}.bar ol{padding:0 16px;gap:0 18px}.cover{padding:40px 0 32px}
h1{font-size:40px}h2{font-size:46px}.lede{font-size:18px}.opener{grid-template-columns:1fr;gap:28px}section{padding-top:48px}
.aa{font-size:96px}
table.palette thead{display:none}table.palette,table.palette tbody,table.palette tr{display:block}
table.palette tr{padding:12px 16px;border-top:1px solid var(--rule)}table.palette tr:first-child{border-top:0}
table.palette td{display:flex;align-items:center;border:0;padding:4px 0;width:auto;text-align:left}
table.palette td::before{content:attr(data-label);flex:none;width:104px;color:var(--quiet);font-size:14px}
table.palette tbody th{display:block;padding:0 0 8px;border:0}.chip{width:44px;height:30px;margin-right:10px}
}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
"""


# ---------- check --------------------------------------------------------------------------------------------

def check(site: Site, design: Path) -> int:
    old = json.loads((design / "usage.json").read_text())
    new = extract(site)
    known = {(o["kind"], o["value"]) for o in old["offtoken"]}
    known_fonts = {f["family"] for f in old["fonts"]["hardcoded"]}
    added = [o for o in new["offtoken"] if (o["kind"], o["value"]) not in known]
    added_fonts = [f for f in new["fonts"]["hardcoded"] if f["family"] not in known_fonts and not f["in_tokens"]]
    for o in added:
        print(f"NEW {o['kind']} outside the tokens: {o['value']} at {', '.join(o['uses'][:5])}")
    for f in added_fonts:
        print(f"NEW font outside the tokens: {f['family']} at {', '.join(f['uses'][:5])}")
    print(f"{len(added)} new values and {len(added_fonts)} new fonts outside the tokens "
          f"(colour uses in tokens {new['coverage']['color_in_tokens_pct']}%)")
    return 1 if added or added_fonts else 0


def summary(data: dict) -> str:
    cov = data["coverage"]
    n = {k: sum(1 for t in data["tokens"].values() if t["type"] == k) for k in ("color", "dimension", "fontFamily", "other")}
    return (f"{len(data['tokens'])} tokens ({n['color']} colours, {n['fontFamily']} fonts, {n['dimension']} dimensions) "
            f"in {len(data['contexts'])} contexts ({', '.join(data['contexts'])}); {data['files_scanned']} files scanned\n"
            f"colour uses: {cov['color_token_uses']} through tokens, {cov['color_offtoken_uses']} outside "
            f"({cov['color_oneoff_uses']} named one-offs) = {cov['color_in_tokens_pct']}% in tokens; "
            f"{len(cov['color_unexplained_values'])} unexplained values\n"
            f"font uses: {cov['font_token_uses']} through tokens, {cov['font_hardcoded_uses']} hard-coded = "
            f"{cov['font_in_tokens_pct']}% in tokens; unexplained fonts: {', '.join(cov['font_unexplained']) or 'none'}\n"
            f"near-duplicate colour pairs (CIEDE2000 < 2): {len(data['near_duplicates'])}; "
            f"docs name fonts: {', '.join(sorted(data['fonts']['docs'])) or 'none'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["extract", "page", "questions", "check"])
    ap.add_argument("--site", default="tools/site.json")
    ap.add_argument("--out")
    ap.add_argument("--design", default="design")
    ap.add_argument("--labels")
    ap.add_argument("--lang", default="en", help="the labels' language, when the labels file holds several")
    ap.add_argument("--roles", help="a plain role name per token for this site, {token: {lang: name}} (copy route)")
    args = ap.parse_args()
    site = Site(args.site)
    if args.command == "extract":
        out = Path(args.out or args.design)
        out.mkdir(parents=True, exist_ok=True)
        data = extract(site)
        (out / "usage.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        (out / "tokens.json").write_text(json.dumps(dtcg(data), indent=1, ensure_ascii=False) + "\n")
        print(summary(data))
        return 0
    design = Path(args.design)
    labels = json.loads(Path(args.labels).read_text()) if args.labels else {}
    labels = labels.get("system_page", labels)
    labels = labels.get(args.lang) or labels.get("en") or labels
    if args.command == "questions":
        print(owner_questions(site, design, labels))
        return 0
    if args.command == "page":
        roles = json.loads(Path(args.roles).read_text()) if args.roles else None
        (design / "system.html").write_text(page(site, design, labels, roles, args.lang))
        print(f"wrote {design / 'system.html'}")
        return 0
    return check(site, design)


if __name__ == "__main__":
    sys.exit(main())
