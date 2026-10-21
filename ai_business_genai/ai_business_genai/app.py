"""
app.py  -  AI Excel Cleaning & Business Analysis Assistant (Streamlit)

Run:  uv run streamlit run app.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from pandas.api import types as ptypes

try:  # optional: loads GEMINI_API_KEY from a local .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ai_agent import (DEFAULT_MODEL, ReportError, ask_data_question, ask_with_tools,
                      chart_from_state, format_tool_call, generate_structured_report, get_client)
from cleaner import (CleaningOptions, clean_data, list_sheets, numeric_measure_columns,
                     profile_columns, read_file, to_excel_bytes)
from schemas import report_to_markdown

st.set_page_config(page_title="AI Excel Cleaning & Analysis Assistant", page_icon="📊", layout="wide")
st.title("📊 AI Excel Cleaning & Business Analysis Assistant")
st.caption("Upload a raw Excel/CSV file → get a cleaned file → explore live statistics → "
           "get a validated AI report → ask questions in plain language.")

MISSING_CHOICES = {
    "Leave blank, only report (safest)": "leave",
    "Fill numbers with median": "median",
    "Fill numbers with median + text with 'Unknown'": "median_unknown",
}
SEVERITY_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡"}


# --------------------------------------------------------------------------- #
# Cached helpers
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Reading file...")
def cached_read(data: bytes, filename: str, sheet):
    return read_file(data, filename, sheet)


@st.cache_data(show_spinner="Cleaning data...")
def cached_clean(raw: pd.DataFrame, header_idx: int, opts: dict):
    result = clean_data(raw, CleaningOptions(**opts), row_offset=header_idx + 2)
    return result, to_excel_bytes(result), result.df.to_csv(index=False).encode("utf-8-sig")


def default_api_key() -> str:
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "API_KEY"):
        if os.getenv(name):
            return os.getenv(name, "")
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:  # no secrets file
        return ""


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("⚙️ Cleaning rules")
    opts = {
        "standardize_columns": st.checkbox("Standardise column names", True),
        "trim_text": st.checkbox("Remove extra spaces", True),
        "nulls_to_nan": st.checkbox("Treat N/A, null, '-' as blank", True),
        "drop_empty_rows": st.checkbox("Remove empty rows", True),
        "drop_empty_cols": st.checkbox("Remove empty columns", True),
        "convert_numbers": st.checkbox("Fix numbers stored as text (₹1,200)", True),
        "convert_dates": st.checkbox("Fix dates stored as text", True),
        "dayfirst": st.checkbox("Dates are DD-MM-YYYY (day first)", True),
        "unify_text_case": st.checkbox("Unify North / north / NORTH", True),
        "drop_exact_duplicates": st.checkbox(
            "Remove exact duplicate rows", True,
            help="Only rows identical in every column. Removed rows are saved in a separate sheet."),
    }
    missing_label = st.radio("Missing values", list(MISSING_CHOICES), index=0)
    opts["missing_strategy"] = MISSING_CHOICES[missing_label]

    st.divider()
    st.header("🤖 AI settings")
    api_key = st.text_input("Gemini API key", value=default_api_key(), type="password",
                            help="Or put GEMINI_API_KEY in a .env file / environment variable.")
    model = st.text_input("Gemini model", value=DEFAULT_MODEL,
                          help="Change this if you want to use another Gemini model.")
    include_samples = st.checkbox("Send 5 sample rows to Gemini", False,
                                  help="Off = Gemini only sees column names and summary statistics "
                                       "(recommended for confidential data).")
    st.caption("Gemini never receives the full file - only the schema, summary statistics, "
               "optional sample rows and small result tables.")

# --------------------------------------------------------------------------- #
# Upload
# --------------------------------------------------------------------------- #
uploaded = st.file_uploader("Upload your Excel or CSV file", type=["xlsx", "xlsm", "csv"])
if uploaded is None:
    st.info("👆 Upload a file to start. Supported: .xlsx, .xlsm, .csv. "
            "Try `sample_data/messy_sales.xlsx` from this repo.")
    st.stop()

data = uploaded.getvalue()
try:
    sheets = list_sheets(data, uploaded.name)
    sheet = st.selectbox("Sheet", sheets) if len(sheets) > 1 else sheets[0]
    raw, header_idx = cached_read(data, uploaded.name, sheet)
except Exception as err:  # noqa: BLE001
    st.error(f"Could not read this file: {err}")
    st.stop()

if raw.empty:
    st.warning("The file/sheet has no data rows.")
    st.stop()

result, excel_bytes, csv_bytes = cached_clean(raw, header_idx, opts)
clean_df = result.df

# reset chat/report whenever the file or the cleaning rules change
data_key = hashlib.md5(data).hexdigest() + str(sheet) + str(sorted(opts.items()))
if st.session_state.get("data_key") != data_key:
    st.session_state.data_key = data_key
    st.session_state.chat = []
    st.session_state.report = None

if clean_df.empty:
    st.warning("Nothing is left after cleaning. Check your cleaning rules in the sidebar.")
    st.stop()

tab_raw, tab_clean, tab_dash, tab_report, tab_chat = st.tabs(
    ["1️⃣ Raw data", "2️⃣ Cleaned data & download", "3️⃣ Live dashboard", "4️⃣ AI report", "5️⃣ Ask your data"]
)

# --------------------------------------------------------------------------- #
# Tab 1 - raw data
# --------------------------------------------------------------------------- #
with tab_raw:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{raw.shape[0]:,}")
    c2.metric("Columns", raw.shape[1])
    c3.metric("Missing cells", f"{int(raw.isna().sum().sum()):,}")
    c4.metric("Exact duplicate rows", f"{int(raw.duplicated().sum()):,}")
    if header_idx:
        st.caption(f"Header was detected on row {header_idx + 1}; rows above it were skipped.")
    st.subheader("Preview (first 100 rows)")
    st.dataframe(raw.head(100))
    st.subheader("Column profile of the raw file")
    st.dataframe(profile_columns(raw))

# --------------------------------------------------------------------------- #
# Tab 2 - cleaned data
# --------------------------------------------------------------------------- #
with tab_clean:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{clean_df.shape[0]:,}", delta=int(clean_df.shape[0] - result.original_shape[0]))
    c2.metric("Columns", clean_df.shape[1], delta=int(clean_df.shape[1] - result.original_shape[1]))
    c3.metric("Missing cells left", f"{int(clean_df.isna().sum().sum()):,}")
    c4.metric("Items to review", f"{len(result.issues):,}")

    st.subheader("What was done automatically")
    for action in result.actions:
        st.markdown(f"- {action}")

    if len(result.issues):
        st.subheader("⚠️ Please review (NOT changed automatically)")
        issue_types = sorted(result.issues["issue"].unique())
        picked = st.multiselect("Filter by issue type", issue_types, default=issue_types)
        st.dataframe(result.issues[result.issues["issue"].isin(picked)])
    else:
        st.success("Nothing needs manual review.")

    if len(result.removed_rows):
        with st.expander(f"Removed duplicate rows ({len(result.removed_rows)})"):
            st.dataframe(result.removed_rows)

    st.subheader("Cleaned data preview")
    st.dataframe(clean_df.head(200))

    stem = Path(uploaded.name).stem
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download cleaned Excel (with log & review sheets)", data=excel_bytes,
                       file_name=f"cleaned_{stem}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    d2.download_button("⬇️ Download cleaned CSV", data=csv_bytes, file_name=f"cleaned_{stem}.csv",
                       mime="text/csv")

# --------------------------------------------------------------------------- #
# Tab 3 - live dashboard (computed with pandas, no AI needed)
# --------------------------------------------------------------------------- #
with tab_dash:
    num_cols = numeric_measure_columns(clean_df) or [
        c for c in clean_df.columns
        if ptypes.is_numeric_dtype(clean_df[c]) and not ptypes.is_bool_dtype(clean_df[c])]
    date_cols = [c for c in clean_df.columns if ptypes.is_datetime64_any_dtype(clean_df[c])]
    cat_cols = [c for c in clean_df.columns
                if (clean_df[c].dtype == object or ptypes.is_string_dtype(clean_df[c]))
                and 1 < clean_df[c].nunique() <= 200]

    if not num_cols:
        st.info("No numeric columns found, so there are no KPIs to chart. "
                "You can still use the 'Ask your data' tab.")
    else:
        def pick(cols, pattern):
            for col in cols:
                if re.search(pattern, col.lower()):
                    return col
            return cols[0]

        s1, s2, s3, s4 = st.columns(4)
        measure = s1.selectbox("Measure (number to analyse)", num_cols,
                               index=num_cols.index(pick(num_cols, r"sale|revenue|amount|profit|price|total")))
        agg_label = s2.selectbox("Calculation", ["Sum", "Average", "Median", "Count"])
        agg = {"Sum": "sum", "Average": "mean", "Median": "median", "Count": "count"}[agg_label]
        dim = s3.selectbox("Group by", cat_cols) if cat_cols else None
        top_n = s4.slider("Top N groups", 3, 30, 10)

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Rows", f"{len(clean_df):,}")
        k2.metric(f"Total {measure}", f"{clean_df[measure].sum():,.2f}")
        k3.metric("Average", f"{clean_df[measure].mean():,.2f}")
        k4.metric("Median", f"{clean_df[measure].median():,.2f}")
        k5.metric("Max", f"{clean_df[measure].max():,.2f}")

        left, right = st.columns(2)
        if dim:
            grp = (clean_df.groupby(dim, dropna=False)[measure].agg(agg)
                   .sort_values(ascending=False).head(top_n).reset_index())
            left.plotly_chart(px.bar(grp, x=dim, y=measure, title=f"{agg_label} of {measure} by {dim}"))
        right.plotly_chart(px.histogram(clean_df, x=measure, title=f"Distribution of {measure}"))

        if date_cols:
            t1, t2 = st.columns(2)
            date_col = t1.selectbox("Date column", date_cols)
            freq_label = t2.selectbox("Trend by", ["Day", "Week", "Month", "Quarter", "Year"], index=2)
            rule = {"Day": "D", "Week": "W", "Month": "MS", "Quarter": "QS", "Year": "YS"}[freq_label]
            ts = (clean_df.dropna(subset=[date_col]).set_index(date_col)[measure]
                  .resample(rule).agg(agg).reset_index())
            st.plotly_chart(px.line(ts, x=date_col, y=measure, markers=True,
                                    title=f"{agg_label} of {measure} per {freq_label.lower()}"))

        if len(num_cols) >= 2:
            corr = clean_df[num_cols[:12]].corr()
            st.plotly_chart(px.imshow(corr, text_auto=".2f", aspect="auto",
                                      title="Correlation between numeric columns"))

        st.subheader("Summary statistics")
        st.dataframe(clean_df[num_cols].describe().T)

# --------------------------------------------------------------------------- #
# Tab 4 - AI report (validated JSON -> rendered sections)
# --------------------------------------------------------------------------- #
with tab_report:
    if not api_key:
        st.warning("Add your Gemini API key in the sidebar (or in a .env file) to generate the AI report.")
    else:
        st.caption("The report is returned as structured JSON, validated against a schema, and every "
                   "number is cross-checked against statistics computed by code.")
        if st.button("✨ Generate AI business report"):
            with st.spinner("Gemini is analysing the data..."):
                try:
                    st.session_state.report = generate_structured_report(
                        get_client(api_key), model, clean_df, result.actions,
                        len(result.issues), include_samples)
                except ReportError as err:
                    st.session_state.report = None
                    st.error(f"The model did not return a valid report: {err}")
                except Exception as err:  # noqa: BLE001
                    st.session_state.report = None
                    st.error(f"Gemini request failed: {err}")

        res = st.session_state.get("report")
        if res:
            rep = res.report
            st.header(rep.headline)
            if res.warnings:
                with st.expander(f"⚠️ {len(res.warnings)} statement(s) contain numbers that could not be "
                                 "verified - please double-check", expanded=True):
                    for w in res.warnings:
                        st.markdown(f"- {w}")
            else:
                st.success("✅ Every number in this report was found in the computed statistics.")

            st.subheader("Executive summary")
            for point in rep.executive_summary:
                st.markdown(f"- {point}")

            st.subheader("Key metrics")
            cols = st.columns(min(4, len(rep.key_metrics)))
            for i, m in enumerate(rep.key_metrics):
                cols[i % len(cols)].metric(m.name, m.value, help=m.context)

            st.subheader("Insights")
            for ins in rep.insights:
                with st.container(border=True):
                    st.markdown(f"**{ins.title}**")
                    st.write(ins.detail)
                    st.caption(f"Evidence: {ins.evidence}")

            st.subheader("Risks & data-quality warnings")
            if rep.risks:
                for r in rep.risks:
                    st.markdown(f"{SEVERITY_ICON[r.severity]} **{r.title}** ({r.severity}) - {r.detail}")
            else:
                st.write("No risks identified.")

            st.subheader("Recommended actions")
            for i, a in enumerate(rep.recommended_actions, 1):
                st.markdown(f"{i}. {a}")

            stem = Path(uploaded.name).stem
            b1, b2 = st.columns(2)
            b1.download_button("⬇️ Download report (.md)",
                               report_to_markdown(rep, res.warnings).encode("utf-8"),
                               file_name=f"report_{stem}.md", mime="text/markdown")
            b2.download_button("⬇️ Download report (.json)",
                               json.dumps({"report": rep.model_dump(), "unverified": res.warnings},
                                          indent=2).encode("utf-8"),
                               file_name=f"report_{stem}.json", mime="application/json")

# --------------------------------------------------------------------------- #
# Tab 5 - ask your data
# --------------------------------------------------------------------------- #
with tab_chat:
    st.write("Ask anything about your sheet, e.g. *Top 5 products by sales*, "
             "*month-wise revenue trend*, *which region has the most negative profit?*")
    if not api_key:
        st.warning("Add your Gemini API key in the sidebar (or in a .env file) to use this feature.")
    else:
        mode = st.radio("Answer mode", ["Safe analytics tools (recommended)", "Free-form pandas code (advanced)"],
                        horizontal=True,
                        help="Tools: Gemini can only call fixed, read-only functions. "
                             "Code: Gemini writes pandas code which is checked before it runs.")
        use_tools = mode.startswith("Safe")

        for i, msg in enumerate(st.session_state.chat):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("grounded") is False:
                    st.warning("No tool was used, so these numbers are NOT verified by calculation.")
                if msg.get("table") is not None:
                    st.dataframe(msg["table"])
                if msg.get("fig") is not None:
                    st.plotly_chart(msg["fig"], key=f"chat_fig_{i}")
                if msg.get("details"):
                    with st.expander("How was this calculated?"):
                        st.code(msg["details"], language="python")

        question = st.chat_input("Ask a question about your Excel data...")
        if question:
            history = [m["content"] for m in st.session_state.chat if m["role"] == "user"]
            st.session_state.chat.append({"role": "user", "content": question})
            try:
                client = get_client(api_key)
                with st.spinner("Analysing..."):
                    if use_tools:
                        out = ask_with_tools(client, model, clean_df, question, history, include_samples)
                        st.session_state.chat.append({
                            "role": "assistant", "content": out["answer"], "table": out["table"],
                            "fig": chart_from_state(out["table"], out["chart"]),
                            "grounded": out["grounded"],
                            "details": "\n".join(format_tool_call(c) for c in out["tool_calls"])})
                    else:
                        out = ask_data_question(client, model, clean_df, question, history, include_samples)
                        st.session_state.chat.append({
                            "role": "assistant", "content": out["answer"], "table": out["table"],
                            "fig": out["fig"], "details": out["code"]})
            except Exception as err:  # noqa: BLE001
                st.session_state.chat.append({"role": "assistant", "content": f"Gemini request failed: {err}"})
            st.rerun()
