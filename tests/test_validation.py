"""Tests for analysis/validation.py (precision / recall / F1 against a reviewer).

The numbers here are hand-calculated test fixtures, not results of the app.
Run with:  python -m pytest -q
"""
import pytest

from analysis.validation import (
    ReviewFileError,
    compare_with_reviewer,
    make_reference_template,
    parse_reference_csv,
    precision_recall_f1,
)


def fake_result(statuses: dict) -> dict:
    """A minimal analyze()-style result with the given {skill: app status}."""
    return {
        "role": "Test Role",
        "method": "level1",
        "skills": [{"skill": s, "category": "Test", "status": st, "evidence": None,
                    "matched_terms": []} for s, st in statuses.items()],
    }


def reference(rows: dict):
    import pandas as pd
    return pd.DataFrame({"skill": list(rows), "reviewer_status": list(rows.values())})


# ---------- the worked example from the README ----------

def test_worked_example_14_detected_10_correct_12_covered():
    # App says 14 covered, 10 of them correct; reviewer says 12 covered.
    m = precision_recall_f1(tp=10, fp=4, fn=2)
    assert m["precision"] == pytest.approx(10 / 14)       # 0.714
    assert m["recall"] == pytest.approx(10 / 12)          # 0.833
    assert m["f1"] == pytest.approx(20 / 26)              # 0.769
    assert (m["precision_den"], m["recall_den"]) == (14, 12)


def test_worked_example_through_compare_with_reviewer():
    app, ref = {}, {}
    for i in range(1, 21):
        skill = f"skill{i}"
        if i <= 10:                    # TP: both covered
            app[skill], ref[skill] = "detected", "covered"
        elif i <= 14:                  # FP: app covered, reviewer not
            app[skill], ref[skill] = "detected", "not_covered"
        elif i <= 16:                  # FN: reviewer covered, app not
            app[skill], ref[skill] = "not_detected", "covered"
        else:                          # TN: both not covered
            app[skill], ref[skill] = "not_detected", "not_covered"
    out = compare_with_reviewer(fake_result(app), reference(ref))
    assert (out["tp"], out["fp"], out["fn"], out["tn"]) == (10, 4, 2, 4)
    assert out["precision"] == pytest.approx(10 / 14)
    assert out["recall"] == pytest.approx(10 / 12)
    assert out["n_compared"] == 20 and not out["small_sample"]
    kinds = sorted(d["type"] for d in out["disagreements"])
    assert kinds == ["False negative"] * 2 + ["False positive"] * 4


# ---------- "brief" checkbox ----------

def test_brief_counts_as_covered_by_default_on_both_sides():
    result = fake_result({"a": "brief", "b": "detected"})
    ref = reference({"a": "covered", "b": "brief"})
    on = compare_with_reviewer(result, ref)
    assert (on["tp"], on["fp"], on["fn"]) == (2, 0, 0)
    off = compare_with_reviewer(result, ref, brief_counts_as_covered=False)
    assert (off["tp"], off["fp"], off["fn"]) == (0, 1, 1)


# ---------- edge cases ----------

def test_undefined_metrics_are_none_not_zero():
    m = precision_recall_f1(tp=0, fp=0, fn=0)
    assert m["precision"] is None and m["recall"] is None and m["f1"] is None


def test_fewer_than_10_skills_is_flagged_as_small_sample():
    out = compare_with_reviewer(fake_result({"a": "detected"}), reference({"a": "covered"}))
    assert out["n_compared"] == 1 and out["small_sample"]


def test_skills_not_in_the_analysis_are_listed_not_compared():
    out = compare_with_reviewer(fake_result({"a": "detected"}),
                                reference({"a": "covered", "Basket Weaving": "covered"}))
    assert out["n_compared"] == 1
    assert out["not_in_analysis"] == ["Basket Weaving"]


# ---------- template and CSV reading ----------

def test_template_lists_role_skills_with_empty_status():
    template = make_reference_template(fake_result({"SQL": "detected", "Excel": "brief"}))
    assert list(template.columns) == ["skill", "reviewer_status"]
    assert list(template["skill"]) == ["Excel", "SQL"]
    assert set(template["reviewer_status"]) == {""}


def test_reference_csv_accepts_excel_bom_and_loose_spelling():
    data = "\ufeffSkill,Reviewer_Status\nSQL,Covered\nExcel,not covered\nTableau,\n".encode("utf-8")
    df, n_blank = parse_reference_csv(data)
    assert dict(zip(df["skill"], df["reviewer_status"])) == {"SQL": "covered", "Excel": "not_covered"}
    assert n_blank == 1


@pytest.mark.parametrize("data, message", [
    (b"", "empty"),
    (b"skill,status\nSQL,covered\n", "needs the column"),
    (b"skill,reviewer_status\nSQL,maybe\n", "not valid"),
    (b"skill,reviewer_status\nSQL,covered\nsql,brief\n", "more than once"),
    (b"skill,reviewer_status\nSQL,\n", "No skill has a reviewer_status"),
])
def test_bad_reference_csv_gives_friendly_error(data, message):
    with pytest.raises(ReviewFileError, match=message):
        parse_reference_csv(data)
