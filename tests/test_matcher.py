"""Tests for analysis/matcher.py and analysis/skill_rules.py.

They use the real data files in /data and small, made-up sentences.
Run with:  python -m pytest -q
"""
import importlib.util
from pathlib import Path

import pytest

from analysis.matcher import COVERAGE_WEIGHT, AnalysisError, analyze
from analysis.skill_rules import SkillMatcher
from utils.data_loading import list_roles, load_skills

# Neutral text (33 words) that mentions no skill of any role. analyze() needs
# at least 30 words, so every test sentence is followed by this filler.
FILLER = (
    "This fictional course runs for fourteen weeks. Students attend weekly lectures "
    "and tutorials on campus. Attendance is recorded every week and the course follows "
    "the university calendar for the whole semester."
)


def run(sentence: str, role: str, method: str = "level2") -> dict:
    """Analyse sentence + filler and return {skill name: skill entry}."""
    result = analyze(f"{sentence}\n{FILLER}", role, method)
    return {s["skill"]: s for s in result["skills"]}


# ---------- the filler itself ----------

def test_filler_matches_no_skill_for_any_role():
    for role in list_roles():
        result = analyze(FILLER, role, "level2")
        found = [s["skill"] for s in result["skills"] if s["mentions"]]
        assert found == [], f"{role}: filler matched {found}"


# ---------- Level 1 vs Level 2 ----------

def test_synonym_found_at_level2_but_not_level1():
    sentence = "Students investigate security alerts in Splunk."
    assert run(sentence, "Cybersecurity Analyst", "level1")["SIEM"]["status"] == "not_detected"
    siem = run(sentence, "Cybersecurity Analyst", "level2")["SIEM"]
    assert siem["status"] == "brief"
    assert siem["matched_terms"] == ["Splunk"]


def test_short_synonym_token_only_counts_at_level2():
    # "ML" is a case-sensitive synonym of Machine Learning, so Level 1 must skip it.
    sentence = "Week 5 introduces ML models."
    assert run(sentence, "Data Scientist", "level1")["Machine Learning"]["status"] == "not_detected"
    assert run(sentence, "Data Scientist", "level2")["Machine Learning"]["status"] == "brief"


# ---------- whole words and ambiguous short names ----------

def test_java_is_not_matched_inside_javascript():
    skills = run("Students build web pages with JavaScript. JavaScript is used every week.",
                 "Software Engineer")
    assert skills["Java"]["status"] == "not_detected"
    assert skills["JavaScript"]["status"] == "detected"
    assert skills["JavaScript"]["mentions"] == 2


def test_r_is_not_matched_inside_ordinary_words_or_r_and_d():
    # "statistics" is a context word for R, so only the token rules can block these.
    skills = run("Statistics students review R&D reports, Research papers and ROI tables.",
                 "Data Scientist")
    assert skills["R"]["status"] == "not_detected"


def test_python_or_r_matches_r():
    r = run("Students analyse data in Python or R.", "Data Scientist")["R"]
    assert r["status"] == "brief"
    assert r["matched_terms"] == ["R"]


def test_lowercase_r_is_not_matched():
    assert run("Students write python or r scripts.", "Data Scientist")["R"]["status"] == "not_detected"


def test_r_without_context_word_is_not_matched():
    # A capital R with no programming/statistics word nearby, e.g. a grade or label.
    assert run("Students who fail receive grade R.", "Data Scientist")["R"]["status"] == "not_detected"


def test_c_plus_plus_does_not_count_as_c():
    skills = run("Students program in C++ only.", "Software Engineer")
    assert skills["C"]["status"] == "not_detected"
    assert skills["C++"]["status"] == "brief"


def test_c_slash_c_plus_plus_counts_as_c():
    skills = run("Students compare C/C++ compilers.", "Software Engineer")
    assert skills["C"]["status"] == "brief"
    assert skills["C++"]["status"] == "brief"


def test_go_to_market_does_not_count_as_go():
    skills = run("The go-to-market plan and Go-to-market strategy use Python.", "Software Engineer")
    assert skills["Go"]["status"] == "not_detected"


# ---------- status from the number of mentions ----------

@pytest.mark.parametrize("sentence, mentions, status", [
    ("", 0, "not_detected"),
    ("Students build one chart in Tableau.", 1, "brief"),
    ("Week 3 covers Tableau. Week 4 uses Tableau again.", 2, "detected"),
    ("Tableau, Tableau and more Tableau.", 3, "detected"),
])
def test_status_depends_on_number_of_mentions(sentence, mentions, status):
    tableau = run(sentence, "Data Analyst", "level1")["Tableau"]
    assert tableau["mentions"] == mentions
    assert tableau["status"] == status


def test_overlapping_matches_count_once():
    # "Apache Spark" also contains the token "Spark"; it must count as 1 mention.
    spark = run("Students process data with Apache Spark.", "Data Scientist")["Apache Spark"]
    assert spark["mentions"] == 1


