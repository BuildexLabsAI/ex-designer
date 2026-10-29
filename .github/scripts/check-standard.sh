#!/usr/bin/env bash
# BuildexLabsAI repository standard check.
#
# The canonical copy is src/check-standard.sh in BuildexLabsAI/.github. Every repository carries
# a copy at .github/scripts/check-standard.sh; CI warns when that copy is out of date.
#
#   check-standard.sh                   whole repository: tracked files plus new, unignored ones
#   check-standard.sh --staged          files staged for commit (git pre-commit hook)
#   check-standard.sh --hook            Claude Code PreToolUse hook: reads the tool call on stdin
#   check-standard.sh --canonical DIR   also compare this repo's copies with those in DIR (CI)
#
# CI passes the pull request title and branch in STANDARD_PR_TITLE and STANDARD_BRANCH.
# Exit codes: 0 = no errors, 1 = errors found, 2 = hook mode blocked the write.
# Written for bash 3.2 (macOS) as well as bash 5 (Linux CI).

export LC_ALL=C

# Besides letters, digits and . _ - this allows the route symbols frameworks put in file names:
# [slug] (group) @slot +page $param {-$optional}.
# shellcheck disable=SC2016  # the $ is a literal character here, not an expansion
NAME_RE='^[][A-Za-z0-9._@+()${}-]+$'
KEBAB_RE='^[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+)*$'
TITLE_RE='^(feat|fix|docs|chore|refactor|test|perf|ci|build|style|revert)(\([a-z0-9._/-]+\))?!?: [^ ]'
BRANCH_RE='^(feat|fix|docs|chore|refactor|test|perf|ci|build|style|revert|claude|codex|dependabot)/[^ ]+$'
KNOWN_DIRS=' src tests docs scripts public static supabase '
TOP_DOCS=' README.md AGENTS.md CLAUDE.md DECISIONS.md CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md SUPPORT.md LICENSE.md CLAUDE.local.md '
EXCEPTIONS_FILE=.github/standard-exceptions
SOURCE='BuildexLabsAI/.github'

mode=full
canonical=
errors=0
warnings=0
exceptions=()
paths=()
seen_dirs=' '
kind=

# --- output -------------------------------------------------------------------------------

