"""Run the takeover dry runs with headless Claude Code, with and without The Ex-Designer skill.

Each run starts in its own empty folder under the system temp directory, with the user's real setup: their
instructions, settings, hooks and skills. `--tools Read,Skill` leaves no tool that runs commands, writes, searches or
opens the network (Glob and Grep are left out: a deny rule for Read does not bind them); `--strict-mcp-config` loads no MCP server; reading anything in the home folder is denied, so a run
cannot find this repository, its plan or the pilot's code. The skill listing budget is raised for both configs: with
the user's 200+ skills the default budget shows most skills by name only. The with-skill folder holds one thing more:
a copy of src/ex-designer as the project skill `.claude/skills/ex-designer`.
(`claude --restricted` is not used: it loads no skills at all, not even the project's.)

Writes, per eval and config, <iteration>/eval-<id>-<name>/<config>/run-1/:
  outputs/RESPONSE.md   the final answer (the only file the judge sees)
  transcript.jsonl      the stream-json transcript (tool calls; never shown to the judge; not committed: it holds
                        the user's setup and e-mail address)
  timing.json           duration, cost, turns, tools used and the skills invoked

Usage: python3 tests/eval/run.py <iteration-dir> [--configs without_skill,with_skill] [--evals 1,2] [--model opus]
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SKILL = REPO / "src" / "ex-designer"
DATA = json.loads((HERE / "evals.json").read_text())


def prompt_of(e: dict) -> str:
    return f"{e['prompt']}\n\n{DATA['dry_run']}\n\nVastauslista:\n{e['answer_sheet']}\n"


def run_one(it: Path, e: dict, config: str, model: str) -> str:
    run = it / f"eval-{e['id']}-{e['name']}" / config / "run-1"
    if run.exists():
        shutil.rmtree(run)
    (run / "outputs").mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix="takeover-"))
    if config == "with_skill":
        shutil.copytree(SKILL, work / ".claude" / "skills" / "ex-designer", ignore=shutil.ignore_patterns("__pycache__"))
    cmd = ["claude", "-p", "--settings", json.dumps({"skillListingBudgetFraction": 0.05}),
           "--tools", "Read,Skill", "--disallowedTools", f"Read(/{Path.home()}/**)", "--strict-mcp-config",
           "--no-chrome", "--no-session-persistence", "--permission-prompts", "none", "--output-format", "stream-json",
           "--verbose", "--model", model, "--effort", "high", prompt_of(e)]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    seconds = round(time.time() - t0, 1)
    shutil.rmtree(work, ignore_errors=True)
    (run / "transcript.jsonl").write_text(p.stdout)
    events = [json.loads(l) for l in p.stdout.splitlines() if l.strip().startswith("{")]
    result = next((ev for ev in reversed(events) if ev.get("type") == "result"), {})
    tools, skills = {}, []
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                tools[block["name"]] = tools.get(block["name"], 0) + 1
                if block["name"] == "Skill":
                    skills.append(block.get("input", {}).get("skill") or block.get("input", {}).get("command"))
    (run / "outputs" / "RESPONSE.md").write_text((result.get("result") or "").strip() + "\n")
    timing = {"config": config, "model": model, "seconds": seconds, "exit": p.returncode,
              "is_error": result.get("is_error"), "cost_usd": result.get("total_cost_usd"),
              "turns": result.get("num_turns"), "tools": tools, "skills_invoked": skills,
              "permission_denials": len(result.get("permission_denials") or []),
              "usage": result.get("usage"), "stderr_tail": p.stderr[-400:]}
    (run / "timing.json").write_text(json.dumps(timing, indent=1) + "\n")
    return f"eval {e['id']} {e['name']} {config}: exit {p.returncode}, {seconds} s, skills {skills or '-'}, tools {tools or '-'}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("iteration")
    ap.add_argument("--configs", default="without_skill,with_skill")
    ap.add_argument("--evals")
    ap.add_argument("--model", default="opus")
    args = ap.parse_args()
    configs = args.configs.split(",")
    if "with_skill" in configs and not (SKILL / "SKILL.md").exists():
        raise SystemExit(f"No skill at {SKILL}: run without_skill only, or build the skill first.")
    wanted = {int(x) for x in args.evals.split(",")} if args.evals else None
    it = Path(args.iteration)
    jobs = [(e, c) for e in DATA["evals"] if not wanted or e["id"] in wanted for c in configs]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for line in pool.map(lambda j: run_one(it, j[0], j[1], args.model), jobs):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
