"""The newcomer test of step 8: can a fresh agent with only the handed-over project folder maintain the site?

build  makes the handover kit of the invented two-brand site (tests/fixtures/code-site) in a new folder: the site, the
       skill's scripts in tools/ (as step 8 copies them), tools/serve.py, CLAUDE.md, systems.md, design/ and a baseline
       (3 identical runs), committed to a new git repository. The evidence the scorer trusts (the baseline commit,
       the shot hashes, the SEO facts, the design usage, the token file) goes to a folder next to the kit, outside it.
score  scores the four jobs from the committed work (HEAD), the evidence and the scripts:
       0 the baseline commit is still in HEAD's history and nothing is left uncommitted; else jobs 1-3 fail
       1 Beta Labs' accent is #7c2d12 (any CSS colour form) in its own token block, Alpha Studio's is unchanged, the
         baseline shots still match the evidence's hashes, and verify.py passes with only beta.invalid expected to
         change
       2 a commit makes Georgia the sans font through the token (--font-sans), and no commit adds a font outside the
         token file. The invented site's served stylesheet hard-codes its font (a planted trap of run_all.py), so job 2
         scores the token change, not the pixels
       3 a later commit rolls that one back with history kept: HEAD's font token is as before, the font commit is an
         ancestor of HEAD, and no Georgia is left in the sources
       4 answers/contact-form.md, committed, names Mailroute, its key MAILROUTE_KEY, where the key lives (Pilvi), the
         sending log and the owner's yes for a test send. A keyword rubric: it checks that the answer comes from
         systems.md, not that every sentence in it is right
run    builds a kit in a temp folder, gives a fresh headless Claude Code the four jobs and nothing else (0 hints), then
       scores it. Writes <out>/score.json, timing.json, the git log and the answer; the transcript stays out of Git (it
       holds the user's setup). Spends Claude usage. Isolation is by tool rules, not an OS sandbox: Read is denied in
       the home folder and Bash is limited to a list of commands, but python3 can still read files, so run it only
       with a trusted model and this fixed prompt. Every process of the run is stopped at the end.

Usage: python3 tests/newcomer/newcomer.py build <dir> | score <dir> [--evidence <dir>] | run <out-dir> [--model opus]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
SKILL = TESTS.parent / "src" / "ex-designer"
FIXTURE = TESTS / "fixtures" / "code-site"
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(SKILL / "scripts"))
import fixture_server  # noqa: E402
import livecheck  # noqa: E402
import shoot  # noqa: E402
import tokens  # noqa: E402
import verify  # noqa: E402
from lib import color as C  # noqa: E402
from lib.site import Site  # noqa: E402

TARGET = "#7c2d12"
PORT = 8787
TIMEOUT = 45 * 60
JOBS = f"""You maintain the website in this folder. Do these four jobs, one commit each:

1. Change Beta Labs' accent colour to {TARGET}. Alpha Studio must not change.
2. Make Georgia the site's sans-serif font (Georgia, serif).
3. The font change was a mistake: roll it back.
4. The contact form stopped sending. Write what to do now in answers/contact-form.md.
"""
IGNORE = "baseline/shots/*\n!baseline/shots/manifest.json\nreview/\n__pycache__/\n"
ANSWER = ["mailroute", "mailroute_key", "pilvi", "log", "owner", "yes"]


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def token(css: str, selector: str, name: str) -> str | None:
    """The value of --name in the first block that opens with selector (no nesting inside the blocks we read)."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    v = m and re.search(rf"--{re.escape(name)}\s*:\s*([^;]+);", m.group(1))
    return v.group(1).strip() if v else None


def colour(value: str | None) -> str | None:
    c = C.parse(value) if value else None
    return C.hex(c) if c else None


def first_font(value: str | None) -> str:
    fams = tokens.families(value) if value else []
    return tokens.norm_font(fams[0]) if fams else ""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def served(root: Path):
    server, base, _ = fixture_server.start(root)
    site = Site(root / "tools" / "site.json")
    site.data["serve"]["url"] = base
    return server, site


def evidence_of(dest: Path) -> Path:
    return dest.parent / f"{dest.name}-evidence"


