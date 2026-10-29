# Security scan of the skill folder

`skillspector scan src/snatcher --no-llm` (SkillSpector 2.13.0), 2026-10-28, before the skill was linked into
`~/.claude/skills/snatcher`. Every flagged line was read. One real defect was fixed (the first row); the other 19
issues are pattern matches on code that does the safe thing. Score 100/100 "do not install" comes from the count of
these matches, not from a confirmed risk.

| Flag | Where | What the line does | Verdict |
|---|---|---|---|
| manifest_parse_error | `SKILL.md:3` | The description held `: ` in an unquoted value, which is not valid YAML | **Fixed**: the description is quoted; js-yaml parses it |
| PE3 credential access (×7) | `scripts/lib/site.py:31-32,64`, `scripts/brandbook.py:145` | The list of secret file names the scripts **refuse** to read (`.env`, `*.pem`, `*.key`, …), matched in any letter case | False positive: a denylist, not access |
| TM1 tool parameter abuse (×2) | `scripts/verify.py:4,103` | The option name `--skip-checks` | False positive: it skips the project's own lint and test commands; nothing runs with more rights |
| LP3 no tool scope | `SKILL.md:1` | The skill declares no `allowed-tools` | Kept: in Claude Code `allowed-tools` pre-approves tools, so declaring it would widen what runs without asking |
| AE4 mixed script | `references/code-site.md:1` | En dashes and middle dots in headings (`4–6`, `4a · …`) | False positive: typography, no lookalike letters |
| RP1 unpinned MCP server (×3) | `references/*.md`, `scripts/lib/site.py:9` | `npx wrangler …` commands | False positive: Wrangler is the site's own CLI from its `package.json`, not an MCP server |
| AST4 subprocess (×3) | `scripts/brandbook.py:1861`, `scripts/tokens.py:676`, `scripts/verify.py:44` | Chrome print to PDF with no network; `git rev-parse`; the project's own check commands from `site.json` | Safe: argument lists, never `shell=True` |
| SSRF3 dynamic request target (×2) | `scripts/livecheck.py:141`, `scripts/shoot.py:73` | A request to a host named in `site.json`, or to the local build on 127.0.0.1 | Safe by design: the hosts are the owner's own; every other request is blocked (run_all checks 6, 13, 14) |
