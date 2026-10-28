# SkillsGap interface contract

This is the agreement between the web app (UI) and the data/ML part.
If you replace `analysis/matcher.py` or the files in `data/`, keep these formats
and the UI keeps working without changes.

## 1. The function

```python
from analysis.matcher import analyze
result = analyze(syllabus_text: str, role: str, method: str = "level1") -> dict
```

- `method`: `"level1"` (skill name only) or `"level2"` (skill name + synonyms).
- Errors: raise `analysis.matcher.AnalysisError` (a `ValueError`) with a friendly,
  user-facing message for empty or short text, an unknown role or an unknown method.
  Raise `utils.data_loading.DataError` if the data files are broken.
  The UI shows the message. It never shows a stack trace.

## 2. The returned dict

| Key | Type | Meaning |
|---|---|---|
| `role` | str | The role that was analysed |
| `method` | str | `level1` or `level2` |
| `method_notes` | str | One line describing what the module did (shown in the Method section) |
| `postings_used` | int | Number of job postings for this role (`total_postings`) |
| `skills_checked` | int | Number of skills checked for this role |
| `coverage_score` | float | 0 to 100, see section 4 |
| `skills` | list[dict] | One entry per skill of the role, see below |
| `category_summary` | list[dict] | `{"category": str, "coverage": float, "demand": float}`, both 0 to 100 |

Each entry in `skills`:

| Key | Type | Required? | Meaning |
|---|---|---|---|
| `skill` | str | yes | Skill name, as in `data/skills.csv` |
| `category` | str | yes | Category from `data/skills.csv` |
| `demand` | float | yes | 0 to 1: share of the role's postings that mention the skill |
| `status` | str | yes | `detected` (2+ mentions), `brief` (1), `not_detected` (0) |
| `mentions` | int | yes | Number of mentions in the syllabus |
| `evidence` | str or None | yes | The sentence around the first mention |
| `gap_score` | float | yes | See section 4 |
| `explanation` | str | yes | Plain English. Never says "missing" or "not taught" |
| `matched_terms` | list[str] | optional | The words found, as written in the syllabus (e.g. `["Splunk"]` for SIEM) |
| `section` | str or None | optional | Syllabus section of the first mention, if known. Currently always `None` |
| `evidence_span` | [int, int] or None | optional | Start and end of the matched word inside `evidence`, for highlighting |

The UI must work if the optional keys are missing.

## 3. Data files (built by `data/prepare_data.py`, read-only for the app)

| File | Columns / keys |
|---|---|
| `data/skills.csv` | `skill,category,synonyms,ambiguous` (synonyms separated by `;`, may be empty; ambiguous is the text `true`/`false`) |
| `data/role_skill_demand.csv` | `role,skill,demand,postings_count,total_postings` (demand 0 to 1, 3 decimals) |
| `data/data_source.json` | `name, url, licence, collection_method, date_range, region, postings_used, roles, notes` |
| `data/validation_results.json` | `syllabi_reviewed, skills_reviewed, precision, recall, f1, lecturer_usefulness_avg, notes` (all `null` until a real pilot) |

Full details: `data/DATA_README.md`. `utils/data_loading.py` checks these files when the
app starts (12 roles, every demand skill exists in `skills.csv`, demand = count / total).

## 4. Scoring: PLACEHOLDER formulas, to be replaced by the ML team

```
coverage_weight   = 1.0 (detected), 0.5 (brief), 0.0 (not detected)
gap_score         = demand x (1 - coverage_weight)
coverage_score    = 100 x sum(demand x coverage_weight) / sum(demand)
category coverage = the coverage_score formula, using only that category's skills
category demand   = 100 x average demand of that category's skills
```

## 5. Matching rules

The syllabus is matched with the same rules that counted the job postings.
They are ported from `data/prepare_data.py` into `analysis/skill_rules.py`:

- Whole words and phrases, case-insensitive, with `(?<!\w)TERM(?!\w)` so that
  `C++`, `C#`, `.NET` and `Security+` work, and "Java" does not match inside "JavaScript".
- Ambiguous short names (R, C, Go, Excel, SAS, React, Sketch, Spark, ML, IR, IDS, IPS)
  are matched case-sensitively as standalone tokens. R, C and Go also need a context
  word (such as "programming" or "Python") within 60 characters.
- The token list `AMBIGUOUS_TOKENS` lives in code, because `skills.csv` only stores
  `ambiguous=true/false`. The app checks at start-up that both lists agree.
- If the data team changes the rules in `prepare_data.py`, copy the change into
  `analysis/skill_rules.py`. `tests/test_matcher.py` compares the two on test sentences.
