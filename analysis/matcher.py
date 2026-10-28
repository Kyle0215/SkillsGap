"""analyze(): compare a syllabus with the job-market skill demand for one role.

INTERFACE CONTRACT (shared with the data/ML team, see docs/INTERFACE.md)
    analyze(syllabus_text: str, role: str, method: str = "level1") -> dict
The UI only reads the dict returned here. A teammate can replace this file
with a better version, as long as it returns the same keys.

MATCHING (same rules as the job-posting counts, see analysis/skill_rules.py)
    level1 = search for the skill's main name only
    level2 = search for the main name plus its synonyms from data/skills.csv
    mentions: 2 or more = "detected", 1 = "brief", 0 = "not_detected"

SCORING - PLACEHOLDER FORMULAS, TO BE REPLACED BY THE ML TEAM
    coverage_weight   = 1.0 (detected), 0.5 (brief), 0.0 (not detected)
    gap_score         = demand x (1 - coverage_weight)
    coverage_score    = 100 x sum(demand x coverage_weight) / sum(demand)
    category coverage = the coverage_score formula, using only that category's skills
    category demand   = 100 x average demand of that category's skills
(demand = fraction 0-1 of the role's job postings that mention the skill)

Not yet done (TODO in PROJECT_LOG.md): section-aware weighting. Every
mention counts the same, wherever it appears, so "section" is always None.
"""
from __future__ import annotations

from functools import lru_cache

from analysis.skill_rules import AMBIGUOUS_TOKENS, SkillMatcher, evidence_snippet
from utils.data_loading import DataError, list_roles, load_skills, role_skills
from utils.text_extraction import ExtractionError, validate_text

METHODS = {
    "level1": "Level 1: exact skill name",
    "level2": "Level 2: skill name + synonyms",
}
COVERAGE_WEIGHT = {"detected": 1.0, "brief": 0.5, "not_detected": 0.0}
DETECTED_MIN_MENTIONS = 2

METHOD_NOTES = {
    "level1": (
        "Level 1: searched the syllabus for each skill's main name only, as whole words or "
        "phrases. Short ambiguous names (such as R, C, Go, SAS) were matched case-sensitively; "
        "R, C and Go also needed a nearby context word such as 'programming'. "
        "All mentions weighted equally (no section weighting). Scoring formulas are placeholders."
    ),
    "level2": (
        "Level 2: searched the syllabus for each skill's main name and its synonyms from the "
        "skill dictionary, as whole words or phrases, using the same rules that counted the "
        "job postings. Short ambiguous names were matched case-sensitively; R, C and Go also "
        "needed a nearby context word. All mentions weighted equally (no section weighting). "
        "Scoring formulas are placeholders."
    ),
}


class AnalysisError(ValueError):
    """A problem with the user's input (text, role or method). The message is friendly."""


# ---------------------------------------------------------------------------
# Cached helpers (built once per app process)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _synonyms() -> dict[str, list[str]]:
    skills = load_skills()
    return dict(zip(skills["skill"], skills["synonyms"]))


@lru_cache(maxsize=1024)
def _matcher(skill: str, method: str) -> SkillMatcher:
    synonyms = _synonyms()[skill] if method == "level2" else []
    return SkillMatcher(skill, synonyms)


@lru_cache(maxsize=1)
def _check_ambiguous_rules() -> bool:
    """Make sure the ambiguous skills in skills.csv match AMBIGUOUS_TOKENS in the code."""
    skills = load_skills()
    in_data = set(skills.loc[skills["ambiguous"], "skill"])
    in_code = set(AMBIGUOUS_TOKENS)
    if in_data != in_code:
        raise DataError(
            "The ambiguous skills in data/skills.csv do not match the matching rules in "
            "analysis/skill_rules.py. Only in data: "
            f"{sorted(in_data - in_code) or 'none'}; only in code: {sorted(in_code - in_data) or 'none'}."
        )
    synonyms = _synonyms()
    for skill, tokens in AMBIGUOUS_TOKENS.items():
        for token in tokens:
            if token != skill and token not in synonyms[skill]:
                raise DataError(f"Token '{token}' for skill '{skill}' is not in data/skills.csv.")
    return True


# ---------------------------------------------------------------------------
# Small helpers for one skill
# ---------------------------------------------------------------------------

def _status(mentions: int) -> str:
    if mentions >= DETECTED_MIN_MENTIONS:
        return "detected"
    return "brief" if mentions == 1 else "not_detected"


