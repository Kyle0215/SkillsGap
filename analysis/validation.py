"""Compare the app's result with a human reviewer's reference answer.

The reviewer (a lecturer or senior) fills in a CSV with two columns:
    skill, reviewer_status        reviewer_status = covered / brief / not_covered

"Positive" means "covered". By default "brief" also counts as covered, on BOTH
sides (the app's "brief" status and the reviewer's "brief"). The UI has a
checkbox to switch this off; then "brief" counts as not covered on both sides.

    true positive  (TP): app says covered,     reviewer says covered
    false positive (FP): app says covered,     reviewer says not covered
    false negative (FN): app says not covered, reviewer says covered
    true negative  (TN): both say not covered

    precision = TP / (TP + FP)  correct detections / all detections by the app
    recall    = TP / (TP + FN)  correct detections / all skills the reviewer says are covered
    F1        = harmonic mean of precision and recall = 2TP / (2TP + FP + FN)

Worked example: the app says 14 skills are covered, 10 of them correctly, and
the reviewer says 12 skills are covered.
    TP = 10, FP = 14 - 10 = 4, FN = 12 - 10 = 2
    precision = 10 / 14 = 0.714    recall = 10 / 12 = 0.833    F1 = 20 / 26 = 0.769

Nothing here is saved to disk. The reviewer's file is processed in memory only.
"""
from __future__ import annotations

import io

import pandas as pd

REVIEWER_STATUSES = ("covered", "brief", "not_covered")
MIN_RELIABLE_SKILLS = 10              # fewer compared skills => "sample too small" warning
MAX_REFERENCE_BYTES = 1 * 1024 * 1024  # 1 MB is far more than a skill list needs


class ReviewFileError(ValueError):
    """A problem with the reviewer's CSV. The message is friendly."""


def precision_recall_f1(tp: int, fp: int, fn: int) -> dict:
    """Precision, recall and F1, plus the numbers behind them ("10 of 14").

    A value is None when its denominator is 0 (for example, precision when the
    app detected nothing), so the UI can say "not defined" instead of guessing.
    """
    def ratio(num: int, den: int):
        return num / den if den else None

    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": ratio(tp, tp + fp), "precision_den": tp + fp,
        "recall": ratio(tp, tp + fn), "recall_den": tp + fn,
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def make_reference_template(result: dict) -> pd.DataFrame:
    """A blank reference answer: the role's skills (A-Z) and an empty reviewer_status."""
    skills = sorted(s["skill"] for s in result["skills"])
    return pd.DataFrame({"skill": skills, "reviewer_status": [""] * len(skills)})


def parse_reference_csv(data: bytes) -> tuple[pd.DataFrame, int]:
    """Read the reviewer's CSV (bytes in memory).

    Returns (table with columns skill and reviewer_status, number of skills left blank).
    Blank statuses are skipped (not reviewed yet). Raises ReviewFileError otherwise.
    """
    if not data:
        raise ReviewFileError("The reference file is empty.")
    if len(data) > MAX_REFERENCE_BYTES:
        raise ReviewFileError("The reference file is too large (limit 1 MB).")
    try:
        text = data.decode("utf-8-sig")       # also removes the BOM that Excel adds
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except Exception:
        raise ReviewFileError(
            "We could not read this CSV file. Please start from the downloaded template."
        ) from None

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in ("skill", "reviewer_status") if c not in df.columns]
    if missing:
        raise ReviewFileError(
            f"The reference file needs the column(s): {', '.join(missing)}. "
            "Please start from the downloaded template."
        )

    df = df[["skill", "reviewer_status"]].apply(lambda col: col.str.strip())
    df = df[df["skill"] != ""]
    # Accept "Covered", "not covered", "Not-Covered" ... as the same values.
    df["reviewer_status"] = df["reviewer_status"].str.lower().str.replace(r"[\s\-]+", "_", regex=True)

    blank = df["reviewer_status"] == ""
    n_blank = int(blank.sum())
    df = df[~blank]

    bad = df.loc[~df["reviewer_status"].isin(REVIEWER_STATUSES)]
    if not bad.empty:
        examples = ", ".join(f"{s} = '{v}'" for s, v in bad.head(5).itertuples(index=False))
        raise ReviewFileError(
            f"Some reviewer_status values are not valid ({examples}). "
            "Use covered, brief or not_covered."
        )
    dupes = df.loc[df["skill"].str.lower().duplicated(), "skill"].tolist()
    if dupes:
        raise ReviewFileError(f"These skills appear more than once: {', '.join(dupes[:5])}.")
    if df.empty:
        raise ReviewFileError(
            "No skill has a reviewer_status yet. Fill in covered, brief or not_covered."
        )
    return df.reset_index(drop=True), n_blank


def compare_with_reviewer(result: dict, reference: pd.DataFrame,
                          brief_counts_as_covered: bool = True) -> dict:
    """Compare one analyze() result with the reviewer's reference answer.

    Only skills that appear in both are compared. Skills in the reference that
    the analysis did not check are listed in "not_in_analysis".
    """
    app_positive = {"detected", "brief"} if brief_counts_as_covered else {"detected"}
    reviewer_positive = {"covered", "brief"} if brief_counts_as_covered else {"covered"}
    by_skill = {s["skill"].lower(): s for s in result["skills"]}

    tp = fp = fn = tn = 0
    disagreements, not_in_analysis = [], []
    for skill, reviewer_status in zip(reference["skill"], reference["reviewer_status"]):
        app = by_skill.get(skill.lower())
        if app is None:
            not_in_analysis.append(skill)
            continue
        app_pos = app["status"] in app_positive
        reviewer_pos = reviewer_status in reviewer_positive
        if app_pos and reviewer_pos:
            tp += 1
        elif app_pos:
            fp += 1
            disagreements.append(_disagreement(app, reviewer_status, "False positive"))
        elif reviewer_pos:
            fn += 1
            disagreements.append(_disagreement(app, reviewer_status, "False negative"))
        else:
            tn += 1

    n_compared = tp + fp + fn + tn
    return {
        "role": result.get("role"),
        "method": result.get("method"),
        "brief_counts_as_covered": brief_counts_as_covered,
        "n_compared": n_compared,
        "small_sample": n_compared < MIN_RELIABLE_SKILLS,
        "tn": tn,
        **precision_recall_f1(tp, fp, fn),
        "disagreements": disagreements,
        "not_in_analysis": not_in_analysis,
    }


def _disagreement(app: dict, reviewer_status: str, kind: str) -> dict:
    meaning = {
        "False positive": "The app found it, but the reviewer says it is not covered.",
        "False negative": "The reviewer says it is covered, but the app did not find it.",
    }[kind]
    return {
        "skill": app["skill"],
        "category": app.get("category"),
        "app_status": app["status"],
        "reviewer_status": reviewer_status,
        "type": kind,
        "meaning": meaning,
        "evidence": app.get("evidence"),
        "matched_terms": app.get("matched_terms", []),
    }