gh_escape() { # text for a GitHub workflow command message
  local s=$1
  s=${s//\%/%25}; s=${s//$'\r'/%0D}; s=${s//$'\n'/%0A}
  printf '%s' "$s"
}

gh_escape_prop() { # text for a GitHub workflow command property (file=...)
  local s
  s=$(gh_escape "$1")
  s=${s//:/%3A}; s=${s//,/%2C}
  printf '%s' "$s"
}

report() { # LEVEL PATH MESSAGE — LEVEL is error or warning; PATH may be empty
  local level=$1 path=$2 msg=$3 tag
  if [ "$mode" = hook ] && [ "$level" = warning ]; then return; fi
  if [ "$level" = error ]; then errors=$((errors + 1)); else warnings=$((warnings + 1)); fi
  if [ "${GITHUB_ACTIONS:-}" = true ]; then
    if [ -n "$path" ]; then
      printf '::%s file=%s::%s\n' "$level" "$(gh_escape_prop "$path")" "$(gh_escape "$msg")" >&3
    else
      printf '::%s::%s\n' "$level" "$(gh_escape "$msg")" >&3
    fi
    return
  fi
  tag='ERROR  '; [ "$level" = warning ] && tag='warning'
  if [ -n "$path" ]; then printf '%s %s: %s\n' "$tag" "$path" "$msg" >&3
  else printf '%s %s\n' "$tag" "$msg" >&3; fi
}

kebab_of() { # suggested kebab-case spelling of a name
  printf '%s' "$1" | tr 'A-Z_ ' 'a-z--' | tr -s -
}

# --- exceptions ---------------------------------------------------------------------------

# shellcheck disable=SC2094  # report only names the file in a message; it never writes to it
load_exceptions() {
  [ -f "$EXCEPTIONS_FILE" ] || return 0
  local line pattern reason n=0
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    line=${line%$'\r'}
    line=${line#"${line%%[![:space:]]*}"}
    case "$line" in ''|'#'*) continue ;; esac
    pattern=${line%%[[:space:]#]*}
    reason=
    case "$line" in *'#'*) reason=${line#*'#'} ;; esac
    reason=${reason#"${reason%%[![:space:]]*}"}
    if [ -z "$reason" ]; then
      report error "$EXCEPTIONS_FILE" "Line $n: \"$pattern\" has no reason. Write it as: <path>  # <why it is needed>"
      continue
    fi
    exceptions+=("$pattern")
  done < "$EXCEPTIONS_FILE"
}

is_excepted() { # PATH — true when a pattern in .github/standard-exceptions matches it
  local p
  for p in ${exceptions[@]+"${exceptions[@]}"}; do
    # shellcheck disable=SC2053  # unquoted on purpose: the pattern is a glob
    [[ $1 == $p ]] && return 0
  done
  return 1
}

# --- rules for one path -------------------------------------------------------------------

is_conventional_name() { # upper-case names every tool expects, allowed where kebab-case applies
  case "$1" in
    README.md|AGENTS.md|CLAUDE.md|DECISIONS.md|CONTRIBUTING.md|SECURITY.md|CODE_OF_CONDUCT.md|\
    SUPPORT.md|LICENSE|LICENSE.md|LICENSE.txt|NOTICE|CODEOWNERS|CLAUDE.local.md|Dockerfile|\
    Dockerfile.*|Makefile|Procfile|Gemfile|Gemfile.lock|Pipfile|Pipfile.lock|Cargo.toml|\
    Cargo.lock|Brewfile|Justfile|Vagrantfile) return 0 ;;
  esac
  return 1
}

set_kind() { # NAME — sets $kind for file types with their own rule, or empties it
  local name=$1 ext=
  kind=
  case "$name" in *.*) ext=${name##*.} ;; esac
  shopt -s nocasematch
  case "$name" in
    .env.example|.env.sample|.env.template) ;;
    .env|.env.*|id_rsa|id_dsa|id_ecdsa|id_ed25519) kind=secret ;;
    .DS_Store|Thumbs.db|desktop.ini) kind=junk ;;
  esac
  if [ -z "$kind" ]; then
    case "$ext" in
      pem|key|p12|pfx|jks|keystore) kind=secret ;;
      png|jpg|jpeg|gif|webp|avif|svg|ico|bmp|tif|tiff|heic) kind=image ;;
    esac
  fi
  shopt -u nocasematch
}

check_path() { # PATH — name and file-type rules for one repository-relative path
  local path=$1 rest=$1 comp first='' depth=0
  is_excepted "$path" && return 0
  while :; do
    comp=${rest%%/*}
    depth=$((depth + 1))
    [ "$depth" -eq 1 ] && first=$comp
    case "$comp" in
      *[[:space:]]*)
        report error "$path" "\"$comp\" contains a space. Use lowercase kebab-case: $(kebab_of "$comp")"
        return ;;
    esac
    if ! [[ $comp =~ $NAME_RE ]]; then
      report error "$path" "\"$comp\" contains a character that is not allowed (such as ä, ö, &, #, : or a quote). Use a-z, 0-9, dot, dash or underscore."
      return
    fi
    if [ "${comp:0:1}" != . ] && ! is_conventional_name "$comp" &&
       { [ "$depth" -eq 1 ] || [ "$first" = docs ]; } && ! [[ $comp =~ $KEBAB_RE ]]; then
      report error "$path" "\"$comp\" is not lowercase kebab-case; the top level and docs/ use it. Rename it: $(kebab_of "$comp")"
      return
    fi
    [ "$rest" = "$comp" ] && break
    rest=${rest#*/}
  done

  set_kind "$comp"
  case "$kind" in
    '') ;;
    secret) report error "$path" "Secrets never go into git (.env files, keys, certificates). Commit .env.example with placeholders instead, and rotate anything already pushed." ;;
    junk) report error "$path" "Operating system junk file. Delete it and add it to .gitignore." ;;
    image) [ "$depth" -eq 1 ] && report error "$path" "Images do not belong at the top level. App assets go in src/ or public/, other images in docs/." ;;
  esac
  if [ "$depth" -eq 1 ] && [ -z "$kind" ]; then
    case "$comp" in
      *.md) case "$TOP_DOCS" in *" $comp "*) ;; *) report warning "$path" "Loose document at the top level. Move it to docs/." ;; esac ;;
    esac
  fi
}

