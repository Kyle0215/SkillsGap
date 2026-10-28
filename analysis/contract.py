"""Check that an analyze() result keeps the interface contract (docs/INTERFACE.md).

Used by the web server (server.py), so a replaced analysis module that returns
the wrong format gives a clear message instead of a crash. Plain Python: no
web framework code here.
"""
from __future__ import annotations

REQUIRED_KEYS = ["role", "method", "postings_used", "skills_checked", "coverage_score",
                 "skills", "category_summary"]
REQUIRED_SKILL_KEYS = ["skill", "category", "demand", "status", "mentions", "evidence",
                       "gap_score", "explanation"]
REQUIRED_CATEGORY_KEYS = ["category", "coverage", "demand"]
VALID_STATUSES = {"detected", "brief", "not_detected"}


class ResultFormatError(ValueError):
    """analyze() returned a dict the UI cannot show. The message is safe to show users."""


def check_result(result) -> None:
    """Raise ResultFormatError if `result` is missing anything the UI needs."""
    problems = []
    if not isinstance(result, dict):
        problems.append("the result is not a dictionary")
    else:
        problems += [f"'{k}'" for k in REQUIRED_KEYS if k not in result]
        skills = result.get("skills")
        if isinstance(skills, list):
            for i, skill in enumerate(skills):
                missing = [k for k in REQUIRED_SKILL_KEYS if not isinstance(skill, dict) or k not in skill]
                if missing:
                    problems.append(f"skills[{i}] is missing {', '.join(missing)}")
                elif skill["status"] not in VALID_STATUSES:
                    problems.append(f"skills[{i}] has an unknown status '{skill['status']}'")
                if len(problems) >= 5:
                    break
        elif "skills" in result:
            problems.append("'skills' is not a list")
        for i, cat in enumerate(result.get("category_summary") or []):
            if not isinstance(cat, dict) or any(k not in cat for k in REQUIRED_CATEGORY_KEYS):
                problems.append(f"category_summary[{i}] is incomplete")
                break
    if problems:
        raise ResultFormatError(
            "The analysis module returned results in an unexpected format, so they cannot be "
            f"shown. Please tell the development team (problem: {'; '.join(problems[:5])})."
        )