# ---------- bad input ----------

def test_empty_syllabus_is_rejected_with_friendly_message():
    with pytest.raises(AnalysisError, match="empty"):
        analyze("   ", "Data Analyst")


def test_very_short_syllabus_is_rejected_with_friendly_message():
    with pytest.raises(AnalysisError, match="too short"):
        analyze("Python and SQL basics.", "Data Analyst")


def test_unknown_role_is_rejected():
    with pytest.raises(AnalysisError, match="no job-market data"):
        analyze(FILLER, "Astronaut")


def test_unknown_method_is_rejected():
    with pytest.raises(AnalysisError, match="Unknown matching method"):
        analyze(FILLER, "Data Analyst", "level9")


# ---------- the returned dict (interface contract) ----------

def test_result_follows_the_interface_contract():
    result = analyze(f"Students use SQL and Excel. SQL is assessed.\n{FILLER}", "Data Analyst", "level2")
    for key, kind in [("role", str), ("method", str), ("method_notes", str), ("postings_used", int),
                      ("skills_checked", int), ("coverage_score", float), ("skills", list),
                      ("category_summary", list)]:
        assert isinstance(result[key], kind), key
    assert result["role"] == "Data Analyst"
    assert result["postings_used"] == 371          # from data/role_skill_demand.csv
    assert result["skills_checked"] == len(result["skills"]) == 29
    assert 0 <= result["coverage_score"] <= 100

    for s in result["skills"]:
        assert set(s) >= {"skill", "category", "demand", "status", "mentions", "evidence",
                          "gap_score", "explanation", "matched_terms", "section"}
        assert s["status"] in COVERAGE_WEIGHT
        assert 0 <= s["demand"] <= 1
        assert (s["evidence"] is None) == (s["mentions"] == 0)
        assert "missing" not in s["explanation"].lower()

    for c in result["category_summary"]:
        assert 0 <= c["coverage"] <= 100 and 0 <= c["demand"] <= 100
    assert len(result["category_summary"]) <= 8


def test_scoring_follows_the_placeholder_formulas():
    result = analyze(f"Students use SQL and Excel. SQL is assessed.\n{FILLER}", "Data Analyst", "level2")
    skills = result["skills"]
    for s in skills:
        assert s["gap_score"] == pytest.approx(s["demand"] * (1 - COVERAGE_WEIGHT[s["status"]]), abs=1e-4)
    expected = 100 * sum(s["demand"] * COVERAGE_WEIGHT[s["status"]] for s in skills) / sum(
        s["demand"] for s in skills)
    assert result["coverage_score"] == pytest.approx(expected, abs=0.05)
    # Ranked by gap score, highest first.
    gaps = [s["gap_score"] for s in skills]
    assert gaps == sorted(gaps, reverse=True)


def test_evidence_is_the_sentence_around_the_first_match():
    siem = run("Week 2 covers firewalls. Students investigate alerts in Splunk. Week 3 covers VPNs.",
               "Cybersecurity Analyst")["SIEM"]
    assert siem["evidence"] == "Students investigate alerts in Splunk."
    start, end = siem["evidence_span"]
    assert siem["evidence"][start:end] == "Splunk"


# ---------- the port matches the data team's reference script ----------

def _load_reference_script():
    path = Path(__file__).resolve().parent.parent / "data" / "prepare_data.py"
    spec = importlib.util.spec_from_file_location("prepare_data_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PARITY_TEXTS = [
    "We use Python or R for statistics, and SQL for queries.",
    "Experience with C/C++ and embedded firmware. Objective-C is a plus.",
    "R&D team. Go-to-market strategy. Research and ROI.",
    "Backend services in Go and Node.js; microservices on Kubernetes (k8s).",
    "Excel, excel and Microsoft Excel. SAS or sas. React and react.js.",
    "Apache Spark, PySpark and Spark SQL. ML pipelines and machine learning.",
    "SIEM tools such as Splunk; IDS/IPS; IR playbooks; incident handling.",
    ".NET Core, C#, Security+ and CI/CD with GD&T drawings.",
    "Figma, Sketch, or InVision. User\nresearch and usability\ntesting.",
    "JavaScript (JS) and TypeScript, but not Java.",
]


def test_level2_matches_the_reference_script_for_every_skill():
    ref = _load_reference_script()
    skills = load_skills()
    for skill, synonyms in zip(skills["skill"], skills["synonyms"]):
        ours = SkillMatcher(skill, synonyms)
        theirs = ref.SkillMatcher(skill, synonyms)
        for text in PARITY_TEXTS:
            expected = theirs.first_match(text)
            assert ours.first_match(text) == expected, (skill, text)
            found = ours.find_all(text)
            assert bool(found) == (expected is not None), (skill, text)
            if found:
                assert found[0][0] == expected[0], (skill, text)
