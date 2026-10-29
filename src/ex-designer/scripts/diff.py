"""Pixel diff of two screenshot sets, and a review page that shows only the shots that changed.

  python3 diff.py <before-dir> <after-dir> --out review/ [--only-stable]

A pixel counts as changed when any channel differs at all: the harness is built for zero noise, so there is no
threshold to tune. Changed pixels are grouped into boxes (16 px cells, joined when they touch). A shot whose height
changed counts its extra rows as changed. Writes review/diff.json and review/index.html (before, after and the
changed boxes outlined, changed shots only). Exit 0: nothing changed; 1: something changed; 2: a set is missing.
--only-stable leaves out the shots the before set's manifest marks unstable.
"""
import argparse
import html
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

CELL = 16


def boxes(mask: np.ndarray) -> list[list[int]]:
    """Boxes [x, y, w, h] around groups of changed pixels: 16 px cells with a change, joined when they touch."""
    h, w = mask.shape
    gh, gw = -(-h // CELL), -(-w // CELL)
    pad = np.zeros((gh * CELL, gw * CELL), bool)
    pad[:h, :w] = mask
    cells = pad.reshape(gh, CELL, gw, CELL).any(axis=(1, 3))
    seen = np.zeros_like(cells)
    out = []
    for cy, cx in zip(*np.nonzero(cells)):
        if seen[cy, cx]:
            continue
        stack, y0, y1, x0, x1 = [(cy, cx)], cy, cy, cx, cx
        seen[cy, cx] = True
        while stack:
            y, x = stack.pop()
            y0, y1, x0, x1 = min(y0, y), max(y1, y), min(x0, x), max(x1, x)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < gh and 0 <= nx < gw and cells[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        sub = mask[y0 * CELL:(y1 + 1) * CELL, x0 * CELL:(x1 + 1) * CELL]
        ys, xs = np.nonzero(sub)
        out.append([int(x0 * CELL + xs.min()), int(y0 * CELL + ys.min()), int(xs.max() - xs.min() + 1),
                    int(ys.max() - ys.min() + 1)])
    return out


def compare(a: Path, b: Path) -> dict:
    ia, ib = np.asarray(Image.open(a).convert("RGB")), np.asarray(Image.open(b).convert("RGB"))
    h, w = max(ia.shape[0], ib.shape[0]), max(ia.shape[1], ib.shape[1])
    pa, pb = np.zeros((h, w, 3), np.int16) - 1, np.zeros((h, w, 3), np.int16) - 2
    pa[:ia.shape[0], :ia.shape[1]] = ia
    pb[:ib.shape[0], :ib.shape[1]] = ib
    mask = np.any(pa != pb, axis=2)
    n = int(mask.sum())
    return {"changed_pixels": n, "boxes": boxes(mask) if n else [], "size_before": [ia.shape[1], ia.shape[0]],
            "size_after": [ib.shape[1], ib.shape[0]]}


def outlined(src: Path, bxs: list, dst: Path):
    img = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(img)
    for x, y, w, h in bxs:
        d.rectangle([x - 3, y - 3, x + w + 2, y + h + 2], outline=(230, 0, 90), width=3)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)


def browser_of(root: Path) -> str | None:
    m = root / "manifest.json"
    return json.loads(m.read_text()).get("browser") if m.exists() else None


def unstable_of(root: Path) -> set[str]:
    m = root / "manifest.json"
    if not m.exists():
        return set()
    return {s["file"] for s in json.loads(m.read_text())["shots"] if not s.get("stable", True)}


def run(before: Path, after: Path, out: Path, only_stable: bool = False) -> dict:
    if not before.is_dir() or not after.is_dir():
        raise FileNotFoundError(f"missing screenshot set: {before if not before.is_dir() else after}")
    vb, va = browser_of(before), browser_of(after)
    if not vb or not va:
        raise ValueError(f"no Chrome version in {before if not vb else after}/manifest.json: shots of unknown versions "
                         "are not compared")
    if vb != va:
        raise ValueError(f"shots from different Chrome versions ({vb} / {va}): re-shoot the baseline with this one")
    skip = unstable_of(before) if only_stable else set()
    files_b = {p.relative_to(before).as_posix() for p in before.rglob("*.png")}
    files_a = {p.relative_to(after).as_posix() for p in after.rglob("*.png")}
    results, changed = [], []
    for rel in sorted(files_b & files_a):
        if rel in skip:
            continue
        r = {"file": rel, **compare(before / rel, after / rel)}
        results.append(r)
        if r["changed_pixels"]:
            changed.append(r)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for r in changed:
        outlined(before / r["file"], r["boxes"], out / "before" / r["file"])
        outlined(after / r["file"], r["boxes"], out / "after" / r["file"])
    report = {"before": str(before), "after": str(after), "compared": len(results), "changed": len(changed),
              "only_in_before": sorted(files_b - files_a), "only_in_after": sorted(files_a - files_b),
              "skipped_unstable": sorted(skip & files_b), "results": results}
    (out / "diff.json").write_text(json.dumps(report, indent=1) + "\n")
    (out / "index.html").write_text(review_page(report))
    return report


def review_page(r: dict) -> str:
    e = html.escape
    rows = []
    for x in r["results"]:
        if not x["changed_pixels"]:
            continue
        rows.append(f"<section><h2>{e(x['file'])}</h2><p>{x['changed_pixels']} px in {len(x['boxes'])} areas"
                    f"{' · size ' + e(str(x['size_before'])) + ' → ' + e(str(x['size_after'])) if x['size_before'] != x['size_after'] else ''}"
                    f"</p><div class=pair><figure><img src='before/{e(x['file'])}' alt=''><figcaption>before</figcaption>"
                    f"</figure><figure><img src='after/{e(x['file'])}' alt=''><figcaption>after</figcaption></figure></div>"
                    "</section>")
    gone = "".join(f"<li>{e(f)}</li>" for f in r["only_in_before"] + r["only_in_after"])
    return ("<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            "initial-scale=1'><title>Review</title><style>body{margin:0;font:15px/1.5 system-ui,sans-serif;background:#f6f6f4;"
            "color:#1b1b19}main{max-width:1400px;margin:0 auto;padding:24px 16px}h1{font-size:22px}h2{font-size:15px;"
            "font-family:ui-monospace,Menlo,monospace;overflow-wrap:anywhere}.pair{display:grid;gap:12px;grid-template-columns:"
            "repeat(auto-fit,minmax(320px,1fr))}figure{margin:0}img{max-width:100%;border:1px solid #d9d9d4}figcaption"
            "{color:#5f5f5a;font-size:13px}section{border-top:1px solid #d9d9d4;padding:12px 0}</style></head><body><main>"
            f"<h1>{r['changed']} of {r['compared']} shots changed</h1>"
            + (f"<p>Only in one set:</p><ul>{gone}</ul>" if gone else "") + "".join(rows) + "</main></body></html>\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only-stable", action="store_true")
    args = ap.parse_args()
    try:
        r = run(Path(args.before), Path(args.after), Path(args.out), args.only_stable)
    except (FileNotFoundError, ValueError) as e:
        print(e)
        return 2
    print(f"{r['changed']} of {r['compared']} shots changed"
          + (f"; {len(r['only_in_before']) + len(r['only_in_after'])} in one set only" if r["only_in_before"] or r["only_in_after"] else "")
          + f" -> {args.out}/index.html")
    for x in r["results"]:
        if x["changed_pixels"]:
            print(f"  {x['file']}: {x['changed_pixels']} px in {len(x['boxes'])} areas")
    return 1 if r["changed"] or r["only_in_before"] or r["only_in_after"] else 0


if __name__ == "__main__":
    sys.exit(main())
