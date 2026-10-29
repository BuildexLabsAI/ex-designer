"""Colour maths for the takeover scripts: CSS colour parsing, colour-mix(), CIEDE2000 distance and WCAG contrast.

A colour is a tuple (r, g, b, a) of floats, sRGB with gamma, 0..1 (out-of-gamut OKLCH values may fall outside 0..1;
hex() and contrast() clip them). parse() takes any CSS colour value: hex, rgb(), hsl(), hwb(), oklab(), oklch(), a
named colour, transparent, lab(), lch(), color() in srgb or display-p3, color-mix() in srgb, srgb-linear, oklab or
oklch, and var() through a lookup function.
It returns None for what it cannot resolve (currentColor, an unknown variable, an unsupported colour space).
"""
import math
import re

_NAMED = (
    "aliceblue:f0f8ff antiquewhite:faebd7 aqua:00ffff aquamarine:7fffd4 azure:f0ffff beige:f5f5dc bisque:ffe4c4 "
    "black:000000 blanchedalmond:ffebcd blue:0000ff blueviolet:8a2be2 brown:a52a2a burlywood:deb887 cadetblue:5f9ea0 "
    "chartreuse:7fff00 chocolate:d2691e coral:ff7f50 cornflowerblue:6495ed cornsilk:fff8dc crimson:dc143c cyan:00ffff "
    "darkblue:00008b darkcyan:008b8b darkgoldenrod:b8860b darkgray:a9a9a9 darkgreen:006400 darkgrey:a9a9a9 "
    "darkkhaki:bdb76b darkmagenta:8b008b darkolivegreen:556b2f darkorange:ff8c00 darkorchid:9932cc darkred:8b0000 "
    "darksalmon:e9967a darkseagreen:8fbc8f darkslateblue:483d8b darkslategray:2f4f4f darkslategrey:2f4f4f "
    "darkturquoise:00ced1 darkviolet:9400d3 deeppink:ff1493 deepskyblue:00bfff dimgray:696969 dimgrey:696969 "
    "dodgerblue:1e90ff firebrick:b22222 floralwhite:fffaf0 forestgreen:228b22 fuchsia:ff00ff gainsboro:dcdcdc "
    "ghostwhite:f8f8ff gold:ffd700 goldenrod:daa520 gray:808080 green:008000 greenyellow:adff2f grey:808080 "
    "honeydew:f0fff0 hotpink:ff69b4 indianred:cd5c5c indigo:4b0082 ivory:fffff0 khaki:f0e68c lavender:e6e6fa "
    "lavenderblush:fff0f5 lawngreen:7cfc00 lemonchiffon:fffacd lightblue:add8e6 lightcoral:f08080 lightcyan:e0ffff "
    "lightgoldenrodyellow:fafad2 lightgray:d3d3d3 lightgreen:90ee90 lightgrey:d3d3d3 lightpink:ffb6c1 "
    "lightsalmon:ffa07a lightseagreen:20b2aa lightskyblue:87cefa lightslategray:778899 lightslategrey:778899 "
    "lightsteelblue:b0c4de lightyellow:ffffe0 lime:00ff00 limegreen:32cd32 linen:faf0e6 magenta:ff00ff maroon:800000 "
    "mediumaquamarine:66cdaa mediumblue:0000cd mediumorchid:ba55d3 mediumpurple:9370db mediumseagreen:3cb371 "
    "mediumslateblue:7b68ee mediumspringgreen:00fa9a mediumturquoise:48d1cc mediumvioletred:c71585 "
    "midnightblue:191970 mintcream:f5fffa mistyrose:ffe4e1 moccasin:ffe4b5 navajowhite:ffdead navy:000080 "
    "oldlace:fdf5e6 olive:808000 olivedrab:6b8e23 orange:ffa500 orangered:ff4500 orchid:da70d6 palegoldenrod:eee8aa "
    "palegreen:98fb98 paleturquoise:afeeee palevioletred:db7093 papayawhip:ffefd5 peachpuff:ffdab9 peru:cd853f "
    "pink:ffc0cb plum:dda0dd powderblue:b0e0e6 purple:800080 rebeccapurple:663399 red:ff0000 rosybrown:bc8f8f "
    "royalblue:4169e1 saddlebrown:8b4513 salmon:fa8072 sandybrown:f4a460 seagreen:2e8b57 seashell:fff5ee "
    "sienna:a0522d silver:c0c0c0 skyblue:87ceeb slateblue:6a5acd slategray:708090 slategrey:708090 snow:fffafa "
    "springgreen:00ff7f steelblue:4682b4 tan:d2b48c teal:008080 thistle:d8bfd8 tomato:ff6347 turquoise:40e0d0 "
    "violet:ee82ee wheat:f5deb3 white:ffffff whitesmoke:f5f5f5 yellow:ffff00 yellowgreen:9acd32")