def _matched_terms(text: str, spans: list[tuple[int, int]]) -> list[str]:
    """The words as they appear in the syllabus, without repeats (ignoring case)."""
    seen, terms = set(), []
    for start, end in spans:
        term = " ".join(text[start:end].split())
        if term.lower() not in seen:
            seen.add(term.lower())
            terms.append(term)
    return terms


def _explanation(status: str, mentions: int, terms: list[str], row, role: str,
                 method: str, has_synonyms: bool) -> str:
    """One plain-English sentence or two. Never says a skill is 'missing' or 'not taught'."""
    demand_text = (
        f"Mentioned in {row.demand * 100:.1f}% of {role} job postings "
        f"({row.postings_count} of {row.total_postings})."
    )
    quoted = ", ".join(f"'{t}'" for t in terms)
    if status == "detected":
        return f"Found {mentions} times in the syllabus text (matched {quoted}). {demand_text}"
    if status == "brief":
        return (f"Found once in the syllabus text (matched {quoted}), so it may only be covered "
                f"briefly. {demand_text}")
    text = (f"Not found in the syllabus text. {demand_text} It may still be taught under "
            "another name; please check with the course lecturer.")
    if method == "level1" and has_synonyms:
        text += " Level 1 checks the skill name only; Level 2 also checks its synonyms."
    return text


# ---------------------------------------------------------------------------
# The contract function
# ---------------------------------------------------------------------------

def analyze(syllabus_text: str, role: str, method: str = "level1") -> dict:
    """Compare a syllabus with the skills mentioned in job postings for one role.

    Raises AnalysisError (friendly message) for empty/short text, an unknown
    role or an unknown method, and DataError if the data files are broken.
    """
    if method not in METHODS:
        raise AnalysisError(f"Unknown matching method '{method}'. Please choose Level 1 or Level 2.")
    if role not in list_roles():
        raise AnalysisError(f"There is no job-market data for the role '{role}'. Please choose another role.")
    try:
        text = validate_text(syllabus_text)
    except ExtractionError as err:
        raise AnalysisError(str(err)) from None
    _check_ambiguous_rules()

    rows = role_skills(role)
    skills_out = []
    for row in rows.itertuples(index=False):
        spans = _matcher(row.skill, method).find_all(text)
        mentions = len(spans)
        status = _status(mentions)
        terms = _matched_terms(text, spans)
        evidence, evidence_span = evidence_snippet(text, *spans[0]) if spans else (None, None)
        skills_out.append({
            "skill": row.skill,
            "category": row.category,
            "demand": float(row.demand),
            "status": status,
            "mentions": mentions,
            "evidence": evidence,
            "gap_score": round(float(row.demand) * (1 - COVERAGE_WEIGHT[status]), 4),
            "explanation": _explanation(status, mentions, terms, row, role, method, bool(row.synonyms)),
            # Optional fields (the UI must also work without them):
            "matched_terms": terms,
            "section": None,                  # section-aware weighting is a TODO
            "evidence_span": evidence_span,   # [start, end] of the match inside "evidence"
        })

    # Highest gap first, then highest demand, then name.
    skills_out.sort(key=lambda s: (-s["gap_score"], -s["demand"], s["skill"]))

    return {
        "role": role,
        "method": method,
        "method_notes": METHOD_NOTES[method],
        "postings_used": int(rows["total_postings"].iloc[0]),
        "skills_checked": len(skills_out),
        "coverage_score": _coverage(skills_out),
        "skills": skills_out,
        "category_summary": _category_summary(skills_out),
    }


def _coverage(skills: list[dict]) -> float:
    """100 x sum(demand x coverage_weight) / sum(demand), rounded to 1 decimal."""
    total = sum(s["demand"] for s in skills)
    if total == 0:
        return 0.0
    covered = sum(s["demand"] * COVERAGE_WEIGHT[s["status"]] for s in skills)
    return round(100 * covered / total, 1)


def _category_summary(skills: list[dict]) -> list[dict]:
    """Coverage and demand per category, both on a 0-100 scale, sorted by category name."""
    summary = []
    for category in sorted({s["category"] for s in skills}):
        group = [s for s in skills if s["category"] == category]
        summary.append({
            "category": category,
            "coverage": _coverage(group),
            "demand": round(100 * sum(s["demand"] for s in group) / len(group), 1),
        })
    return summary
