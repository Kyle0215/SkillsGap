# SkillsGap: job-market skill-demand data

Team ArgonUT, HackSpire Lumina, UNITEN.

This folder holds the skill-demand data that the SkillsGap app compares against a course syllabus.

## Files

| File | What it is |
|---|---|
| `data/skills.csv` | Skill dictionary: `skill,category,synonyms,ambiguous` (244 skills; synonyms separated by `;`) |
| `data/role_skill_demand.csv` | `role,skill,demand,postings_count,total_postings` (350 rows, 28 to 30 skills per role) |
| `data/data_source.json` | Source, licence, date range, region, postings used, notes |
| `data/validation_results.json` | Placeholder. Not yet evaluated, so all numbers are `null` |
| `prepare_data.py` | Rebuilds the first three files from the raw dataset |

`demand` is the share of a role's postings that mention the skill, from 0 to 1, rounded to 3 decimals.
For example, `Data Analyst,SQL,0.625,232,371` means 232 of the 371 Data Analyst postings mention SQL.

## Source and licence

- **Name:** LinkedIn Job Postings (2023 - 2024), by Arsh Koneru, on Kaggle
- **URL:** https://www.kaggle.com/datasets/arshkon/linkedin-job-postings
- **Licence:** CC BY-SA 4.0. You must credit the source. Files derived from it (these CSV/JSON files) must also be shared under CC BY-SA 4.0.
- **Collection method:** public licensed dataset. We did no scraping.
- **Date range of the postings used:** 2024-04 to 2024-04. The raw file covers 2024-03-24 to 2024-04-20, and its only March posting did not match any of our roles.
- **Region:** Global. The dataset has **0 Malaysian postings** (we searched locations for Malaysia, Kuala Lumpur, Selangor, Penang, Johor, Putrajaya and Cyberjaya). Nearly all postings are in the United States.

The raw dataset is **not** in the repo (see `.gitignore`). To rebuild:

```
# 1. Download the dataset from Kaggle and put postings.csv next to prepare_data.py
# 2. Run (Python 3.12 + pandas):
python prepare_data.py --raw postings.csv
# Optional: print postings per role only, or 20 random matches to check by hand
python prepare_data.py --raw postings.csv --counts-only
python prepare_data.py --raw postings.csv --hand-check 20
```

## Steps

1. **Load.** Read only `title`, `description`, `listed_time` and `location` (123,849 rows). Company names, URLs and any contact details are never loaded, so no personal data reaches the output files.
2. **Clean.** Drop 7 rows with no description. Drop exact duplicates (same title and description). That leaves 110,898 rows.
3. **Assign roles.** Each title is lower-cased and checked against the keywords below, in the order of the role list. The first role that matches wins, and each posting gets **one role only**. Titles with none of the keywords are dropped. All seniority levels are kept. Result: **8,042 postings**.
4. **Build the skill dictionary.** Each role has 25 to 30 skills and at most 8 categories. Skills can be shared between roles. Each skill has a list of synonyms and abbreviations.
5. **Count skills.** For each role and skill, count the postings whose `description` mentions the skill or any synonym as a whole word or phrase (`re.escape`, case-insensitive). Our pattern works like `\b...\b`, and it also handles names that start or end with a symbol, such as `C++`, `C#`, `.NET` and `Security+`. Because of this, "Java" does not match inside "JavaScript".
6. **Ambiguous skills** (`ambiguous=true`): R, C, Go, Excel, SAS, React, Sketch, Apache Spark (as "Spark"), Machine Learning (as "ML"), Incident Response (as "IR") and IDS/IPS (as "IDS" and "IPS"). Their short form is matched **case-sensitively** as a standalone token. It can't be glued to `&`, `-`, `.`, `+` or `#`, so "R&D", "Objective-C", "C++" and "go-to-market" don't count. **R, C and Go** also need a context word within 60 characters, such as "programming", "language", "Python", "SQL", "C++" or "embedded". Clear forms like "RStudio", "R programming", "C language" or "Golang" are matched normally.
7. **Compute demand.** `demand = postings_count / total_postings` for the role.

## Title mapping (keywords per role)

Titles containing recruiter, recruiting, recruitment, sales, business development, technician, instructor, professor, teacher, lecturer or faculty are skipped for every role.