NAMED = {k: "#" + v for k, v in (p.split(":") for p in _NAMED.split())}
NAMED["transparent"] = "#00000000"

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])")
SPACES = r"srgb|srgb-linear|display-p3|a98-rgb|prophoto-rgb|rec2020|xyz|xyz-d50|xyz-d65"
# color() only with a colour space after it, so a JavaScript function called color() is not taken for one.
FUNC_RE = re.compile(rf"\b(?:rgba?|hsla?|hwb|oklab|oklch|lab|lch|color-mix)\(|\bcolor\((?=\s*(?:{SPACES})\b)", re.I)


def _split_top(s: str, sep: str) -> list[str]:
    """Split on sep outside parentheses."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x.strip() for x in out]


def call_span(text: str, start: int) -> int:
    """Index just past the closing parenthesis of the call whose name starts at `start`; -1 if it never closes."""
    depth = 0
    for i in range(text.index("(", start), len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def _num(tok: str, pct_scale: float = 1.0) -> float:
    tok = tok.strip()
    if tok == "none":
        return 0.0
    if tok.endswith("%"):
        return float(tok[:-1]) / 100 * pct_scale
    return float(tok)


def _hue(tok: str) -> float:
    tok = tok.strip().lower()
    if tok == "none":
        return 0.0
    for unit, k in (("deg", 1), ("grad", 0.9), ("rad", 180 / math.pi), ("turn", 360)):
        if tok.endswith(unit):
            return float(tok[: -len(unit)]) * k
    return float(tok)


def _args(body: str) -> tuple[list[str], str | None]:
    """Channel tokens and the alpha token of a colour function body, legacy (commas) or modern (spaces and /)."""
    if "," in body:
        parts = _split_top(body, ",")
        return parts[:3], (parts[3] if len(parts) > 3 else None)
    main, _, alpha = body.partition("/")
    return main.split(), (alpha.strip() or None)


def _alpha(tok: str | None) -> float:
    return 1.0 if tok is None else max(0.0, min(1.0, _num(tok)))


def to_linear(c: float) -> float:
    a = abs(c)
    return math.copysign(a / 12.92 if a <= 0.04045 else ((a + 0.055) / 1.055) ** 2.4, c)


def from_linear(c: float) -> float:
    a = abs(c)
    return math.copysign(12.92 * a if a <= 0.0031308 else 1.055 * a ** (1 / 2.4) - 0.055, c)


def _cbrt(x: float) -> float:
    return math.copysign(abs(x) ** (1 / 3), x)


def srgb_to_oklab(r, g, b):
    r, g, b = to_linear(r), to_linear(g), to_linear(b)
    l = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab_to_srgb(L, a, b):
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (from_linear(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
            from_linear(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
            from_linear(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


def _hsl_to_srgb(h, s, l):
    def f(n):
        k = (n + h / 30) % 12
        return l - s * min(l, 1 - l) * max(-1, min(k - 3, 9 - k, 1))
    return f(0), f(8), f(4)


def _parse_hex(h: str):
    h = h[1:]
    if len(h) in (3, 4):
        h = "".join(ch * 2 for ch in h)
    v = [int(h[i:i + 2], 16) / 255 for i in range(0, len(h), 2)]
    return (v[0], v[1], v[2], v[3] if len(v) == 4 else 1.0)


D50 = (0.3457 / 0.3585, 1.0, (1 - 0.3457 - 0.3585) / 0.3585)


def _lab_d50_to_srgb(L, a, b):
    """CSS lab(): CIE Lab with the D50 white, adapted to D65 (Bradford) and converted to sRGB (CSS Color 4)."""
    eps, kappa = 216 / 24389, 24389 / 27
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    xr = fx ** 3 if fx ** 3 > eps else (116 * fx - 16) / kappa
    yr = fy ** 3 if L > kappa * eps else L / kappa
    zr = fz ** 3 if fz ** 3 > eps else (116 * fz - 16) / kappa
    x, y, z = xr * D50[0], yr * D50[1], zr * D50[2]
    x, y, z = (0.9554734527042182 * x - 0.023098536874261423 * y + 0.0632593086610217 * z,
               -0.028369706963208136 * x + 1.0099954580058226 * y + 0.021041398966943008 * z,
               0.012314001688319899 * x - 0.020507696433477912 * y + 1.3303659366080753 * z)
    return (from_linear(3.2404542 * x - 1.5371385 * y - 0.4985314 * z),
            from_linear(-0.9692660 * x + 1.8760108 * y + 0.0415560 * z),
            from_linear(0.0556434 * x - 0.2040259 * y + 1.0572252 * z))


def _p3_to_srgb(r, g, b):
    r, g, b = (to_linear(x) for x in (r, g, b))
    x = 0.4865709 * r + 0.2656677 * g + 0.1982173 * b
    y = 0.2289746 * r + 0.6917385 * g + 0.0792869 * b
    z = 0.0000000 * r + 0.0451134 * g + 1.0439444 * b
    return (from_linear(3.2404542 * x - 1.5371385 * y - 0.4985314 * z),
            from_linear(-0.9692660 * x + 1.8760108 * y + 0.0415560 * z),
            from_linear(0.0556434 * x - 0.2040259 * y + 1.0572252 * z))


def _mix(body: str, lookup, depth: int = 0):
    parts = _split_top(body, ",")
    if len(parts) != 3 or not parts[0].lower().startswith("in "):
        return None
    space = parts[0][3:].split()[0].lower()
    cols, pcts = [], []
    for p in parts[1:]:
        m = re.search(r"\s(\d+(?:\.\d+)?)%\s*$", " " + p)
        pct = float(m.group(1)) / 100 if m else None
        col = parse((" " + p)[: m.start()].strip() if m else p, lookup, depth + 1)
        if col is None:
            return None
        cols.append(col)
        pcts.append(pct)
    p1, p2 = pcts
    if p1 is None and p2 is None:
        p1 = p2 = 0.5
    elif p1 is None:
        p1 = 1 - p2
    elif p2 is None:
        p2 = 1 - p1
    total = p1 + p2
    if total <= 0:
        return None
    mult = min(total, 1.0)
    p1, p2 = p1 / total, p2 / total
    (c1, c2) = cols
    a = c1[3] * p1 + c2[3] * p2
    if space in ("srgb", "srgb-linear", "oklab"):
        conv = {"srgb": lambda c: c[:3], "srgb-linear": lambda c: tuple(to_linear(x) for x in c[:3]),
                "oklab": lambda c: srgb_to_oklab(*c[:3])}[space]
        back = {"srgb": lambda v: v, "srgb-linear": lambda v: tuple(from_linear(x) for x in v),
                "oklab": lambda v: oklab_to_srgb(*v)}[space]
        v1, v2 = conv(c1), conv(c2)
        if a == 0:
            return (0.0, 0.0, 0.0, 0.0)
        mixed = tuple((x * c1[3] * p1 + y * c2[3] * p2) / a for x, y in zip(v1, v2))
        r, g, b = back(mixed)
        return (r, g, b, a * mult)
    if space == "oklch":
        def lch(c):
            L, A, B = srgb_to_oklab(*c[:3])
            C = math.hypot(A, B)
            return L, C, (math.degrees(math.atan2(B, A)) % 360 if C > 1e-4 else None)
        (L1, C1, h1), (L2, C2, h2) = lch(c1), lch(c2)
        if h1 is None:
            h1 = h2 if h2 is not None else 0.0
        if h2 is None:
            h2 = h1
        m = re.search(r"\b(shorter|longer|increasing|decreasing)\s+hue\b", parts[0], re.I)
        method, d = (m.group(1).lower() if m else "shorter"), h2 - h1
        if method == "shorter":
            if d > 180:
                h1 += 360
            elif d < -180:
                h2 += 360
        elif method == "longer":
            if 0 < d < 180:
                h1 += 360
            elif -180 < d <= 0:
                h2 += 360
        elif method == "increasing" and h2 < h1:
            h2 += 360
        elif method == "decreasing" and h1 < h2:
            h1 += 360
        if a == 0:
            return (0.0, 0.0, 0.0, 0.0)
        L = (L1 * c1[3] * p1 + L2 * c2[3] * p2) / a
        C = (C1 * c1[3] * p1 + C2 * c2[3] * p2) / a
        h = math.radians((h1 * p1 + h2 * p2) % 360)
        r, g, b = oklab_to_srgb(L, C * math.cos(h), C * math.sin(h))
        return (r, g, b, a * mult)
    return None


def parse(value: str, lookup=None, depth: int = 0):
    """A CSS colour value as (r, g, b, a), or None. lookup(name) returns the raw value of a custom property."""
    if value is None or depth > 20:
        return None
    v = value.strip()
    low = v.lower()
    if not v:
        return None
    if low.startswith("var("):
        inner = v[v.index("(") + 1: call_span(v, 0) - 1] if call_span(v, 0) > 0 else ""
        name, _, fallback = inner.partition(",")
        raw = lookup(name.strip()) if lookup else None
        if raw is None and fallback.strip():
            raw = fallback.strip()
        return parse(raw, lookup, depth + 1) if raw is not None else None
    if v.startswith("#"):
        return _parse_hex(v) if HEX_RE.fullmatch(v) else None
    if low in NAMED:
        return _parse_hex(NAMED[low])
    m = re.match(r"([a-z-]+)\((.*)\)$", low, re.S)
    if not m:
        return None
    fn, body = m.group(1), v[v.index("(") + 1:-1]
    if "var(" in body.lower() and fn != "color-mix":
        if depth > 10:
            return None
        body = re.sub(r"var\([^()]*\)", lambda mm: lookup(mm.group(0)[4:-1].split(",")[0].strip()) or "0"
                      if lookup else "0", body)
    try:
        if fn == "color-mix":
            return _mix(body, lookup, depth)
        if fn == "color":
            space, _, rest = body.strip().partition(" ")
            ch, al = _args(rest)
            vals = [_num(x) for x in ch[:3]]
            if space.lower() == "srgb":
                return (*vals, _alpha(al))
            if space.lower() == "srgb-linear":
                return (*(from_linear(v) for v in vals), _alpha(al))
            if space.lower() == "display-p3":
                return (*_p3_to_srgb(*vals), _alpha(al))
            return None
        ch, al = _args(body)
        if fn in ("rgb", "rgba"):
            r, g, b = (_num(x, 255) / 255 if x.strip().endswith("%") else _num(x) / 255 for x in ch)
            return (r, g, b, _alpha(al))
        if fn in ("hsl", "hsla"):
            h, s, l = _hue(ch[0]), _num(ch[1] if ch[1].endswith("%") else ch[1] + "%"), \
                _num(ch[2] if ch[2].endswith("%") else ch[2] + "%")
            return (*_hsl_to_srgb(h, s, l), _alpha(al))
        if fn == "hwb":
            h, w, bl = _hue(ch[0]), _num(ch[1]), _num(ch[2])
            if w + bl >= 1:
                g = w / (w + bl)
                return (g, g, g, _alpha(al))
            r, g, b = _hsl_to_srgb(h, 1, 0.5)
            return (*(x * (1 - w - bl) + w for x in (r, g, b)), _alpha(al))
        if fn == "lab":
            L = _num(ch[0], 100) if ch[0].strip().endswith("%") else _num(ch[0])
            return (*_lab_d50_to_srgb(L, _num(ch[1], 125), _num(ch[2], 125)), _alpha(al))
        if fn == "lch":
            L = _num(ch[0], 100) if ch[0].strip().endswith("%") else _num(ch[0])
            C, h = _num(ch[1], 150), math.radians(_hue(ch[2]))
            return (*_lab_d50_to_srgb(L, C * math.cos(h), C * math.sin(h)), _alpha(al))
        if fn == "oklab":
            L = _num(ch[0])
            return (*oklab_to_srgb(L, _num(ch[1], 0.4), _num(ch[2], 0.4)), _alpha(al))
        if fn == "oklch":
            L, C, h = _num(ch[0]), _num(ch[1], 0.4), math.radians(_hue(ch[2]))
            return (*oklab_to_srgb(L, C * math.cos(h), C * math.sin(h)), _alpha(al))
    except (ValueError, IndexError, ZeroDivisionError):
        return None
    return None


def clip(c):
    return tuple(max(0.0, min(1.0, x)) for x in c[:3]) + tuple(c[3:])


def hex(c) -> str:  # noqa: A001  the CSS name for the notation
    r, g, b, a = clip(c)
    s = "#{:02x}{:02x}{:02x}".format(*(round(x * 255) for x in (r, g, b)))
    return s if a >= 0.9995 else s + "{:02x}".format(round(a * 255))


def over(fg, bg):
    """fg composited over an opaque bg."""
    a = fg[3]
    return tuple(f * a + b * (1 - a) for f, b in zip(clip(fg)[:3], clip(bg)[:3])) + (1.0,)


def luminance(c) -> float:
    r, g, b = (to_linear(x) for x in clip(c)[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg, base=(1.0, 1.0, 1.0, 1.0)) -> float:
    """WCAG 2 contrast ratio; a translucent bg sits on `base`, a translucent fg on the result."""
    bg = over(bg, base) if bg[3] < 1 else bg
    fg = over(fg, bg) if fg[3] < 1 else fg
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def lab(c):
    """CIE L*a*b* (D65) of an sRGB colour."""
    r, g, b = (to_linear(x) for x in clip(c)[:3])
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29  # noqa: E731
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def from_lab(L, a, b):
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    inv = lambda t: t ** 3 if t > 6 / 29 else 3 * (6 / 29) ** 2 * (t - 4 / 29)  # noqa: E731
    x, y, z = inv(fx) * 0.95047, inv(fy), inv(fz) * 1.08883
    r = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    bl = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    return (from_linear(r), from_linear(g), from_linear(bl), 1.0)


def delta_e(c1, c2) -> float:
    """CIEDE2000 between two opaque sRGB colours."""
    return de2000(lab(c1), lab(c2))


def de2000(lab1, lab2) -> float:
    """CIEDE2000 between two CIE L*a*b* colours (Sharma, Wu, Dalal 2005)."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if C1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if C2p else 0.0
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        if dhp > 180:
            dhp -= 360
        elif dhp < -180:
            dhp += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lpm, Cpm = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hpm = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hpm = (h1p + h2p) / 2
    else:
        hpm = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hpm - 30)) + 0.24 * math.cos(math.radians(2 * hpm))
         + 0.32 * math.cos(math.radians(3 * hpm + 6)) - 0.20 * math.cos(math.radians(4 * hpm - 63)))
    dtheta = 30 * math.exp(-(((hpm - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / math.sqrt(20 + (Lpm - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cpm, 1 + 0.015 * Cpm * T
    Rt = -math.sin(math.radians(2 * dtheta)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))
