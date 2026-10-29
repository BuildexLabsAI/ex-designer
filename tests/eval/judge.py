"""Blind judging of the dry runs by Codex (high reasoning effort, read-only).

A/B mode (default): both runs of an eval go into a packet as A and B in random order; the mapping stays outside the
packet. Codex grades every assertion for each side, scores both and names a winner.
Single mode (--single <config>): one run is graded alone, as A (used for the baseline, before the skill exists).
The packet copies are redacted: the skill's name becomes "[guide]", so a side cannot be recognised by it.
Writes grading.json into each judged run, comparison.json per eval (A/B mode) and <iteration>/summary.md.

Usage: python3 tests/eval/judge.py <iteration-dir> [--evals 1,2] [--single without_skill]
"""
import argparse
import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "evals.json").read_text())

SIDE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["assertions", "score", "strengths", "weaknesses"],
    "properties": {
        "assertions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["n", "passed", "evidence"],
                "properties": {"n": {"type": "integer"}, "passed": {"type": "boolean"}, "evidence": {"type": "string"}},
            },
        },
        "score": {"type": "integer"},
        "strengths": {"type": "string"},
        "weaknesses": {"type": "string"},
    },
}


def schema(labels: list[str]) -> dict:
    props = {label: SIDE for label in labels}
    req = list(labels)
    if len(labels) > 1:
        props |= {"winner": {"type": "string", "enum": [*labels, "tie"]}, "reason": {"type": "string"}}
        req += ["winner", "reason"]
    return {"type": "object", "additionalProperties": False, "required": req, "properties": props}


PROMPT = """You are an impartial judge. {who} did the same task for the same user. Judge {how}.

Read task.md first. Then read {files}. The task is a dry run: the candidate writes a plan and runs nothing, so judge
the plan as written: its steps, their order, the commands it names and the questions it asks.

For every numbered assertion in task.md, decide for each candidate separately: passed is true only when the plan
clearly satisfies it; give short evidence (a short quote, or what is missing). An assertion about an order ("before
any edit") fails when the plan does the later thing first or never does the earlier thing. Then score each candidate
1 to 10 for how well it serves this user, and name what is strong and weak in a sentence each.{winner} Do not reward
length. Do not guess which candidate had which tools. Output only JSON matching the schema."""


def task_md(e: dict) -> str:
    lines = [f"# Task {e['id']}: {e['name']}", "", "## The user's message", "", e["prompt"], "", "## The dry-run rule",
             "", DATA["dry_run"], "", "## The user's answers (stand-in for the interview)", "", e["answer_sheet"], "",
             "## What a good result looks like", "", e["expected_output"], "", "## Assertions", ""]
    lines += [f"{i}. {a}" for i, a in enumerate(e["assertions"], 1)]
    return "\n".join(lines) + "\n"


def redact(folder: Path):
    for f in folder.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".txt", ".json", ".html"):
            f.write_text(re.sub(r"snatcher|ex-designer", "[guide]", f.read_text(), flags=re.I))


def grade(run: Path, e: dict, side: dict, label: str):
    exps = []
    for i, text in enumerate(e["assertions"], 1):
        a = next((x for x in side["assertions"] if x["n"] == i), {"passed": False, "evidence": "not graded"})
        exps.append({"n": i, "text": text, "passed": bool(a["passed"]), "evidence": a["evidence"]})
    passed = sum(x["passed"] for x in exps)
    out = {"expectations": exps,
           "summary": {"passed": passed, "failed": len(exps) - passed, "total": len(exps),
                       "pass_rate": round(passed / len(exps), 2)},
           "judge": {"by": "codex exec, high reasoning effort, blind", "label": label, "score": side["score"],
                     "strengths": side["strengths"], "weaknesses": side["weaknesses"]}}
    (run / "grading.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")