| Role | Title keywords (whole phrase, case-insensitive) |
|---|---|
| Data Analyst | data analyst, data analytics analyst, analytics analyst, business intelligence analyst, bi analyst |
| Cybersecurity Analyst | cybersecurity / cyber security / cyber-security analyst, security analyst, soc analyst, security operations analyst, cyber analyst, cyber threat analyst, threat intelligence analyst, incident response analyst, vulnerability analyst, penetration tester, cybersecurity / cyber security engineer, security engineer, cybersecurity / cyber security / information security specialist, cybersecurity / cyber security consultant |
| Software Engineer | software engineer, software developer, software development engineer, software engineering, full stack / full-stack / fullstack developer or engineer, backend / back end / back-end developer or engineer, frontend / front end / front-end developer or engineer, web developer, application(s) developer, java / python / .net / dotnet / c# / ios / android / mobile / react / javascript developer |
| Data Scientist | data scientist, data science, machine learning engineer, machine learning scientist, ml engineer, applied scientist |
| Network Engineer | network engineer, network engineering, network administrator, network architect |
| Cloud Engineer | cloud engineer, cloud architect, cloud solutions architect, cloud infrastructure / platform / operations engineer, cloud developer, cloud administrator, cloud consultant, devops engineer, devops architect, aws / azure engineer or architect, gcp engineer. *Titles containing "salesforce" are excluded (CRM work).* |
| Electrical Engineer | electrical engineer, electrical engineering, electrical design engineer, electrical designer, electrical controls engineer, electrical project engineer, power systems engineer |
| Mechanical Engineer | mechanical engineer, mechanical engineering, mechanical design engineer, mechanical designer, mechanical project engineer |
| Civil Engineer | civil engineer, civil engineering, structural engineer, geotechnical engineer, transportation engineer, traffic engineer, water resources engineer |
| UI/UX Designer | ui/ux designer, ux/ui designer, ui/ux, ux/ui, ux designer, ui designer, ux researcher, ux research, ux lead, ux architect, user experience designer / researcher / specialist / lead, user interface designer, product designer, interaction designer |
| Business Analyst | business analyst, business systems analyst, business analysis |
| Project Manager | project manager |

Examples: "Junior Data Analyst" maps to Data Analyst. "Senior Network Engineer II" maps to Network Engineer. "Business Data Analyst" maps to Data Analyst, because Data Analyst comes first in the list.

## Postings per role

| Role | Postings | Flag |
|---|---|---|
| Data Analyst | 371 | |
| Cybersecurity Analyst | 403 | |
| Software Engineer | 2,442 | |
| Data Scientist | 415 | |
| Network Engineer | 308 | |
| Cloud Engineer | 396 | |
| Electrical Engineer | 405 | |
| Mechanical Engineer | 323 | |
| Civil Engineer | 309 | |
| UI/UX Designer | 226 | |
| Business Analyst | 605 | |
| Project Manager | 1,839 | |
| **Total** | **8,042** | |

**Low-sample roles (under 30 postings):** none. **Roles left out (0 postings):** none.

## Hand-check of 20 random matches

We drew 20 matches at random (`--hand-check 20`, seed 42) and read the text around each one.
**18 of 20 were correct.** This only checks our keyword matching. It is **not** an accuracy figure for the app.

Wrong or doubtful matches:

| # | Role | Skill | Text around the match | Why it's wrong |
|---|---|---|---|---|
| 1 | Project Manager | Leadership | "...time management skills. Executive leadership communication..." | The phrase means communicating *with* executives. It doesn't ask for leadership skill. |
| 13 | Cybersecurity Analyst | SIEM | "...monitoring and data analysis tools such as Splunk, Sitescope, Grafana..." | Splunk is listed as a monitoring tool here, not for SIEM or security work. It's borderline, so we count it as wrong. |

The other 18 were correct: C++, Linux, Kubernetes (×2), SQL, JavaScript (×2, one as "JS"), Java, AWS, Agile, PMP, Motor Controls, User Stories, Microsoft Office ("MS Office"), Problem Solving (×2) and Communication (×2).

The random sample happened to contain no ambiguous skills, so we also read 5 random matches each for Software Engineer/Go, Software Engineer/C, Data Scientist/R, UI/UX Designer/Sketch, Cybersecurity Analyst/IDS/IPS, Cybersecurity Analyst/Incident Response and Data Analyst/SAS. All 35 were real mentions of the skill (for example "Python, Scala, or R", "C/C++", "Python or Golang", "Figma, Sketch, or InVision"). This extra check is not part of the 20.

## Known limitations and biases

- **Not Malaysian data.** There are 0 Malaysian postings, and the data is almost all from the US. Demand shows what US employers ask for, which may differ from Malaysian employers.
- **Short time window.** All postings used were listed in April 2024 (about 4 weeks). Seasonal hiring and trends since then are not captured.
- **LinkedIn only, English only, online only.** Jobs advertised elsewhere (JobStreet, company sites, word of mouth) are missing.
- **Role sizes are uneven.** Software Engineer (2,442) and Project Manager (1,839) are much larger than UI/UX Designer (226).
- **Project Manager covers all industries**, including construction and marketing PMs, so its skill list is broad.
- **Cybersecurity Analyst includes security engineers.** Analyst-only titles would give far fewer postings.
- **Roles come from titles only.** Unusual titles are missed, and a posting can only have one role.
- **A mention isn't always a requirement.** Keyword matching can't tell "required" from "nice to have", and it can pick up company boilerplate (see the Leadership example above).
- **Some synonyms are broad.** For example, "collaboration" counts as Teamwork, "routing" as Routing and Switching, and "sap" as ERP. Soft-skill and broad-term counts are probably higher than true demand.
- **Near-duplicates remain.** Only exact duplicates were removed, so reposts with small edits still count.
- **The dictionary is hand-made.** Skills that aren't in it are never counted.

## Attribution

Data derived from "LinkedIn Job Postings (2023 - 2024)" by Arsh Koneru, Kaggle, licensed CC BY-SA 4.0
(https://www.kaggle.com/datasets/arshkon/linkedin-job-postings). We filtered, mapped and counted the data as described above.
The derived files in `data/` are shared under CC BY-SA 4.0.
