"""Tests for utils/data_loading.py, using the real files in /data.

Run with:  python -m pytest -q
"""
import pytest

from utils.data_loading import (
    DataError,
    check_data,
    has_pilot_results,
    list_roles,
    load_data_source,
    load_demand,
    load_skills,
    load_validation_results,
    role_skills,
)


def test_data_files_pass_all_checks():
    check_data()  # raises DataError if anything is inconsistent
    assert len(list_roles()) == 12
    assert len(load_skills()) == 244
    assert len(load_demand()) == 350


def test_every_demand_skill_is_in_the_dictionary():
    assert set(load_demand()["skill"]) <= set(load_skills()["skill"])


def test_synonyms_and_ambiguous_are_parsed():
    skills = load_skills().set_index("skill")
    assert skills.loc["ANSYS", "synonyms"] == []          # empty synonyms field
    assert "splunk" in skills.loc["SIEM", "synonyms"]
    assert bool(skills.loc["R", "ambiguous"]) is True
    assert bool(skills.loc["SQL", "ambiguous"]) is False


def test_role_skills_are_sorted_by_demand():
    rows = role_skills("UI/UX Designer")       # role name with a slash
    assert list(rows["demand"]) == sorted(rows["demand"], reverse=True)
    assert rows["total_postings"].nunique() == 1


def test_unknown_role_raises_data_error():
    with pytest.raises(DataError, match="no job-market data"):
        role_skills("Astronaut")


def test_data_source_has_name_url_and_licence():
    source = load_data_source()
    assert source["name"] and source["url"] and source["licence"]
    assert source["postings_used"] == 8042


def test_real_validation_file_means_not_yet_evaluated():
    assert not has_pilot_results(load_validation_results())


def test_missing_or_broken_json_gives_none_values(tmp_path):
    assert all(v is None for v in load_data_source(tmp_path / "missing.json").values())
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert not has_pilot_results(load_validation_results(broken))


def test_pilot_results_are_detected_only_when_numbers_exist(tmp_path):
    # Test fixture only; these are not real results.
    path = tmp_path / "pilot.json"
    path.write_text('{"precision": 0.5, "notes": "test fixture"}', encoding="utf-8")
    assert has_pilot_results(load_validation_results(path))
