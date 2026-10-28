"""Skill-matching rules for the syllabus, ported from the data team's script.

The job-posting counts in data/role_skill_demand.csv were made with
phrase_regex(), strict_token_regex(), SkillMatcher, AMBIGUOUS_TOKENS and
CONTEXT_WINDOW in data/prepare_data.py. A syllabus must be matched with the
SAME rules, otherwise it would be judged differently from the job ads.

Those pieces are copied here unchanged, except for two small additions:

1. SkillMatcher only uses the strict (case-sensitive) tokens that are in its
   own list of terms. This lets Level 1 ("skill name only") skip short
   synonym tokens such as "ML" or "IR". With all synonyms (Level 2) it
   behaves exactly like the reference script. tests/test_matcher.py checks this.
2. find_all() returns every mention, not only the first one, because the
   syllabus status needs a mention count. Overlapping matches count once
   (for example "Apache Spark" also contains the token "Spark").

If the data team changes these rules in prepare_data.py, copy the change here.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Copied from data/prepare_data.py, section 3.
# Ambiguous short tokens are matched CASE-SENSITIVELY as standalone tokens.
# If a list of context words is given, one of them must appear within
# CONTEXT_WINDOW characters of the token (needed for single letters and "Go").
# skills.csv only stores ambiguous=true/false, so the tokens live here in code.
# ---------------------------------------------------------------------------
CONTEXT_WINDOW = 60
PROG_CONTEXT = ["python", "java", "sql", "programming", "language", "languages", "coding"]
AMBIGUOUS_TOKENS: dict[str, dict[str, list[str] | None]] = {
    "R": {"R": PROG_CONTEXT + ["sas", "spss", "stata", "matlab", "scala", "julia", "statistical",
                               "statistics", "tidyverse", "ggplot2", "shiny"]},
    "C": {"C": PROG_CONTEXT + ["c++", "c#", "embedded", "firmware", "assembly", "rust",
                               "microcontroller", "microcontrollers", "verilog", "vhdl"]},
    "Go": {"Go": PROG_CONTEXT + ["golang", "rust", "kotlin", "c++", "ruby", "scala", "node.js",
                                 "typescript", "microservices", "backend"]},
    "Incident Response": {"IR": None},
    "Machine Learning": {"ML": None},
    "SAS": {"SAS": None},
    "Excel": {"Excel": None},
    "Apache Spark": {"Spark": None},
    "React": {"React": None},
    "Sketch": {"Sketch": None},
    "IDS/IPS": {"IDS": None, "IPS": None},
}


def phrase_regex(term: str) -> str:
    """Whole word/phrase pattern. (?<!\\w) and (?!\\w) behave like \\b...\\b for normal
    words, and also work for terms that start/end with symbols (C++, C#, .NET, Security+).
    Spaces in a phrase match any run of whitespace (text contains line breaks)."""
    body = re.escape(term).replace(r"\ ", r"\s+")
    return rf"(?<!\w){body}(?!\w)"


def strict_token_regex(token: str) -> str:
    """Case-sensitive standalone token for ambiguous short skills.
    Not allowed to be glued to letters/digits or to & - . + # (stops R&D, Objective-C,
    C++ counting as C, Go-to-market, R.N.). "Python/R" and "C/C++" are still allowed."""
    return rf"(?<![\w&\-.]){re.escape(token)}(?![\w&+#\-]|\.\w|/\d)"


class SkillMatcher:
    """Finds one skill in a text. Copied from prepare_data.py, plus find_all()."""

    def __init__(self, skill: str, synonyms: list[str]):
        self.skill = skill
        terms = sorted({skill, *synonyms}, key=len, reverse=True)
        # Addition 1: only use the strict tokens that are among this matcher's terms.
        strict = {tok: ctx for tok, ctx in AMBIGUOUS_TOKENS.get(skill, {}).items() if tok in terms}
        loose = [t for t in terms if t not in strict]
        self.loose = re.compile("|".join(phrase_regex(t) for t in loose), re.IGNORECASE) if loose else None
        self.strict = []
        for token, context in strict.items():
            ctx = None
            if context:
                ctx = re.compile("|".join(phrase_regex(c) for c in context), re.IGNORECASE)
            self.strict.append((re.compile(strict_token_regex(token)), ctx))

    def first_match(self, text: str):
        """Return (start, end) of the first valid match, or None. (Same as the reference.)"""
        best = None
        if self.loose:
            m = self.loose.search(text)
            if m:
                best = (m.start(), m.end())
        for token_re, ctx in self.strict:
            for m in token_re.finditer(text):
                if best and m.start() >= best[0]:
                    break
                if ctx is None or ctx.search(text[max(0, m.start() - CONTEXT_WINDOW): m.end() + CONTEXT_WINDOW]):
                    best = (m.start(), m.end())
                    break
        return best

    def find_all(self, text: str) -> list[tuple[int, int]]:
        """Addition 2: every valid, non-overlapping match as (start, end), in text order."""
        spans = []
        if self.loose:
            spans += [(m.start(), m.end()) for m in self.loose.finditer(text)]
        for token_re, ctx in self.strict:
            for m in token_re.finditer(text):
                window = text[max(0, m.start() - CONTEXT_WINDOW): m.end() + CONTEXT_WINDOW]
                if ctx is None or ctx.search(window):
                    spans.append((m.start(), m.end()))

        # When two matches overlap, keep the one that starts first (longest if tied).
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        kept, last_end = [], -1
        for start, end in spans:
            if start >= last_end:
                kept.append((start, end))
                last_end = end
        return kept


# ---------------------------------------------------------------------------
# Evidence snippet: the sentence around a match
# ---------------------------------------------------------------------------
# A sentence ends at . ! or ? followed by a space, or at a line break.
# (".NET" or "Node.js" do not end a sentence because no space follows the dot.)
_SENTENCE_END = re.compile(r"[.!?](?=\s)|\n")


def _squash(text: str) -> str:
    """Turn every run of whitespace (including line breaks) into one space."""
    return re.sub(r"\s+", " ", text)


def evidence_snippet(text: str, start: int, end: int, max_side: int = 150) -> tuple[str, list[int]]:
    """Return (sentence around the match, [start, end] of the match inside that sentence).

    Very long sentences are shortened to about max_side characters on each
    side of the match, with "…" showing where text was cut.
    """
    left = 0
    for m in _SENTENCE_END.finditer(text, 0, start):
        left = m.end()
    m = _SENTENCE_END.search(text, end)
    right = m.end() if m else len(text)

    before = _squash(text[left:start]).lstrip()
    match = _squash(text[start:end])
    after = _squash(text[end:right]).rstrip()

    prefix = suffix = ""
    if len(before) > max_side:
        before = before[-max_side:]
        before = before[before.find(" ") + 1:]   # don't start in the middle of a word
        prefix = "… "
    if len(after) > max_side:
        after = after[:max_side]
        after = after[:after.rfind(" ")] if " " in after else after
        suffix = " …"

    snippet = prefix + before + match + after + suffix
    offset = len(prefix + before)
    return snippet, [offset, offset + len(match)]