def build(dest: Path, evidence: Path | None = None) -> Path:
    evidence = evidence or evidence_of(dest)
    if dest.exists() or evidence.exists():
        raise SystemExit(f"{dest} or {evidence} exists: give a new folder")
    shutil.copytree(FIXTURE, dest)
    tools_dir = dest / "tools"
    for p in (SKILL / "scripts").glob("*.py"):
        shutil.copy2(p, tools_dir / p.name)
    shutil.copytree(SKILL / "scripts" / "lib", tools_dir / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(TESTS / "fixture_server.py", tools_dir / "serve.py")
    data = json.loads((tools_dir / "site.json").read_text())
    data["serve"] = {"url": f"http://127.0.0.1:{PORT}", "start": "python3 tools/serve.py"}
    (tools_dir / "site.json").write_text(json.dumps(data, indent=2) + "\n")
    shutil.copy2(HERE / "project-CLAUDE.md", dest / "CLAUDE.md")
    shutil.copy2(HERE / "systems.md", dest / "systems.md")
    (dest / ".gitignore").write_text(IGNORE)

    server, site = served(dest)
    try:
        m = shoot.shoot(site, dest / "baseline" / "shots", runs=3)
        shaky = [s["file"] for s in m["shots"] if not s["stable"]]
        if shaky:
            raise SystemExit(f"unstable baseline shots: {shaky}")
        facts = livecheck.seo(site, livecheck.Source(site, False), m["pages"])
        (dest / "baseline" / "seo.json").write_text(json.dumps(facts, indent=1) + "\n")
        data = tokens.extract(site)
        (dest / "design").mkdir()
        (dest / "design" / "usage.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        (dest / "design" / "tokens.json").write_text(json.dumps(tokens.dtcg(data), indent=1, ensure_ascii=False) + "\n")
    finally:
        server.shutdown()
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "-c", "user.name=Takeover", "-c", "user.email=takeover@example.invalid", "commit", "-q", "-m",
        "Baseline of the takeover")
    evidence.mkdir(parents=True)
    (evidence / "base.txt").write_text(git(dest, "rev-parse", "HEAD") + "\n")
    for rel in ("baseline/shots/manifest.json", "baseline/seo.json", "design/usage.json", "app/globals.css"):
        shutil.copy2(dest / rel, evidence / Path(rel).name)
    return dest


def job(fn) -> dict:
    """One job's score; a missing or broken file in the submission fails that job, never the scorer."""
    try:
        ok, detail = fn()
    except (OSError, ValueError, KeyError, StopIteration, SystemExit, subprocess.CalledProcessError) as e:
        ok, detail = False, f"error: {type(e).__name__}: {str(e)[:200]}"
    return {"ok": bool(ok), "detail": detail}


def score(root: Path, evidence: Path | None = None) -> dict:
    root = root.resolve()
    ev = (evidence or evidence_of(root)).resolve()
    base = (ev / "base.txt").read_text().strip()
    css0 = (ev / "globals.css").read_text()
    in_history = subprocess.run(["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=root,
                                capture_output=True).returncode == 0
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout.split("\n")
    dirty = [l for l in dirty if l.strip()]
    sound = in_history and not dirty
    why = "" if sound else ("the baseline commit is gone from history; " if not in_history else "") + (
        f"{len(dirty)} uncommitted changes; " if dirty else "")
    css_at = lambda rev: git(root, "show", f"{rev}:app/globals.css")  # noqa: E731
    jobs = {}

    def job1():
        css = css_at("HEAD")
        beta, alpha = token(css, '[data-brand="beta"]', "accent"), token(css, ":root", "accent")
        manifest = json.loads((ev / "manifest.json").read_text())
        shots = root / "baseline" / "shots"
        moved = [s["file"] for s in manifest["shots"]
                 if not (shots / s["file"]).is_file() or sha(shots / s["file"]) != s["sha256"]]
        if moved or not sound:
            return False, why + f"baseline shots moved {len(moved)}"
        work = Path(tempfile.mkdtemp(prefix="newcomer-score-"))
        try:
            (work / "baseline").mkdir()
            shutil.copytree(shots, work / "baseline" / "shots")
            shutil.copy2(ev / "manifest.json", work / "baseline" / "shots" / "manifest.json")
            shutil.copy2(ev / "seo.json", work / "baseline" / "seo.json")
            (work / "design").mkdir()
            shutil.copy2(ev / "usage.json", work / "design" / "usage.json")
            server, site = served(root)
            try:
                r = verify.run(site, work / "baseline", work / "design", work / "review", ["beta.invalid"], True)
            finally:
                server.shutdown()
        finally:
            shutil.rmtree(work, ignore_errors=True)
        changed = r["pixels"]["changed"]
        failed = [k for k, v in r.items() if isinstance(v, dict) and not v["ok"]]
        ok = (colour(beta) == TARGET and alpha == token(css0, ":root", "accent") and r["ok"] and bool(changed)
              and all(f.startswith("beta.invalid/") for f in changed))
        return ok, (f"beta accent {beta}, alpha accent {alpha}; baseline shots moved 0; verify "
                    f"{'pass' if r['ok'] else 'FAIL ' + ', '.join(failed)}; {len(changed)} shots changed, "
                    f"{sum(not f.startswith('beta.invalid/') for f in changed)} outside beta")

    def font_of(rev: str) -> str:
        try:
            return first_font(token(css_at(rev), "@theme inline", "font-sans"))
        except subprocess.CalledProcessError:  # a commit without the token file
            return ""
    commits = git(root, "rev-list", "--reverse", f"{base}..HEAD").split() if in_history else []
    font_commit = next((c for c in commits if font_of(c) == "georgia"), None)

    def job2():
        patch = git(root, "log", "-p", "--format=", f"{base}..HEAD", "--", "app", "components", "lib",
                    ":!app/globals.css") if in_history else ""
        hard = [l for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")
                and re.search(r"georgia|font-family|fontfamily", l, re.I)]
        return (sound and bool(font_commit) and not hard,
                why + f"font commit {font_commit[:7] if font_commit else 'none'}; fonts added outside the token file: "
                      f"{len(hard)}")

    def job3():
        font0, font_now = token(css0, "@theme inline", "font-sans"), token(css_at("HEAD"), "@theme inline", "font-sans")
        kept = bool(font_commit) and subprocess.run(["git", "merge-base", "--is-ancestor", font_commit, "HEAD"],
                                                    cwd=root).returncode == 0
        head = git(root, "rev-parse", "HEAD")
        left = subprocess.run(["git", "grep", "-il", "georgia", "HEAD", "--", "app", "components", "lib"], cwd=root,
                              capture_output=True, text=True).stdout.split()
        return (sound and kept and head != font_commit and font_now == font0 and not left,
                why + f"font token now {font_now!r} (before {font0!r}); font commit in history: {kept}; Georgia left in "
                      f"{left or 'no file'}")

    def job4():
        text = git(root, "show", "HEAD:answers/contact-form.md").lower()
        missing = [w for w in ANSWER if w not in text]
        return not missing, f"missing: {missing or 'nothing'}"

    for n, fn in ((1, job1), (2, job2), (3, job3), (4, job4)):
        jobs[n] = job(fn)
    return {"passed": sum(j["ok"] for j in jobs.values()), "jobs": jobs}


def port_users() -> list[str]:
    p = subprocess.run(["lsof", "-ti", f"tcp:{PORT}", "-sTCP:LISTEN"], capture_output=True, text=True)
    return p.stdout.split()


def listeners() -> list[str]:
    p = subprocess.run(["lsof", "-t", "-iTCP", "-sTCP:LISTEN"], capture_output=True, text=True)
    return sorted(set(p.stdout.split()))


def cwd_of(pid: str) -> str:
    p = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], capture_output=True, text=True)
    return next((l[1:] for l in p.stdout.splitlines() if l.startswith("n")), "")


