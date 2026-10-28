"""The built-in fictional sample syllabi in /samples (the "Sample" option on the start screen)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from utils.text_extraction import ExtractionError

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

# Display name -> (file name, suggested job role). The file name without ".txt"
# is the sample's id in the web API (e.g. "intro_data_analytics").
SAMPLES: dict[str, tuple[str, str]] = {
    "Introduction to Data Analytics (fictional sample)": ("intro_data_analytics.txt", "Data Analyst"),
    "Network Security Fundamentals (fictional sample)": ("network_security_fundamentals.txt", "Cybersecurity Analyst"),
    "Engineering Project Management (fictional sample)": ("engineering_project_management.txt", "Project Manager"),
}


@lru_cache(maxsize=None)
def load_sample(name: str) -> str:
    """Return the text of a sample syllabus, or raise ExtractionError if it is missing."""
    if name not in SAMPLES:
        raise ExtractionError("Please choose one of the sample syllabi.")
    path = SAMPLES_DIR / SAMPLES[name][0]
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        raise ExtractionError("This sample syllabus could not be found. Please choose another one.") from None


def sample_list() -> list[dict]:
    """[{"id", "name", "role"}] for the web page (name without the "(fictional sample)" part)."""
    return [
        {"id": Path(file).stem, "name": name.replace(" (fictional sample)", ""), "role": role}
        for name, (file, role) in SAMPLES.items()
    ]


def sample_name_from_id(sample_id: str) -> str | None:
    for name, (file, _role) in SAMPLES.items():
        if Path(file).stem == sample_id:
            return name
    return None
