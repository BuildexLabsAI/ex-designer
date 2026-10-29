"""Make the README's pictures again, from the invented site and brand in tests/fixtures/. Usage, from the repository:

  python3 scripts/readme_images.py

1. Serves a copy of tests/fixtures/code-site on 127.0.0.1 (no network; the site's third-party requests are blocked).
2. Runs the skill's own scripts on it: report.py (the audit, with the invented findings below), tokens.py (the design
   system page), brandbook.py (the brand book of the invented brand Alpha Studio), and shoot.py and verify.py (one
   token change: the Beta Labs accent goes from #b93a0b to #9a3412).
3. Takes screenshots of each output in the Mac's Google Chrome and writes them to docs/images/.
4. Prints the numbers the README quotes.

It takes about two minutes. All names in it are invented; the findings texts were written by GPT (copy route).
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "src" / "ex-designer"
TESTS = REPO / "tests"
IMAGES = REPO / "docs" / "images"
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(SKILL / "scripts"))
import fixture_server  # noqa: E402
import brandbook  # noqa: E402
import livecheck  # noqa: E402
import shoot  # noqa: E402
import verify  # noqa: E402
from lib.site import Site  # noqa: E402

VIEW = (1280, 860)
WIDTH = 1600  # the width of each picture in docs/images/, shot at 2x and scaled down
OLD_ACCENT, NEW_ACCENT = "#b93a0b", "#9a3412"
FINDINGS = [  # (id, severity, area, rank, places): facts of tests/fixtures/code-site
    ("F1", "high", "cro", 1, [{"page": "home", "selector": ".hero .button"}]),
    ("F2", "high", "privacy", 2, []),
    ("F3", "medium", "seo", 3, []),
    ("F4", "medium", "ux", 4, [{"page": "home", "selector": ".pulse"}]),
    ("F5", "low", "ux", None, [{"page": "home", "selector": ".card", "text": "Today"}]),
    ("F6", "low", "ux", None, [{"page": "home", "selector": "nav a", "text": "Wide"}]),
    ("F7", "low", "cro", None, [{"page": "about", "selector": ".card"}]),
]
TEXTS = {
    "F1": {
        "title": "“Start” leads to About",
        "where": "The main button on the home page.",
        "fix": "Rename the button to describe its next step and link it to contact or signup."
    },
    "F2": {
        "title": "Tracking starts without consent",
        "where": "On the home page, before the visitor gives consent.",
        "fix": "Add a consent banner. Load the tracker and send analytics only after the visitor agrees."
    },
    "F3": {
        "title": "The Finnish page is missing",
        "where": "The home page’s language information for search engines points to /fi/.",
        "fix": "Remove the Finnish language reference until /fi/ has a working Finnish page."
    },
    "F4": {
        "title": "The pulsing dot ignores motion preferences",
        "where": "The teal dot in the home page hero.",
        "fix": "Stop the continuous pulse. Keep the dot still when the visitor has enabled reduced motion."
    },
    "F5": {
        "title": "The “Today” card shows unexplained numbers",
        "where": "The “Today” card on the home page.",
        "fix": "Remove the random number. Explain what the timestamp means, or remove it too."
    },
    "F6": {
        "title": "“Wide” does not explain its destination",
        "where": "The “Wide” link in the top menu.",
        "fix": "Rename the link to describe what visitors will find on the page."
    },
    "F7": {
        "title": "The promised contact form is missing",
        "where": "The contact card on the About page.",
        "fix": "Add the promised form and link the button to it."
    },
    "X1": {
        "title": "“Built to last.” has sufficient contrast",
        "reason": "The teal text measures 5.47:1 on white, above the WCAG AA requirement of 4.5:1."
    },
}  # written by GPT (copy route)


def findings_json(base: str) -> dict:
    rows = []
    for fid, sev, area, rank, places in FINDINGS:
        row = {"id": fid, "severity": sev, "area": area, "places": places, "text": {"en": TEXTS[fid]}}
        if rank:
            row["rank"] = rank
        rows.append(row)
    return {"site": "alpha.invalid", "date": "2026-10-28",
            "pages": [{"id": "home", "url": base + "/", "name": "Alpha Studio /"},
                      {"id": "about", "url": base + "/about/", "name": "Alpha Studio /about/"}],
            "findings": rows, "dropped": [{"id": "X1", "area": "ux", "text": {"en": TEXTS["X1"]}}]}


def set_accent(css: Path, value: str):
    text = css.read_text()
    block = text.index('[data-brand="beta"]')
    end = text.index("}", block)
    part = text[block:end]
    assert f"--accent: {OLD_ACCENT};" in part or f"--accent: {NEW_ACCENT};" in part
    part = part.replace(f"--accent: {OLD_ACCENT};", f"--accent: {value};").replace(
        f"--accent: {NEW_ACCENT};", f"--accent: {value};")
    css.write_text(text[:block] + part + text[end:])


def shot(page, url: str, out: Path, scroll_to: str | None = None):
    page.goto(url)
    page.wait_for_load_state("networkidle")
    if scroll_to:
        page.locator(scroll_to).first.scroll_into_view_if_needed()
        page.evaluate("(sel) => window.scrollTo(0, document.querySelector(sel).getBoundingClientRect().top"
                      " + window.scrollY - 24)", scroll_to)
    page.wait_for_timeout(400)
    page.screenshot(path=str(out))
    img = Image.open(out)
    img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
    img.convert("RGB").save(out, optimize=True)


def overview(parts: list[Path], out: Path):
    """The four outputs side by side, each with its step number, for the top of the README."""
    tw, gap, pad, head = 560, 32, 32, 56
    thumbs = [Image.open(p).convert("RGB") for p in parts]
    thumbs = [t.resize((tw, round(t.height * tw / t.width)), Image.LANCZOS) for t in thumbs]
    th = max(t.height for t in thumbs) + head
    sheet = Image.new("RGB", (pad * 2 + tw * 2 + gap, pad * 2 + th * 2 + gap), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 24)
    for i, t in enumerate(thumbs):
        x, y = pad + (i % 2) * (tw + gap), pad + (i // 2) * (th + gap)
        cx, cy = x + 18, y + head // 2 - 4
        draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=(22, 22, 22))
        draw.text((cx, cy), str(i + 1), fill=(255, 255, 255), font=font, anchor="mm")
        sheet.paste(t, (x, y + head))
        draw.rectangle([x - 1, y + head - 1, x + tw, y + head + t.height], outline=(214, 214, 208))
    sheet.save(out, optimize=True)


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ex-designer-readme-") as tmp:
        return build(Path(tmp))


def build(work: Path) -> int:
    site_dir = work / "code-site"
    shutil.copytree(TESTS / "fixtures" / "code-site", site_dir)
    server, base, _ = fixture_server.start(site_dir)
    site = Site(site_dir / "tools" / "site.json")
    site.data["serve"]["url"] = base
    (site_dir / "tools" / "site.json").write_text(json.dumps(site.data, indent=2))
    numbers = {}
    try:
        # 1. The audit report.
        (work / "findings.json").write_text(json.dumps(findings_json(base)))
        subprocess.run([sys.executable, str(SKILL / "scripts" / "report.py"), "--findings", str(work / "findings.json"),
                        "--labels", str(SKILL / "templates" / "report-labels.json"), "--lang", "en",
                        "--out", str(work / "report.html")], check=True, capture_output=True)
        numbers["findings"] = len(FINDINGS)
        numbers["fix_first"] = sum(1 for f in FINDINGS if f[3])

        # 2. The design system page, from the site's own token file.
        design = work / "design"
        for cmd in (["extract", "--out", str(design)],
                    ["page", "--design", str(design), "--labels", str(SKILL / "templates" / "ui-labels.json"),
                     "--lang", "en"]):
            subprocess.run([sys.executable, str(SKILL / "scripts" / "tokens.py"), cmd[0], "--site",
                            str(site_dir / "tools" / "site.json"), *cmd[1:]], check=True, capture_output=True)
        numbers["token_file"] = site.data["tokens"]["file"]

        # 3. The brand book of Alpha Studio.
        wd = work / "brand-work"
        shutil.copytree(TESTS / "fixtures" / "brand-work", wd)
        cfg = json.loads((wd / "brand.json").read_text())
        cfg.update(site=str(site_dir / "tools" / "site.json"), design=str(design), kit=str(work / "brand"))
        (wd / "brand.json").write_text(json.dumps(cfg))
        brandbook.read(wd, base=base)
        built = brandbook.build(wd)
        if not built["ok"]:
            raise SystemExit(f"brand book build failed: {built['problems'][:3]}")
        numbers["brand_book_pdf_pages"] = built["pdf_pages"]

        # 4. One change, checked against the baseline.
        baseline = work / "baseline"
        stable = shoot.shoot(site, baseline / "shots", runs=3)
        seo = livecheck.seo(site, livecheck.Source(site, False), site.get("pages"))
        (baseline / "seo.json").write_text(json.dumps(seo))
        css = site_dir / site.data["tokens"]["file"]
        set_accent(css, NEW_ACCENT)
        review = verify.run(site, baseline, design, work / "review", ["beta.invalid"], True)
        set_accent(css, OLD_ACCENT)
        if not review["ok"]:
            raise SystemExit(f"verify failed: {json.dumps(review)[:600]}")
        numbers["shots"] = len(stable["shots"])
        numbers["shots_changed"] = len(review["pixels"]["changed"])
        numbers["changed_hosts"] = sorted({c.split("/")[0] for c in review["pixels"]["changed"]})

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": VIEW[0], "height": VIEW[1]}, device_scale_factor=2)
            shot(page, (work / "report.html").as_uri(), IMAGES / "audit-report.png")
            shot(page, (design / "system.html").as_uri(), IMAGES / "design-system-page.png", "#colours")
            shot(page, (work / "brand" / "brand-book.html").as_uri(), IMAGES / "brand-book-page.png", "#colour")
            shot(page, (work / "review" / "diff" / "index.html").as_uri(), IMAGES / "change-review.png")
            browser.close()
        overview([IMAGES / n for n in ("audit-report.png", "design-system-page.png", "brand-book-page.png",
                                       "change-review.png")], IMAGES / "takeover-overview.png")
    finally:
        server.shutdown()
    print(json.dumps(numbers, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