def run(out: Path, model: str) -> dict:
    if port_users():
        raise SystemExit(f"port {PORT} is in use: stop that server first")
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="newcomer-"))
    kit = build(work / "site")
    allowed = ["Read", "Edit", "Write", "Glob", "Grep"] + [f"Bash({c}:*)" for c in (
        "python3", "git", "ls", "cat", "head", "tail", "grep", "sed", "find", "diff", "mkdir", "lsof", "kill", "sleep",
        "echo", "wc")]
    cmd = ["claude", "-p", "--tools", "Bash,Read,Edit,Write,Glob,Grep", "--allowedTools", *allowed,
           "--disallowedTools", f"Read(/{Path.home()}/**)", "--strict-mcp-config", "--no-chrome",
           "--no-session-persistence", "--permission-prompts", "none", "--output-format", "stream-json", "--verbose",
           "--model", model, JOBS]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=kit, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate(timeout=60)
        stderr += f"\nstopped after {TIMEOUT} s"
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # background shells the agent started
        except (ProcessLookupError, PermissionError):
            pass
        for pid in listeners():  # a server that left the group, on any port, if it runs from the kit
            if any(cwd_of(pid).startswith(str(w)) for w in (work, work.resolve())):
                subprocess.run(["kill", "-9", pid])
    seconds = round(time.time() - t0, 1)
    try:
        (out / "transcript.jsonl").write_text(stdout)
        events = [json.loads(l) for l in stdout.splitlines() if l.strip().startswith("{")]
        result = next((ev for ev in reversed(events) if ev.get("type") == "result"), {})
        s = score(kit)
        s["hints"] = 0
        (out / "score.json").write_text(json.dumps(s, indent=1) + "\n")
        (out / "git-log.txt").write_text(git(kit, "log", "--stat", "--format=%h %s") + "\n")
        if (kit / "answers" / "contact-form.md").is_file():
            shutil.copy2(kit / "answers" / "contact-form.md", out / "contact-form.md")
        (out / "timing.json").write_text(json.dumps({
            "model": model, "seconds": seconds, "exit": proc.returncode, "turns": result.get("num_turns"),
            "cost_usd": result.get("total_cost_usd"), "permission_denials": len(result.get("permission_denials") or []),
            "stderr_tail": stderr[-400:]}, indent=1) + "\n")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["build", "score", "run"])
    ap.add_argument("dir")
    ap.add_argument("--evidence")
    ap.add_argument("--model", default="opus")
    args = ap.parse_args()
    if args.command == "build":
        kit = build(Path(args.dir), Path(args.evidence) if args.evidence else None)
        print(f"kit built in {kit}; evidence in {Path(args.evidence) if args.evidence else evidence_of(kit)}")
        return 0
    if args.command == "score":
        s = score(Path(args.dir), Path(args.evidence) if args.evidence else None)
    else:
        s = run(Path(args.dir), args.model)
    for n, j in s["jobs"].items():
        print(f"JOB {n} {'PASS' if j['ok'] else 'FAIL'} {j['detail']}")
    print(f"{s['passed']}/4 jobs")
    return 0 if s["passed"] == 4 else 1


if __name__ == "__main__":
    sys.exit(main())
