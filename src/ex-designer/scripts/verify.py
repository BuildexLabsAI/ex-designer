"""The checks of one change, against the baseline: run after every token edit, before anyone sees the change.

  python3 verify.py --site tools/site.json --baseline baseline/ --design design/ --out review/
                    [--expect-hosts example.com] [--skip-checks]

1. The project's own checks (site.json "checks", such as npm run lint and npm test) pass.
2. No new colour or font outside the tokens (tokens.py check against design/usage.json).
3. Contrast: every foreground/background token pair that passed WCAG AA (4.5:1) in the baseline still passes.
4. Screenshots of the local build (serve.url) against baseline/shots: the review page lists only changed shots.
   With --expect-hosts, a change on any other host fails (a token change for one brand must not move another).
5. No new sideways overflow; no page that answered 200 now answers an error.
6. SEO facts of the local build equal baseline/seo.json.
Writes review/verify.json and review/index.html (the diff). Exit 0 only when every check passes.
"""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diff  # noqa: E402
import livecheck  # noqa: E402
import shoot  # noqa: E402
import tokens  # noqa: E402
from lib.site import Site  # noqa: E402


def pairs(data: dict) -> dict[tuple, float]:
    return {(ctx, p["fg"], p["bg"]): p["ratio_exact"] for ctx in data["contexts"]
            for p in tokens.contrast_pairs(data, ctx, all_fills=True)}


def run(site: Site, baseline: Path, design: Path, out: Path, expect_hosts: list[str] | None, skip_checks: bool) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    results = {}

    if skip_checks or not site.get("checks"):
        results["project_checks"] = {"ok": True, "skipped": True}
    else:
        rows = []
        for cmd in site.get("checks"):
            p = subprocess.run(shlex.split(cmd), cwd=site.root, capture_output=True, text=True)
            rows.append({"cmd": cmd, "exit": p.returncode, "tail": (p.stdout + p.stderr).strip().splitlines()[-5:]})
        results["project_checks"] = {"ok": all(r["exit"] == 0 for r in rows), "runs": rows}

    old = json.loads((design / "usage.json").read_text())
    new = tokens.extract(site)
    known = {(o["kind"], o["value"]) for o in old["offtoken"]}
    known_fonts = {f["family"] for f in old["fonts"]["hardcoded"]}
    added = [{"value": o["value"], "uses": o["uses"][:5]} for o in new["offtoken"] if (o["kind"], o["value"]) not in known]
    added_fonts = [f["family"] for f in new["fonts"]["hardcoded"] if f["family"] not in known_fonts and not f["in_tokens"]]
    results["outside_tokens"] = {"ok": not added and not added_fonts, "new_values": added, "new_fonts": added_fonts}

    was, now = pairs(old), pairs(new)
    broke = sorted(k for k, r in now.items() if r < 4.5 and was.get(k, 99) >= 4.5)
    lost = sorted(k for k in was if k not in now)  # a pair that can no longer be measured is not a pass
    results["contrast"] = {"ok": not broke and not lost,
                           "newly_failing": [{"context": c, "fg": f, "bg": b, "ratio": round(now[(c, f, b)], 2)}
                                             for c, f, b in broke],
                           "no_longer_measured": [{"context": c, "fg": f, "bg": b} for c, f, b in lost]}

    before = json.loads((baseline / "shots" / "manifest.json").read_text())
    after = shoot.shoot(site, out / "shots", runs=1, pages=before["pages"], hosts=before["hosts"],
                        sizes=[tuple(int(v) for v in s.split("x")) for s in before["sizes"]], modes=before["modes"])
    d = diff.run(baseline / "shots", out / "shots", out / "diff", only_stable=True)
    changed = [r["file"] for r in d["results"] if r["changed_pixels"]]
    wrong_host = [f for f in changed if expect_hosts and f.split("/")[0] not in expect_hosts]
    results["pixels"] = {"ok": not wrong_host and not d["only_in_before"] and not d["only_in_after"]
                         and not d["skipped_unstable"],  # an unstable baseline shot checks nothing: mask it, shoot again
                         "changed": changed, "outside_expected_hosts": wrong_host,
                         "skipped_unstable": d["skipped_unstable"], "review": str(out / "diff" / "index.html")}

    was = {s["file"]: s for s in before["shots"]}
    new_over = [s["file"] for s in after["shots"] if s["overflow"] and not was.get(s["file"], {}).get("overflow")]
    new_err = [s["file"] for s in after["shots"] if (s["status"] or 0) >= 400 and (was.get(s["file"], {}).get("status") or 0) < 400]
    wrong_mode = [s["file"] for s in after["shots"] if not s.get("mode_ok", True)]
    results["overflow_and_status"] = {"ok": not new_over and not new_err and not after["errors"] and not wrong_mode,
                                      "new_overflow": new_over, "new_errors": new_err, "fetch_errors": after["errors"],
                                      "wrong_mode": wrong_mode}

    seo_file = baseline / "seo.json"
    if seo_file.exists():
        facts = livecheck.seo(site, livecheck.Source(site, False), before["pages"])  # pages per host, as shot
        lines = livecheck.diff_facts(json.loads(seo_file.read_text()), facts, "baseline", "now")
        results["seo"] = {"ok": not lines, "differences": lines}
    else:
        results["seo"] = {"ok": False, "differences": [f"no {seo_file}: run livecheck.py seo first"]}

    results["ok"] = all(v["ok"] for v in results.values() if isinstance(v, dict))
    (out / "verify.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default="tools/site.json")
    ap.add_argument("--baseline", default="baseline")
    ap.add_argument("--design", default="design")
    ap.add_argument("--out", default="review")
    ap.add_argument("--expect-hosts", nargs="*")
    ap.add_argument("--skip-checks", action="store_true")
    args = ap.parse_args()
    r = run(Site(args.site), Path(args.baseline), Path(args.design), Path(args.out), args.expect_hosts, args.skip_checks)
    for k, v in r.items():
        if isinstance(v, dict):
            detail = {kk: vv for kk, vv in v.items() if kk not in ("ok", "runs") and vv}
            print(f"{'PASS' if v['ok'] else 'FAIL'} {k}" + (f": {json.dumps(detail, ensure_ascii=False)[:400]}" if detail else ""))
    print(f"{len(r['pixels']['changed'])} shots changed -> {r['pixels']['review']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
