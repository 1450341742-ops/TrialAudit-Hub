# TrialAudit Hub

Clinical audit project management and operations analytics for internal teams.

TrialAudit Hub reads the existing **项目管理部每周汇报表** and **中心稽查项目流程记录表** directly. It does not require users to rebuild the source workbooks or copy data into a new template.

## MVP features

- Upload and automatically identify the two Excel workbooks.
- Monthly plan vs actual, cumulative progress, annual completion rate and drill-down project ledger.
- Process tracking for kickoff letter, materials, DingTalk space, EDC, confirmation letter, report, CAPA and finalization.
- Staff workload based on de-duplicated occupied dates, maximum consecutive days and same-day project conflicts.
- Part-time auditor days, costs, name normalization and manual-review notes.
- Data-quality checks for missing project IDs, invalid dates, duplicates and unconfirmed phases.
- Rule-based management summary with metric and project evidence.
- Export structured analysis results to Excel.

> The repository contains no real project data. Uploaded files are processed only in the running Streamlit session.

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` and upload the two source workbooks.

## Demo workbooks

Generate synthetic test workbooks without real names, phone numbers or project information:

```bash
python scripts/generate_demo_data.py
```

Then upload `demo_data/weekly_demo.xlsx` and `demo_data/flow_demo.xlsx`.

## Run tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

## Docker

```bash
docker build -t trialaudit-hub .
docker run --rm -p 8501:8501 trialaudit-hub
```

## Current scope

This is the first runnable MVP. It uses session-based analysis and does not yet include user authentication, PostgreSQL/Supabase persistence, DingTalk notification delivery, or an external LLM call. The code is modular so those capabilities can be added without rewriting the core import and metric logic.

## Metric conventions

- Actual monthly audits are counted by audit end date.
- Reserved IDs and rows without a valid project/site combination are excluded.
- Staff journey days are de-duplicated by person and calendar date.
- 15–17 journey days per month are marked **关注**; 18 or more are **高负荷**.
- Blank workflow fields are shown as unrecorded/pending confirmation, not automatically treated as incomplete work.
