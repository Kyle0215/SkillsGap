# SkillsGap – Project Log

Team ArgonUT · HackSpire Lumina, UNITEN. Submitted on GitHub; runs on localhost (`uvicorn server:app --reload` → http://127.0.0.1:8000).

## Architecture
- `server.py` (FastAPI): serves `web/` and a JSON API. Stateless: the server keeps nothing between requests.
  - `GET /api/health`: health check.
  - `GET /api/meta`: roles (+ postings), samples, data source, pilot status and figures (only real numbers from `data/validation_results.json`), gap threshold, limits, attribution.
  - `POST /api/analyze`: `{source: upload|paste|sample, role, text?, sample?, filename?, file_base64?}` → `{role, source_label, elapsed_seconds, results: {level1, level2}}`. Both methods are returned so the page switches Smart/Exact instantly.
  - `POST /api/validate`: `{reference_base64, results: {level1, level2}}` → `{rows, blank, comparisons: {brief_on|brief_off: {level1, level2}}}`, using the tested `parse_reference_csv` / `compare_with_reviewer`.
  - Uploads travel as base64 inside JSON so they stay in memory (Starlette writes multipart uploads over 1 MB to a temp file on disk).
  - Errors are always `{"error": "<friendly message>"}`; unexpected errors log only type/path/line, never the message (it could contain syllabus text). Request bodies over 8 MB are rejected. Security headers on every response (CSP `'self'` only, nosniff, no-referrer, frame DENY); API responses are `no-store`.
- `web/`: plain HTML/CSS/JavaScript, no build step.
  - `index.html` (all views), `css/styles.css`.
  - `js/app.js` (hash router: #/, #/results, #/validate, #/about), `js/start.js`, `js/results.js` (dashboard), `js/grid.js` (draggable tile grid), `js/charts.js` (coverage ring + radar, SVG), `js/validate.js`, `js/about.js`, `js/shared.js` (status labels, evidence highlight, CSV helpers), `js/api.js`, `js/dom.js` (safe element builder: strings are always text, never HTML).
  - Results, review answers and the rating live in browser memory only (no localStorage/sessionStorage); reloading clears them.
- `analysis/`: `matcher.py` (`analyze()`, the contract in `docs/INTERFACE.md`), `skill_rules.py` (matching rules ported from the data team's `data/prepare_data.py`, plus `find_all()` and evidence snippets), `validation.py` (precision/recall/F1 against a reviewer CSV), `contract.py` (`check_result()`: every `analyze()` result is checked before the page uses it).
- `utils/`: `text_extraction.py` (PDF/DOCX/pasted text → cleaned text, in memory; rejects empty, too short, too long > 200,000 chars, over 5 MB, scanned PDFs, wrong types), `data_loading.py` (cached, checked loading of `data/*`; never writes to `data/`), `samples.py`.
- `samples/`: 3 fictional sample syllabi (not real UNITEN courses).
- `tests/`: 60 pytest tests (text extraction, matcher incl. parity with the data team's script, data checks, validation maths incl. the 14/10/12 worked example).
- Optional hosting: `render.yaml` (Render free plan, Singapore) + `.python-version` (3.12.7).

## Data (delivered by the data team)
- Source: "LinkedIn Job Postings (2023 - 2024)" by Arsh Koneru, Kaggle, CC BY-SA 4.0 (public licensed dataset, no scraping).
- 8,042 postings, listed April 2024, region "Global" but almost all US, 0 Malaysian postings.
- 244 skills, 350 role–skill rows, 12 roles, 28–30 skills per role, 6–8 categories per role.
- Files in `data/` are read-only for the app and stay under CC BY-SA 4.0. Ask the data team before changing `data/` or `data/prepare_data.py`.
- The data team's hand-check (18 of 20 keyword matches correct) checks their pipeline only. It is never shown as the app's accuracy.

## Decisions
- Theme: Navy #102A43 (text), Teal #14B8A6 (main button), Amber #F0B429 (skill-gap highlights only), Off-white #F5F7FA (background), White #FFFFFF (cards). Darker shades only where WCAG contrast needs them: dark teal #0F766E, navy shades #334E68 / #486581 / #BCCCDC / #D9E2EC. Light mode only. English only.
- Detection: dictionary matching with the data team's rules. Exact (Level 1) = skill name only; Smart (Level 2) = name + synonyms, exactly the rules used on the job postings. Default: Smart.
- Ambiguous short names (R, C, Go, Excel, SAS, React, Sketch, Spark, ML, IR, IDS, IPS) are case-sensitive stand-alone tokens; R, C and Go need a context word within 60 characters. The ported matcher only uses strict tokens that are among its own terms, so Exact skips synonym tokens like "ML".
- Overlapping matches count once ("Apache Spark" also contains "Spark").
- Status labels: Detected in syllabus (2+ mentions), Briefly mentioned (1), Not detected in syllabus text (0), Potential skill gap (not detected and in ≥ 20% of the role's job ads). Never "missing".
- Scoring formulas are placeholders (`docs/INTERFACE.md` §4), to be replaced by the ML team.
- Soft skills (category "Soft Skills") are shown separately from technical gaps.
- Validation: "brief" counts as covered by default on both sides; a switch turns this off. Pilot figures are shown only from real data, with the sample size and "Pilot · small sample · not generalisable"; otherwise "Not yet evaluated".
- Feedback: in-session 1–5 rating only (no form, nothing saved).
- Dashboard: 7 draggable tiles (Coverage, Top gaps, Soft skills, Validation, By category, Found in syllabus, Evidence). Clicking any skill updates the Evidence tile. Review answers (Correct / Wrong / Unsure) can be downloaded as CSV (agreed columns; `comment` left empty). CSV cells starting with = + - @ get a leading ' so spreadsheets don't run them as formulas.
- Radar: two series, coverage (solid, circles) and job-ad demand (dashed, diamonds). With 0% coverage everywhere, a note explains that the visible shape is demand only.
- Responsible use wording follows the user's edit (no "ads from one website and one period…" sentence there); the US/Malaysia note stays next to the data facts.
- AI assistance is allowed in this competition (confirmed by the team) and is disclosed in the README.

## History
- v1 was a Streamlit app (milestones a–f: skeleton, text extraction, matcher + data, pages, method/validation pages, error handling + accessibility). It was replaced by the HTML/CSS/JS + FastAPI web app in four stages (start screen, dashboard, validate + about, README + deployment) and then **removed** at the user's request before submission. The analysis code, data, samples and tests were kept unchanged.
- Bug-fix passes after the redesign: All-skills table numbers drawn as circles (CSS class clash, fixed by renaming the step badge to `.step-num`); table too wide on phones (Category column hidden below 560 px); zero-coverage radar note added; BOMs removed from three web files; personal paths removed from the README.

## Verification (latest)
- 60 tests pass. All 36 role × sample combinations analyse. Bad requests return 400 with a friendly message. `server.py`, `data/` and the README cannot be downloaded through the web server.
- Edge at 1366, 900 and 390 px: every view checked (start in all three input modes; results in Smart and Exact with the table open; validate with a reviewer file; about; all 3 samples). 0 axe-core WCAG 2.1 AA violations, no clipped text, no tile overflow, no sideways scrolling, no console errors.

## Known issues / TODO
- Not yet validated with a lecturer on a real syllabus. TODO (team): run a pilot and record the totals in `data/validation_results.json` via the data team.
- Drag-and-drop not yet tried on a real touch screen (long-press logic is ported from the reference; mouse and keyboard were tested).
- Not tested: screen readers (NVDA/JAWS), 200% zoom.
- TODO (optional): section-aware weighting (learning outcomes / weekly topics / assessment at full weight; references lower).
- Scanned-PDF check is a heuristic (< 50 characters of text per page on average).
- `data/prepare_data.py` writes to `data/` relative to the current folder: run it from the project root. `data/DATA_README.md` says otherwise; not changed (data team's file). `data/prepare_data.py` also starts with a UTF-8 BOM (harmless).
- Known matching misses (limitation, not a bug): e.g. "clean data" does not match Data Cleaning.
- TODO (team): choose a licence for the code (the data must stay CC BY-SA 4.0).