note_top_dir() { # PATH — warns once about each unexpected top-level folder
  local dir
  case "$1" in */*) dir=${1%%/*} ;; *) return ;; esac
  case "$seen_dirs" in *" $dir "*) return ;; esac
  seen_dirs="$seen_dirs$dir "
  case "$dir" in .*) return ;; esac
  case "$KNOWN_DIRS" in *" $dir "*) return ;; esac
  if is_excepted "$dir" || is_excepted "$dir/" || is_excepted "$dir/-"; then return; fi
  report warning "$dir/" "Unexpected top-level folder. Code goes in src/ and documents in docs/. If a tool needs this folder at the root, list it in $EXCEPTIONS_FILE with the reason."
}

# --- whole-repository rules ---------------------------------------------------------------

check_required() {
  local f
  for f in README.md AGENTS.md CLAUDE.md DECISIONS.md .gitignore; do
    [ -f "$f" ] || report error "$f" "Required file is missing. Copy it from BuildexLabsAI/repo-template."
  done
  if [ -f CLAUDE.md ] && ! grep -qE '^@AGENTS\.md[[:space:]]*$' CLAUDE.md; then
    report error CLAUDE.md "CLAUDE.md must import AGENTS.md with a line that reads exactly: @AGENTS.md"
  fi
  if [ -f AGENTS.md ] && ! { grep -q 'buildexlabs-standard:start' AGENTS.md && grep -q 'buildexlabs-standard:end' AGENTS.md; }; then
    report error AGENTS.md "AGENTS.md lacks the BuildexLabsAI standard block. Copy it from src/agents-block.md in $SOURCE."
  fi
  # core.excludesFile is switched off so a personal global ignore cannot hide a missing rule.
  if [ -f .gitignore ] && ! git -c core.excludesFile=/dev/null check-ignore -q --no-index .env; then
    report error .gitignore ".gitignore must ignore .env so secrets cannot be committed by accident."
  fi
}

check_collisions() { # names in $paths that differ only by letter case, at any folder level
  local a b
  while IFS=$'\t' read -r a b; do
    report error "$b" "\"$b\" and \"$a\" differ only by letter case, which breaks on macOS and Windows. Rename one of them."
  done < <(printf '%s\n' ${paths[@]+"${paths[@]}"} |
    awk -F/ '{ p = ""; for (i = 1; i <= NF; i++) { p = (i == 1) ? $i : p "/" $i; print p } }' |
    sort -u |
    awk '{ l = tolower($0); if (l in seen) { if (seen[l] != $0) print seen[l] "\t" $0 } else seen[l] = $0 }')
}

check_drift() { # DIR — compare this repo's copies with the canonical ones in DIR
  local dir=$1 copy=.github/scripts/check-standard.sh
  if [ -f AGENTS.md ] && grep -q 'buildexlabs-standard:start' AGENTS.md &&
     ! awk '/buildexlabs-standard:start/ { on = 1 } on { print } /buildexlabs-standard:end/ { on = 0 }' AGENTS.md |
       cmp -s - "$dir/agents-block.md"; then
    report warning AGENTS.md "The BuildexLabsAI standard block is out of date. Replace it with the current src/agents-block.md from $SOURCE."
  fi
  if [ ! -f "$copy" ]; then
    report warning "$copy" "Missing, so the Claude Code and git hooks cannot run. Copy src/check-standard.sh from $SOURCE here."
  elif ! cmp -s "$copy" "$dir/check-standard.sh"; then
    report warning "$copy" "This copy is out of date. Replace it with the current src/check-standard.sh from $SOURCE."
  fi
}

check_pull_request() {
  if [ -n "${STANDARD_PR_TITLE:-}" ] && ! [[ $STANDARD_PR_TITLE =~ $TITLE_RE ]]; then
    report error "" "Pull request title \"$STANDARD_PR_TITLE\" does not follow Conventional Commits, e.g. \"feat(api): add athlete height endpoint\". The title becomes the commit on main."
  fi
  if [ -n "${STANDARD_BRANCH:-}" ] && ! [[ $STANDARD_BRANCH =~ $BRANCH_RE ]]; then
    report warning "" "Branch \"$STANDARD_BRANCH\" should start with feat/, fix/, docs/, chore/, refactor/ or test/."
  fi
}

# --- modes --------------------------------------------------------------------------------

run_full() {
  local p
  while IFS= read -r -d '' p; do paths+=("$p"); done < <(git ls-files -z --cached --others --exclude-standard)
  check_required
  for p in ${paths[@]+"${paths[@]}"}; do
    check_path "$p"
    note_top_dir "$p"
  done
  check_collisions
  [ -n "$canonical" ] && check_drift "$canonical"
  check_pull_request
}

run_staged() {
  local base p
  if git rev-parse -q --verify HEAD >/dev/null 2>&1; then base=HEAD
  else base=$(git hash-object -t tree /dev/null); fi   # first commit: compare with nothing
  # Only new names are checked, so a commit that edits an old, non-standard file still goes in.
  while IFS= read -r -d '' p; do
    check_path "$p"
    note_top_dir "$p"
  done < <(git diff --cached --name-only -z --diff-filter=ACR "$base")
  while IFS= read -r -d '' p; do paths+=("$p"); done < <(git ls-files -z)
  check_collisions
}

run_hook() { # blocks Claude Code from creating a file whose name breaks the standard
  local input file_path script_dir root_l root_p rel cur rest comp match entry
  input=$(cat)
  if ! command -v jq >/dev/null 2>&1; then
    echo "check-standard: jq is not installed, so the file-name check was skipped." >&2
    return 0
  fi
  file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
  [ -n "$file_path" ] || return 0
  [ -e "$file_path" ] && return 0   # editing an existing file is never blocked

  # This script lives at <repo>/.github/scripts/; only files inside that repository are checked.
  script_dir=$(cd "$(dirname "$0")" && pwd)
  root_l=${script_dir%/.github/scripts}
  root_p=$(cd "$root_l" && pwd -P)
  case "$file_path" in
    "$root_l"/*) rel=${file_path#"$root_l"/} ;;
    "$root_p"/*) rel=${file_path#"$root_p"/} ;;
    *) return 0 ;;
  esac
  cd "$root_l" || return 0
  git check-ignore -q --no-index -- "$rel" 2>/dev/null && return 0   # never reaches git

  load_exceptions
  check_path "$rel"
  cur=.
  rest=$rel
  while [ "$errors" -eq 0 ]; do   # a new name must not clash by letter case with an existing one
    comp=${rest%%/*}
    match=
    shopt -s nocasematch
    for entry in "$cur"/* "$cur"/.[!.]* "$cur"/..?*; do
      [ -e "$entry" ] || continue
      entry=${entry##*/}
      if [ "$entry" != "$comp" ] && [[ $entry == "$comp" ]]; then match=$entry; break; fi
    done
    shopt -u nocasematch
    if [ -n "$match" ]; then
      report error "$rel" "\"$comp\" differs only by letter case from the existing \"$match\". Use \"$match\"."
      break
    fi
    [ "$rest" = "$comp" ] && break
    cur=$cur/$comp
    rest=${rest#*/}
    [ -d "$cur" ] || break
  done
  if [ "$errors" -gt 0 ]; then
    echo "Blocked by the BuildexLabsAI repository standard. Pick a name that follows it, or ask the user to add an exception to $EXCEPTIONS_FILE." >&2
    return 2
  fi
  return 0
}

# --- main ---------------------------------------------------------------------------------

while [ $# -gt 0 ]; do
  case "$1" in
    --staged) mode=staged; shift ;;
    --hook) mode=hook; shift ;;
    --canonical)
      canonical=$(cd "${2:-}" 2>/dev/null && pwd) || { echo "check-standard: --canonical needs a folder." >&2; exit 1; }
      shift 2 ;;
    *) echo "check-standard: unknown option $1" >&2; exit 1 ;;
  esac
done

if [ "$mode" = hook ]; then
  exec 3>&2
  run_hook
  exit $?
fi

exec 3>&1
root=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "check-standard: run this inside a git repository." >&2
  exit 1
}
cd "$root" || exit 1
load_exceptions
if [ "$mode" = staged ]; then run_staged; else run_full; fi

if [ "$errors" -gt 0 ]; then
  echo "check-standard: $errors error(s), $warnings warning(s). The rules: CONTRIBUTING.md in $SOURCE."
  exit 1
fi
echo "check-standard: OK ($warnings warning(s))."
