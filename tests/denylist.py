"""The denylist of check 11 as SHA-256 hashes, so the public repository names nobody it guards against.

A term is its lowercase words joined by one space: "Acme-Corp" and "acme corp" are both "acme corp". A text holds a
term when one of its runs of one to three words hashes to it, so "acme_corp" and "ACME.corp" are caught as well.
Short words can be guessed by hashing a dictionary: the hashes keep the list unreadable, not secret.

The plain list, tests/denylist.txt (one term per line, # for comments), stays on the owner's Mac only and is
gitignored. After a change to it: python3 tests/denylist.py   (rewrites tests/denylist.sha256)
"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAIN = HERE / "denylist.txt"
HASHES = HERE / "denylist.sha256"
MAX_WORDS = 3


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def digest(phrase: str) -> str:
    return hashlib.sha256(phrase.encode()).hexdigest()


def load() -> set[str]:
    return {line.split()[0] for line in HASHES.read_text().splitlines() if line.strip() and not line.startswith("#")}


def hits(text: str, hashes: set[str]) -> set[str]:
    """The phrases of text whose hash is on the list."""
    w = words(text)
    return {" ".join(w[i:i + n]) for n in range(1, MAX_WORDS + 1) for i in range(len(w) - n + 1)
            if digest(" ".join(w[i:i + n])) in hashes}


def main() -> int:
    terms = sorted({" ".join(words(t)) for t in PLAIN.read_text().splitlines() if t.strip() and not t.startswith("#")})
    too_long = [t for t in terms if len(t.split()) > MAX_WORDS]
    if too_long:
        print(f"terms of more than {MAX_WORDS} words are never matched: {too_long}", file=sys.stderr)
        return 1
    HASHES.write_text("# SHA-256 of each denylisted term (tests/denylist.py explains the format and how to update it)\n"
                      + "".join(f"{digest(t)}\n" for t in sorted(terms, key=digest)))
    print(f"{len(terms)} terms written to {HASHES.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
