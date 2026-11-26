"""Text normalization and the verbatim-quote check.

A quote is "found" when its normalized form occurs in the normalized capture
text. What gets stored is always the *source's own* span, never the caller's
spelling, so a curly apostrophe typed as a straight one is still recorded as
the page wrote it.

Normalization only removes differences a reader can't see: Unicode
compatibility forms, curly versus straight quote marks, dash variants and
runs of whitespace (including line breaks). Case and wording are kept.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_CHAR_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", "​": "",
}
_WS = re.compile(r"\s+")


def norm_char(c: str) -> str:
    c = unicodedata.normalize("NFKC", c)
    return "".join(_CHAR_MAP.get(x, x) for x in c)


def normalize(s: str) -> str:
    """Normalized form used for matching (keeps case)."""
    return _WS.sub(" ", "".join(norm_char(c) for c in s)).strip()


def clean_line(s: str) -> str:
    """A displayable line: whitespace collapsed, invisible characters dropped."""
    s = s.replace("​", "").replace(" ", " ")
    return _WS.sub(" ", s).strip()


@dataclass(frozen=True)
class Span:
    text: str          # the source's own text for the quote
    start_line: int    # 1-based line numbers within the capture
    end_line: int


class SearchableText:
    """A capture's lines joined with single spaces, with a map from each
    normalized character back to its source line and source character."""

    def __init__(self, lines: list[str]):
        self.lines = lines
        norm_chars: list[str] = []
        src_pos: list[tuple[int, int]] = []  # (line index, char index in line)
        for li, line in enumerate(lines):
            if li > 0:
                norm_chars.append(" ")
                src_pos.append((li, -1))  # the joining space
            for ci, ch in enumerate(line):
                for n in norm_char(ch):
                    norm_chars.append(n)
                    src_pos.append((li, ci))
        # collapse whitespace runs, keeping the first position of each run
        out, pos = [], []
        prev_ws = True
        for ch, p in zip(norm_chars, src_pos):
            if ch.isspace():
                if prev_ws:
                    continue
                out.append(" ")
                pos.append(p)
                prev_ws = True
            else:
                out.append(ch)
                pos.append(p)
                prev_ws = False
        self.norm = "".join(out)
        self.pos = pos

    def find(self, quote: str) -> Span | None:
        q = normalize(quote)
        if not q:
            return None
        i = self.norm.find(q)
        if i < 0:
            return None
        j = i + len(q) - 1
        (l1, c1), (l2, c2) = self.pos[i], self.pos[j]
        if c1 < 0:  # began on a joining space (can't, after strip) – be safe
            l1, c1 = l1 + 1, 0
        if c2 < 0:
            l2, c2 = l2 - 1, len(self.lines[l2 - 1]) - 1
        if l1 == l2:
            text = self.lines[l1][c1:c2 + 1]
        else:
            parts = [self.lines[l1][c1:]]
            parts += self.lines[l1 + 1:l2]
            parts.append(self.lines[l2][:c2 + 1])
            text = " ".join(parts)
        return Span(text=text, start_line=l1 + 1, end_line=l2 + 1)

    def count(self, quote: str) -> int:
        q = normalize(quote)
        return self.norm.count(q) if q else 0


# ---- word helpers used by the "named in its own quote" checks ----

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def singular(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and re.search(r"(ches|shes|sses|xes|oes)$", w):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def words(s: str) -> list[str]:
    return [singular(w) for w in _WORD.findall(normalize(s).lower())]


def named_in(name: str, quote: str) -> bool:
    """True when every word of `name` appears, in order and contiguously, in
    `quote` (case-insensitive, simple singular/plural forgiven)."""
    n, q = words(name), words(quote)
    if not n:
        return False
    for i in range(len(q) - len(n) + 1):
        if q[i:i + len(n)] == n:
            return True
    return False


def key(s: str) -> str:
    """Matching key for names and section paths (method §2 step 1)."""
    s = normalize(s).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return _WS.sub(" ", s).strip()