def judge_one(it: Path, e: dict, configs: list[str], rng: random.Random) -> bool:
    ed = next(it.glob(f"eval-{e['id']}-*"), None)
    runs = {c: ed / c / "run-1" for c in configs} if ed else {}
    if not runs or not all((r / "outputs" / "RESPONSE.md").exists() for r in runs.values()):
        print(f"eval {e['id']}: not complete, skipped")
        return False
    order = list(configs)
    rng.shuffle(order)
    labels = ["A", "B"][:len(order)]
    mapping = dict(zip(labels, order))
    packet = it / "judge" / (f"eval-{e['id']}" + ("" if len(labels) > 1 else f"-{order[0]}"))
    if packet.exists():
        shutil.rmtree(packet)
    packet.mkdir(parents=True)
    for label, cfg in mapping.items():
        shutil.copytree(runs[cfg] / "outputs", packet / label)
    redact(packet)
    (packet / "task.md").write_text(task_md(e))
    (packet / "schema.json").write_text(json.dumps(schema(labels)))
    if len(labels) > 1:
        prompt = PROMPT.format(who="Two candidates, A and B,", how="them blind", files="A/RESPONSE.md and B/RESPONSE.md",
                               winner=" Name the winner (or tie) with a one-sentence reason.")
    else:
        prompt = PROMPT.format(who="One candidate, A,", how="it", files="A/RESPONSE.md", winner="")
    cmd = ["nice", "-n", "20", "codex", "exec", "-C", str(packet), "-s", "read-only", "--skip-git-repo-check",
           "-c", "model_reasoning_effort=high", "--output-schema", str(packet / "schema.json"),
           "-o", str(packet / "judge.json")]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True)
    (packet / "codex.log").write_text(f"exit {p.returncode}\n--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}")
    if p.returncode or not (packet / "judge.json").exists():
        print(f"eval {e['id']}: codex failed: {p.stderr[-600:]}")
        return False
    verdict = json.loads((packet / "judge.json").read_text())
    for label, cfg in mapping.items():
        grade(runs[cfg], e, verdict[label], label)
    if len(labels) > 1:
        winner = verdict["winner"] if verdict["winner"] == "tie" else mapping[verdict["winner"]]
        comparison = {"eval": e["name"], "mapping": mapping, "winner": winner, "reason": verdict["reason"],
                      "scores": {mapping[x]: verdict[x]["score"] for x in labels}}
        (ed / "comparison.json").write_text(json.dumps(comparison, indent=1, ensure_ascii=False) + "\n")
        print(f"eval {e['id']} {e['name']}: winner {winner}; scores {comparison['scores']}")
    else:
        print(f"eval {e['id']} {e['name']}: graded {order[0]} alone")
    return True


def summary(it: Path):
    lines = ["# Eval summary", "", "| Eval | Config | Passed | Failed assertions | Judge score |", "|---|---|---|---|---|"]
    for e in DATA["evals"]:
        for g in sorted(it.glob(f"eval-{e['id']}-*/*/run-1/grading.json")):
            d = json.loads(g.read_text())
            failed = ", ".join(str(x["n"]) for x in d["expectations"] if not x["passed"]) or "-"
            s = d["summary"]
            lines.append(f"| {e['id']} {e['name']} | {g.parent.parent.name} | {s['passed']}/{s['total']} | {failed} | "
                         f"{d['judge']['score']} |")
    (it / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("iteration")
    ap.add_argument("--evals")
    ap.add_argument("--single")
    args = ap.parse_args()
    it = Path(args.iteration)
    wanted = {int(x) for x in args.evals.split(",")} if args.evals else None
    configs = [args.single] if args.single else ["with_skill", "without_skill"]
    rng = random.Random(20261027)
    for e in DATA["evals"]:
        if wanted and e["id"] not in wanted:
            rng.random()
            continue
        judge_one(it, e, configs, rng)
    summary(it)
    return 0


if __name__ == "__main__":
    sys.exit(main())
