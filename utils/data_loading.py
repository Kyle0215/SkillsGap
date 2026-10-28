"""Load and check the job-market data files in /data.

The files are built by the data team with data/prepare_data.py from the Kaggle
dataset "LinkedIn Job Postings (2023 - 2024)" by Arsh Koneru (CC BY-SA 4.0).
They are READ-ONLY for the app: nothing in this module ever writes to /data.

Each file is read once and then kept in memory (functools.lru_cache), so every
request after the first is fast. This also works in pytest.

Any problem raises DataError with a clear message the UI can show.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SKILLS_FILE = DATA_DIR / "skills.csv"
DEMAND_FILE = DATA_DIR / "role_skill_demand.csv"
SOURCE_FILE = DATA_DIR / "data_source.json"
VALIDATION_FILE = DATA_DIR / "validation_results.json"

# The data team delivered exactly 12 roles. If they add or remove roles,
# change this number together with the data.
EXPECTED_ROLE_COUNT = 12

SKILLS_COLUMNS = ["skill", "category", "synonyms", "ambiguous"]
DEMAND_COLUMNS = ["role", "skill", "demand", "postings_count", "total_postings"]
SOURCE_KEYS = ["name", "url", "licence", "collection_method", "date_range",
               "region", "postings_used", "roles", "notes"]
VALIDATION_KEYS = ["syllabi_reviewed", "skills_reviewed", "precision", "recall",
                   "f1", "lecturer_usefulness_avg", "notes"]
VALIDATION_METRICS = VALIDATION_KEYS[:-1]   # everything except "notes"


class DataError(RuntimeError):
    """A data file is missing or inconsistent. The message is safe to show users."""


# ---------------------------------------------------------------------------
# Reading the CSV files
# ---------------------------------------------------------------------------

def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    """Read a CSV as plain text (no automatic number/NaN guessing) and check its columns."""
    if not path.exists():
        raise DataError(f"Data file not found: data/{path.name}. Ask the data team to rebuild it.")
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    except Exception:
        raise DataError(f"Could not read data/{path.name}. The file may be damaged.") from None
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DataError(f"data/{path.name} is missing column(s): {', '.join(missing)}.")
    return df[columns].apply(lambda col: col.str.strip())


def _load_skills_file() -> pd.DataFrame:
    df = _read_csv(SKILLS_FILE, SKILLS_COLUMNS)
    if df["skill"].eq("").any():
        raise DataError("data/skills.csv has a row with an empty skill name.")
    dupes = sorted(df.loc[df["skill"].duplicated(), "skill"])
    if dupes:
        raise DataError(f"data/skills.csv lists these skills twice: {', '.join(dupes)}.")
    bad = sorted(set(df["ambiguous"]) - {"true", "false"})
    if bad:
        raise DataError(f"data/skills.csv: 'ambiguous' must be true or false, found: {', '.join(bad)}.")

    # "true"/"false" text -> real booleans; "a;b;c" -> ["a", "b", "c"] (can be empty).
    df["ambiguous"] = df["ambiguous"] == "true"
    df["synonyms"] = df["synonyms"].map(lambda s: [t.strip() for t in s.split(";") if t.strip()])
    return df


def _load_demand_file() -> pd.DataFrame:
    df = _read_csv(DEMAND_FILE, DEMAND_COLUMNS)
    for col in ["demand", "postings_count", "total_postings"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["demand", "postings_count", "total_postings"]].isna().any().any():
        raise DataError("data/role_skill_demand.csv has empty or non-numeric values.")
    df["postings_count"] = df["postings_count"].astype(int)
    df["total_postings"] = df["total_postings"].astype(int)

    if not df["demand"].between(0, 1).all():
        raise DataError("data/role_skill_demand.csv: demand must be between 0 and 1.")
    if (df["total_postings"] <= 0).any() or (df["postings_count"] > df["total_postings"]).any():
        raise DataError("data/role_skill_demand.csv: postings_count must be between 0 and total_postings.")
    # demand should equal postings_count / total_postings (rounded to 3 decimals).
    if ((df["demand"] - df["postings_count"] / df["total_postings"]).abs() > 0.0006).any():
        raise DataError("data/role_skill_demand.csv: demand does not match postings_count / total_postings.")
    if df.duplicated(["role", "skill"]).any():
        raise DataError("data/role_skill_demand.csv lists the same role and skill twice.")
    if (df.groupby("role")["total_postings"].nunique() > 1).any():
        raise DataError("data/role_skill_demand.csv: total_postings differs within one role.")
    return df


@lru_cache(maxsize=1)
def _load_all() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load both CSV files once and check that they fit together."""
    skills = _load_skills_file()
    demand = _load_demand_file()

    unknown = sorted(set(demand["skill"]) - set(skills["skill"]))
    if unknown:
        raise DataError(
            "These skills are in role_skill_demand.csv but not in skills.csv: "
            + ", ".join(unknown[:10])
        )
    n_roles = demand["role"].nunique()
    if n_roles != EXPECTED_ROLE_COUNT:
        raise DataError(
            f"Expected {EXPECTED_ROLE_COUNT} roles in role_skill_demand.csv, found {n_roles}."
        )
    return skills, demand


# ---------------------------------------------------------------------------
# Public functions used by the matcher and the UI
# ---------------------------------------------------------------------------

def check_data() -> None:
    """Load and check all job-market data. Raises DataError if anything is wrong."""
    _load_all()


def load_skills() -> pd.DataFrame:
    """The skill dictionary: skill, category, synonyms (list), ambiguous (bool)."""
    return _load_all()[0].copy()


def load_demand() -> pd.DataFrame:
    """Demand per role and skill: role, skill, demand (0-1), postings_count, total_postings."""
    return _load_all()[1].copy()


def list_roles() -> list[str]:
    """All roles that have demand data, in alphabetical order (for the dropdown)."""
    return sorted(_load_all()[1]["role"].unique())


def role_skills(role: str) -> pd.DataFrame:
    """One row per skill of the role, with demand data and dictionary data joined.

    Sorted by demand (highest first), then skill name. The app never relies on
    the order of the CSV file itself.
    """
    skills, demand = _load_all()
    rows = demand[demand["role"] == role]
    if rows.empty:
        raise DataError(f"There is no job-market data for the role '{role}'.")
    merged = rows.merge(skills, on="skill", how="left", validate="one_to_one")
    return merged.sort_values(["demand", "skill"], ascending=[False, True]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# JSON files: data source and pilot validation results
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def _read_json(path: Path) -> dict:
    """Read a JSON object. A missing, empty or broken file gives {}."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_data_source(path: Path = SOURCE_FILE) -> dict:
    """Information about where the job data comes from.

    Every key in SOURCE_KEYS is present. Missing or empty values are None,
    so the UI can show "UNKNOWN" instead of inventing anything.
    """
    raw = _read_json(path)
    return {key: (raw.get(key) if raw.get(key) not in ("", []) else None) for key in SOURCE_KEYS}


def load_validation_results(path: Path = VALIDATION_FILE) -> dict:
    """Published pilot results. Every key in VALIDATION_KEYS is present (None if missing)."""
    raw = _read_json(path)
    return {key: raw.get(key) for key in VALIDATION_KEYS}


def has_pilot_results(results: dict) -> bool:
    """True only if at least one pilot figure is a real number.

    If this is False the UI must show "Not yet evaluated" and no numbers.
    """
    return any(
        isinstance(results.get(key), (int, float)) and not isinstance(results.get(key), bool)
        for key in VALIDATION_METRICS
    )
