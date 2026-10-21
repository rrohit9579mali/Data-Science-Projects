# AI Excel Cleaning & Business Analysis Assistant

A Streamlit app for non-technical users: **upload a messy Excel/CSV file → get a cleaned workbook →
see live KPIs → get a validated AI report → ask questions in plain language** (English or Hinglish).

> Built with Python, Pandas, OpenPyXL, Plotly, Pydantic, Streamlit and the Gemini API.

<!-- TODO: add 2-3 screenshots of your own run here (cleaning tab, AI report, chat) -->

## Why this project is different from "paste a CSV into an LLM"

| Problem with naive LLM data tools | What this project does |
|---|---|
| Dirty data → wrong answers | A rule-based **cleaning engine** fixes safe issues and *flags* risky ones instead of silently changing them |
| LLMs invent numbers | Report is returned as **JSON validated by Pydantic**, and every number is **cross-checked against statistics computed by code** (unverified numbers are shown as warnings) |
| Letting an LLM run code is risky | Default Q&A uses **function calling with fixed, read-only tools** - the model can only pick a tool and its arguments |
| Sending company data to an API | Gemini only sees column names, summary statistics and small results - **never the full file** (sample rows are opt-in) |

## Features

**1. Cleaning engine (`cleaner.py`)** - works on any Excel/CSV
- Detects the real header row (skips title rows), standardises column names
- Trims spaces, turns `N/A`, `null`, `-` into real blanks, removes empty rows/columns
- `₹1,200` / `(500)` → numbers, `15-01-2026` → real dates (day-first option), keeps `007` and phone numbers as text
- Unifies `North` / `north` / `NORTH`
- Removes **only exact** duplicate rows (kept in a separate sheet)
- **Never** auto-fills missing values with 0; median-fill is opt-in
- Flags for human review (never changed): negative amounts, extreme outliers (3×IQR), repeated IDs, unreadable numbers/dates
- Downloads: cleaned `.xlsx` (with `Cleaning_Log`, `Review_Needed`, `Removed_Duplicates`, `Column_Profile` sheets) and `.csv`

**2. Live dashboard** - KPIs, group-by charts, time trends, correlation heatmap (pure Pandas/Plotly, no AI needed)

**3. Validated AI report (`ai_agent.py`, `schemas.py`)**
- Gemini returns structured JSON (`response_schema`) → validated with Pydantic → one automatic retry on invalid output
- Grounding check: numbers that do not appear in the computed statistics are listed as *unverified*
- Download as Markdown or JSON

**4. Ask your data**
- *Safe tools mode (default)*: Gemini calls `aggregate`, `time_trend`, `value_counts`, `correlation`, `top_rows`, ... (`analytics_tools.py`). Each tool validates its inputs against the real table and returns errors the model can learn from. The UI shows which tools were called and warns if an answer was given without using any tool.
- *Advanced mode*: Gemini writes pandas code, which is AST-validated (no imports, file access, dunder attributes) before it runs.

## Architecture

```
Excel / CSV
    │
    ▼
cleaner.py ──► cleaned DataFrame + log + review flags ──► cleaned .xlsx / .csv
    │
    ├──► Plotly dashboard (app.py)
    │
    └──► ai_agent.py
           ├─ build_context()  → schema + stats + breakdowns (no raw rows by default)
           ├─ generate_structured_report() → Gemini JSON → Pydantic → grounding check
           ├─ ask_with_tools()  → Gemini function calling → analytics_tools.py (read-only)
           └─ ask_data_question() → Gemini pandas code → AST validation → exec (advanced)
```

## Run locally (with [uv](https://docs.astral.sh/uv/))

```bash
uv sync                      # installs everything from pyproject.toml
cp .env.example .env         # then put your key in .env  (Windows: copy .env.example .env)
uv run streamlit run app.py
```

Get a free key at <https://aistudio.google.com/apikey>. `.env` is git-ignored - never commit it.
The default model is `gemini-3.8-flash`; change it in the sidebar or with `GEMINI_MODEL` in `.env`.

Try it with the included dirty file: **`sample_data/messy_sales.xlsx`**
(regenerate with `uv run python sample_data/make_sample.py`).

## Tests

```bash
uv run pytest -q
```

56 tests cover the cleaning rules, Pydantic schema + grounding check, every analytics tool, the structured-report
retry logic, tool-calling flow (with a fake Gemini client - no API key or network needed) and the code-safety validator.

## Deploy (Streamlit Community Cloud)

1. Push this repo to GitHub (check that `.env` is **not** committed).
2. On <https://share.streamlit.io> create an app from the repo, main file `app.py`.
3. In *App settings → Secrets* paste: `GEMINI_API_KEY = "your_key"`.

## Known limitations (honest notes)

- Advanced code mode uses an AST allow-list, **not** a real sandbox. Fine for local use; for a public deployment run it in a
  container/subprocess with resource limits, or keep only the safe-tools mode.
- The cleaning engine infers meaning from column names and value patterns; unusual files may need the sidebar rules adjusted
  (e.g. month-first dates).
- The grounding check verifies that quoted numbers exist in the computed statistics; it cannot judge whether the
  *interpretation* is right - a human should still read the report.
- Free Gemini quota is limited; very large files only send summaries, but wide tables (80+ columns) are truncated in the context.

## Project layout

```
app.py              Streamlit UI
cleaner.py          cleaning engine + Excel export
analytics_tools.py  safe tools for Gemini function calling
ai_agent.py         Gemini client, structured report, tool-calling Q&A, advanced code mode
schemas.py          Pydantic report schema + grounding check
sample_data/        messy_sales.xlsx + generator
tests/              pytest suite
notebooks/          original exploratory notebook
```
