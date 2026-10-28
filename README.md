# SkillsGap

**Is your syllabus job-ready?** SkillsGap compares a university course syllabus with the skills that job ads mention, and gives lecturers a subject-level checklist of *potential* skill gaps, with the evidence behind every result.

Team **ArgonUT** · HackSpire Lumina, UNITEN · Prototype

![Start screen](docs/screenshots/start.png)

![Results dashboard for the fictional "Introduction to Data Analytics" sample](docs/screenshots/dashboard.png)

*Screenshots show the app's real output for a fictional sample syllabus (not a real UNITEN course).*

---

## What it does

1. **Add a syllabus:** upload a PDF or Word file, paste the text, or pick one of 3 fictional samples.
2. **Choose a target job:** 12 roles, such as Data Analyst, Cybersecurity Analyst or Civil Engineer.
3. **See the results:** a coverage score, the potential gaps, a chart by skill category, the skills found, and the sentence from the syllabus behind each one. Tiles can be dragged to rearrange.
4. **Validate:** a lecturer marks each skill in a template, and the app reports precision, recall and F1 for both matching methods.

Results are **decision support only**. "Not detected" means the skill's words were not found in the text. It does not mean the skill is not taught.

## Status (read this first)

- **Not yet validated.** No comparison with lecturers on real syllabi has been published yet, so there are **no accuracy figures**. The Validate page is the tool for doing this.
- **The scoring formulas are placeholders** (see [Method](#method)). The ML team may replace them.
- **The job data is mostly from the US**, from April 2024. It contains no Malaysian postings (see [Data](#data)).

---

## Run it on your computer (Windows PowerShell)

You need Python 3.12. Open PowerShell in the project folder (the one that contains `server.py`), then:

```powershell
py -3.12 -m venv .venv               # once: create the virtual environment
.\.venv\Scripts\Activate.ps1         # every time: activate it
pip install -r requirements.txt      # once: install the pinned packages
uvicorn server:app --reload          # start the app
```

Open **http://127.0.0.1:8000**. Press **Ctrl+C** to stop.

If PowerShell blocks `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### Run the tests

```powershell
python -m pytest -q
```

Expected: `60 passed`. The tests cover text extraction, the matcher (including "Java" not matching inside "JavaScript" and "R&D" not counting as R), the data checks and the validation maths.

---

## Publish the code on GitHub

The easiest option is **GitHub Desktop** (https://desktop.github.com). It follows `.gitignore`, so the virtual environment, caches and any PDF/Word files are left out.

1. Create a free GitHub account, then install GitHub Desktop and sign in.
2. **File → Add local repository →** choose the project folder → **create a repository** here.
3. Check the list of changed files. It must **not** contain `.venv`, `__pycache__`, `.pdf` or `.docx` files. It should be about 50 files (under 1 MB).
4. Write a summary (for example "SkillsGap prototype") → **Commit to main**.
5. **Publish repository**. Untick "Keep this code private" if you want judges to be able to read the code → **Publish**.

<details>
<summary>Prefer the command line?</summary>

Install Git (`winget install --id Git.Git -e`), open a new PowerShell window in the project folder, then:

```powershell
git init
git add .
git status                      # check: no .venv, no .pdf/.docx files
git commit -m "SkillsGap prototype"
git branch -M main
git remote add origin https://github.com/YOUR-NAME/skillsgap.git   # create this empty repo on github.com first
git push -u origin main
```
</details>

---

## Optional: put it online with Render (free)

The app runs on localhost (see above). To share a public link instead, the repo already includes `render.yaml` (a Render "Blueprint") and `.python-version` (Python 3.12.7).

> **Free-tier note:** Render's free web services spin down after 15 minutes without traffic, and waking up takes about a minute ([Render docs](https://render.com/free), [Render free-tier article](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)). Open the link a few minutes before you need it. The page tells visitors when the server is waking up.

1. Publish the code on GitHub (above), then sign up at https://render.com with your GitHub account.
2. **New → Blueprint** → pick your `skillsgap` repo → **Apply**. Render reads `render.yaml`, which sets:
   - plan **free**, region **Singapore**;
   - build `pip install -r requirements.txt`;
   - start `uvicorn server:app --host 0.0.0.0 --port $PORT`;
   - health check `/api/health`.
3. Wait for the first build (a few minutes). Your link looks like `https://skillsgap-xxxx.onrender.com`.
4. Check it works: open `https://YOUR-LINK/api/health`. It should show `{"ok":true}`.

If you'd rather click through the settings yourself, choose **New → Web Service** and enter the same build command, start command and health check path as above. After that, every push to GitHub redeploys the app automatically.

---

## Method

SkillsGap uses **dictionary-based matching**, not AI. Every result shows its evidence, so a lecturer can check it.

1. **Read the text** from the PDF/Word file (pdfplumber, python-docx) or the pasted text. Scanned PDFs (images of pages) are rejected.
2. **Look up the role's skills:** each role has 28 to 30 skills from a dictionary of 244. Each skill has a category and synonyms.
3. **Search for each skill as whole words or phrases:**
   - **Exact (Level 1):** the skill name only.
   - **Smart (Level 2):** the name plus its synonyms, for example "Splunk" for SIEM. These are the same rules the data team used to count the job ads.
   - **Short, ambiguous names** are matched case-sensitively as stand-alone words. These are R, C, Go, Excel, SAS, React, Sketch, Spark, ML, IR, IDS and IPS. R, C and Go also need a nearby word such as "programming" or "Python".
4. **Status** from the number of mentions:
   - 2 or more: *Detected in syllabus*
   - 1: *Briefly mentioned*
   - 0: *Not detected in syllabus text*
   - Not detected **and** mentioned in at least 20% of the role's job ads: *Potential skill gap*

**Scores (placeholder formulas, to be replaced by the ML team).** Demand is the share (0 to 1) of the role's job ads that mention the skill.

```
coverage weight   = 1 (detected), 0.5 (briefly mentioned), 0 (not detected)
gap score         = demand × (1 − coverage weight)
coverage score    = 100 × sum(demand × coverage weight) ÷ sum(demand)
category coverage = the coverage score, using only that category's skills
category demand   = 100 × average demand of that category's skills
```

The contract between the web app and the analysis code is in [docs/INTERFACE.md](docs/INTERFACE.md). A teammate can replace `analysis/matcher.py` without touching the web page, as long as `analyze()` keeps the same output format. The server checks every result against that format.

### Limitations

- **Missed skills:** a syllabus can teach something without using its name. For example, "examine system logs for attacks" is SIEM work.
- **False detections:** a word can appear in an unrelated context, such as a reading list.
- **No teaching depth:** the text cannot show how well a topic is taught.
- **Dictionary only:** skills that are not in the dictionary are never found.
- **Equal weight:** every mention counts the same, wherever it appears in the syllabus. Section-aware weighting is planned.

---

## Validation

### How to run a pilot

1. Analyse a real syllabus.
2. On the **Validate** page, download the template (the role's skills with an empty `reviewer_status` column).
3. A lecturer who knows the course fills in `covered`, `brief` or `not_covered` for each skill, ideally *before* seeing the app's results.
4. Upload the file. The page shows precision, recall and F1 for Exact and Smart side by side, plus every disagreement with its evidence.
5. To publish pilot results in the app, the data team records the totals in `data/validation_results.json`. The app then shows them with the sample size and the label "Pilot, small sample, not generalisable". Until then it shows "Not yet evaluated".

### The formulas, with a worked example

"Covered" means the app found the skill (Detected, and by default also Briefly mentioned) and the lecturer said covered (or brief). A switch on the Validate page treats "brief" as not covered on both sides.

- **Precision** = correct detections ÷ all detections by the app
- **Recall** = correct detections ÷ all skills the lecturer says are covered
- **F1** = 2 × precision × recall ÷ (precision + recall)

**Worked example** (teammates can check the maths by hand): the app says **14** skills are covered, **10** of them correctly, and the lecturer says **12** skills are covered.

| | Calculation | Result |
|---|---|---|
| Correct detections (TP) | | 10 |
| False detections (FP) | 14 − 10 | 4 |
| Missed (FN) | 12 − 10 | 2 |
| **Precision** | 10 ÷ 14 | **0.714** (71%) |
| **Recall** | 10 ÷ 12 | **0.833** (83%) |
| **F1** | 2 × 10 ÷ (2 × 10 + 4 + 2) = 20 ÷ 26 | **0.769** |

This exact example is a test: `tests/test_validation.py::test_worked_example_14_detected_10_correct_12_covered`.

If fewer than 10 skills are compared, the page warns that the sample is too small to draw conclusions.

---

## Data

| | |
|---|---|
| Source | [LinkedIn Job Postings (2023 - 2024)](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings) by Arsh Koneru, Kaggle |
| Licence | CC BY-SA 4.0 |
| Collection | Public licensed dataset (no scraping) |
| Postings used | 8,042, listed in April 2024 |
| Region | Global, but almost all from the US. **No Malaysian postings.** |
| Roles | 12, assigned from job-title keywords |

**Attribution (required by the licence):** Job-market data derived from 'LinkedIn Job Postings (2023 - 2024)' by Arsh Koneru, Kaggle, CC BY-SA 4.0 (https://www.kaggle.com/datasets/arshkon/linkedin-job-postings). Filtered and counted by Team ArgonUT.

The derived files in `data/` are shared under **CC BY-SA 4.0**. Full details (title mapping, steps, the data team's own spot check, known biases) are in [data/DATA_README.md](data/DATA_README.md). The raw dataset is **not** in this repo. To rebuild the files, download `postings.csv` from Kaggle and run, **from the project root**:

```powershell
python data/prepare_data.py --raw postings.csv
```

Data limits to keep in mind:
- A mention in a job ad is not always a requirement.
- Soft skills such as "collaboration" probably score higher than true demand.
- Role sizes are uneven: Software Engineer has 2,442 ads, UI/UX Designer has 226.

---

## Privacy and responsible use

- **Nothing is stored.** Syllabi are processed in server memory and forgotten after each request. Uploads are sent inside the request itself, so they are never written to a temporary file on disk, and they are never logged. Results, review answers and ratings stay in the browser tab only.
- **People decide.** SkillsGap supports a lecturer or curriculum committee. It makes no curriculum or accreditation judgement.
- **"Not detected" ≠ "not taught".**
- **No real syllabi in this repo.** `.gitignore` blocks `.pdf` and `.docx` files. The 3 samples in `samples/` are fictional and were written for this demo.
- **Security:**
  - The page loads nothing from other websites, and a Content Security Policy enforces this.
  - Text from syllabi and CSV files is always shown as plain text, never as HTML.
  - Requests over 8 MB are rejected.
  - Errors show a short message, never technical details.
  - Downloaded CSV cells cannot run as spreadsheet formulas.

---

## Project structure

```
server.py              FastAPI server: JSON API + serves web/
web/                   the web page: index.html, css/styles.css, js/*.js (no build step)
analysis/              matcher.py (analyze), skill_rules.py, validation.py, contract.py
utils/                 text_extraction.py, data_loading.py, samples.py
data/                  job-market data from the data team (read-only, CC BY-SA 4.0)
samples/               3 fictional sample syllabi
tests/                 pytest tests (60)
docs/                  INTERFACE.md, screenshots/
requirements.txt       pinned Python packages
render.yaml, .python-version   optional Render deployment
PROJECT_LOG.md         decisions, milestones, known issues
```

API used by the page:

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/meta` | Roles, samples, data source, pilot status |
| `POST /api/analyze` | Analyse a syllabus, returning both Exact and Smart results |
| `POST /api/validate` | Compare the results with a lecturer's CSV |

---

## AI assistance and credits

- **AI assistance:** an AI coding assistant (Kiro) was used to write most of the code, tests and documentation in this repository, under the team's direction. The team reviewed and tested the results. The team confirmed that AI assistance is allowed in this competition.
- **Data:** "LinkedIn Job Postings (2023 - 2024)" by Arsh Koneru (Kaggle, CC BY-SA 4.0). Filtering, role mapping, skill dictionary and counts were done by the ArgonUT data team.
- **Draggable tile grid:** the layout and drag logic in `web/js/grid.js` are a plain-JavaScript port of the team's reference component "Draggable Widget Grid" (React + Motion).
- **Open-source libraries:** FastAPI, Uvicorn, pandas, pdfplumber, python-docx and pytest.

## Licence

- **Data files** in `data/`: CC BY-SA 4.0 (required by the source dataset).
- **Code:** the team has not chosen a licence yet.
