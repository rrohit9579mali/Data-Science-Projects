"""
ai_agent.py
===========
Gemini layer on top of the cleaned data. Three features:

1. generate_structured_report()  - report as validated JSON (Pydantic) + grounding check
2. ask_with_tools()              - question answering through SAFE function calling
                                   (Gemini picks tools from analytics_tools.py)
3. ask_data_question()           - "advanced mode": Gemini writes pandas code which is
                                   AST-validated before it is executed

PRIVACY: Gemini receives column names, summary statistics, optional 5 sample rows and small
result tables - never the full file.
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pandas.api import types as ptypes
from pydantic import ValidationError

from analytics_tools import ToolState, make_tools
from cleaner import is_code_like, numeric_measure_columns
from schemas import BusinessReport, check_grounding

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MEASURE_HINT = ("sale", "revenue", "profit", "amount", "total", "income", "cost", "price", "salary")


# --------------------------------------------------------------------------- #
# Gemini client
# --------------------------------------------------------------------------- #
def get_client(api_key: str):
    from google import genai  # pip install google-genai
    return genai.Client(api_key=api_key)


def ask_gemini(client, model: str, prompt: str, temperature: float = 0.2) -> str:
    response = client.models.generate_content(
        model=model, contents=prompt, config={"temperature": temperature}
    )
    return response.text or ""


# --------------------------------------------------------------------------- #
# Dataset context (everything Gemini is allowed to see)
# --------------------------------------------------------------------------- #
def _is_text(s: pd.Series) -> bool:
    return s.dtype == object or ptypes.is_string_dtype(s)


def _rank_measures(measures: list[str]) -> list[str]:
    return sorted(measures, key=lambda c: (not any(h in c.lower() for h in MEASURE_HINT), measures.index(c)))


def _breakdowns(df: pd.DataFrame, max_cats: int = 3, max_measures: int = 2, top: int = 6) -> list[str]:
    """Pre-computed group sums, so the report can talk about real regions/categories."""
    measures = _rank_measures(numeric_measure_columns(df))[:max_measures]
    cats = [c for c in df.columns
            if _is_text(df[c]) and 2 <= df[c].nunique() <= 30 and not is_code_like(c)][:max_cats]
    lines = []
    for m in measures:
        for c in cats:
            g = df.groupby(c)[m].sum().sort_values(ascending=False)
            best = ", ".join(f"{k}={v:,.2f}" for k, v in g.head(top).items())
            line = f"- sum of {m} by {c}: {best}"
            if len(g) > top:
                line += " | lowest: " + ", ".join(f"{k}={v:,.2f}" for k, v in g.tail(2).items())
            lines.append(line)
    date_cols = [c for c in df.columns if ptypes.is_datetime64_any_dtype(df[c]) and df[c].notna().any()]
    if date_cols and measures:
        d, m = date_cols[0], measures[0]
        span_days = (df[d].max() - df[d].min()).days
        rule, fmt = ("YS", "%Y") if span_days >= 730 else ("MS", "%Y-%m")
        series = df.dropna(subset=[d]).set_index(d)[m].resample(rule).sum()
        lines.append(f"- sum of {m} per {'year' if rule == 'YS' else 'month'} ({d}): " +
                     ", ".join(f"{k.strftime(fmt)}={v:,.2f}" for k, v in series.tail(12).items()))
    return lines


def build_context(df: pd.DataFrame, include_samples: bool = True, max_cols: int = 80) -> str:
    df = df.iloc[:, :max_cols]
    lines = [f"Rows: {len(df)} | Columns: {df.shape[1]}", "", "COLUMNS (name | type | missing | unique):"]
    for c in df.columns:
        s = df[c]
        kind = ("date" if ptypes.is_datetime64_any_dtype(s)
                else "number" if ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s)
                else "text")
        lines.append(f"- {c} | {kind} | {int(s.isna().sum())} | {int(s.nunique(dropna=True))}")

    measures = numeric_measure_columns(df)
    if measures:
        desc = df[measures].agg(["count", "sum", "mean", "median", "min", "max"]).T.round(2)
        lines += ["", "NUMERIC SUMMARY (count, sum, mean, median, min, max):", desc.to_string()]

    breakdowns = _breakdowns(df)
    if breakdowns:
        lines += ["", "BREAKDOWNS (computed from the full data):"] + breakdowns

    cat_lines = []
    for c in df.columns:
        s = df[c]
        if _is_text(s) and 1 < s.nunique() <= 30 and not is_code_like(c):
            top = s.value_counts().head(8)
            cat_lines.append(f"- {c}: " + ", ".join(f"{k} ({v})" for k, v in top.items()))
    if cat_lines:
        lines += ["", "ROW COUNTS PER CATEGORY:"] + cat_lines

    date_lines = [f"- {c}: {df[c].min():%d-%m-%Y} to {df[c].max():%d-%m-%Y}" for c in df.columns
                  if ptypes.is_datetime64_any_dtype(df[c]) and df[c].notna().any()]
    if date_lines:
        lines += ["", "DATE RANGES:"] + date_lines

    if include_samples:
        lines += ["", "SAMPLE ROWS:", df.head(5).to_string()[:3000]]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 1. Structured business report
# --------------------------------------------------------------------------- #
class ReportError(RuntimeError):
    """Gemini did not return a valid report, even after a retry."""


@dataclass
class ReportResult:
    report: BusinessReport
    warnings: list = field(default_factory=list)   # numbers that could not be verified
    attempts: int = 1


def _report_prompt(context: str, actions: list[str], n_review: int) -> str:
    log = "\n".join(f"- {a}" for a in actions)
    return f"""You are a senior business data analyst writing for non-technical managers.

DATASET STATISTICS (computed by code from the cleaned file - this is your ONLY source of numbers)
{context}

DATA-CLEANING LOG
{log}
Items still flagged for human review: {n_review}

Return the report as JSON that follows the given schema.
Hard rules:
- Use only numbers that appear in the statistics above. Copy them exactly, with the same digits.
  Never abbreviate (write 2,297,200.86, not 2.3M). Never invent columns or values.
- If something cannot be concluded from the statistics, say so instead of guessing.
- Mention data-quality issues (review flags, missing values) in `risks`.
- Simple language, short sentences, no jargon."""


def generate_structured_report(client, model: str, df: pd.DataFrame, actions: list[str],
                               n_review: int, include_samples: bool = True,
                               max_attempts: int = 2) -> ReportResult:
    from google.genai import types

    context = build_context(df, include_samples)
    base_prompt = _report_prompt(context, actions, n_review)
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        prompt = base_prompt if not last_error else (
            base_prompt + f"\n\nYour previous answer was rejected: {last_error}\nReturn corrected JSON only.")
        response = client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BusinessReport,
                temperature=0.2,
            ),
        )
        try:
            report = BusinessReport.model_validate_json((response.text or "").strip())
        except ValidationError as err:
            last_error = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in err.errors()[:5])
            continue
        return ReportResult(report=report, warnings=check_grounding(report, context), attempts=attempt)
    raise ReportError(f"Gemini returned an invalid report after {max_attempts} attempts: {last_error}")


# --------------------------------------------------------------------------- #
# 2. Question answering with safe tool calling
# --------------------------------------------------------------------------- #
TOOL_SYSTEM_PROMPT = """You are a careful business data analyst. The user's cleaned table is available
ONLY through the provided tools.
- ALWAYS call tools to obtain numbers. Never compute or recall numbers yourself.
- If you are unsure about column names, call describe_dataset first.
- If a tool returns an error, read it, fix the arguments and try again.
- Answer in 2-6 short sentences, in the SAME language/style as the question (Hinglish -> Hinglish).
- Say which column(s) you used. If the data cannot answer the question, say so plainly."""


def ask_with_tools(client, model: str, df: pd.DataFrame, question: str,
                   history: list[str] | None = None, include_samples: bool = False) -> dict:
    """Returns dict(answer, table, chart, tool_calls, grounded, error)."""
    from google.genai import types

    state = ToolState()
    tools = make_tools(df, state)
    context = build_context(df, include_samples)
    prev = "\n".join(f"- {q}" for q in (history or [])[-3:]) or "- (none)"
    prompt = (f"DATASET OVERVIEW\n{context}\n\nPREVIOUS QUESTIONS\n{prev}\n\nQUESTION\n{question}")
    config = types.GenerateContentConfig(
        system_instruction=TOOL_SYSTEM_PROMPT,
        tools=tools,
        temperature=0.1,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=8),
    )
    response = client.models.generate_content(model=model, contents=prompt, config=config)
    answer = (response.text or "").strip() or "I could not produce an answer. Please rephrase the question."
    used_tools = any(c["ok"] for c in state.calls)
    return {"answer": answer, "table": state.table, "chart": state.chart,
            "tool_calls": state.calls, "grounded": used_tools, "error": ""}


def chart_from_state(table: pd.DataFrame | None, chart: dict | None):
    """Build a Plotly figure for the last tool result (bar or line)."""
    if table is None or chart is None or table.empty:
        return None
    if chart["kind"] == "line":
        return px.line(table, x=chart["x"], y=chart["y"], markers=True)
    return px.bar(table, x=chart["x"], y=chart["y"])


def format_tool_call(call: dict) -> str:
    args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
    return f"{'OK ' if call['ok'] else 'ERR'} {call['tool']}({args})"


# --------------------------------------------------------------------------- #
# 3. Advanced mode: AI-written pandas code, validated before execution
# --------------------------------------------------------------------------- #
FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "input", "breakpoint", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "__import__", "help", "dir", "memoryview", "exit", "quit",
}
FORBIDDEN_ATTRS = {
    "to_csv", "to_excel", "to_pickle", "to_sql", "to_json", "to_parquet", "to_feather",
    "to_hdf", "to_clipboard", "to_xml", "to_html", "to_latex", "read_csv", "read_excel",
    "read_pickle", "read_sql", "read_json", "read_parquet", "read_html", "read_clipboard",
    "eval", "system", "popen", "write_html", "write_image", "write_json",
}
SAFE_BUILTINS = {
    name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    for name in ("len", "range", "min", "max", "sum", "abs", "round", "sorted", "enumerate",
                 "zip", "list", "dict", "set", "tuple", "str", "int", "float", "bool", "any",
                 "all", "map", "filter", "reversed", "isinstance", "slice", "pow", "divmod")
}


def validate_code(code: str) -> None:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Imports are not allowed")
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id.startswith("__")):
            raise ValueError(f"Use of '{node.id}' is not allowed")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr in FORBIDDEN_ATTRS):
            raise ValueError(f"Use of '.{node.attr}' is not allowed")


def extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    return (match.group(1) if match else text).strip()


def run_analysis_code(code: str, df: pd.DataFrame):
    validate_code(code)
    env = {"__builtins__": SAFE_BUILTINS, "pd": pd, "np": np, "px": px, "df": df.copy()}
    exec(compile(code, "<analysis>", "exec"), env)  # noqa: S102 - validated above
    if "result" not in env:
        raise ValueError("The code did not create a variable named `result`")
    fig = env.get("fig")
    return env["result"], fig if isinstance(fig, go.Figure) else None


def result_to_text(result, limit: int = 30) -> str:
    if isinstance(result, pd.DataFrame):
        text = f"DataFrame shape={result.shape}\n{result.head(limit).to_string()}"
    elif isinstance(result, pd.Series):
        text = f"Series name={result.name}, length={len(result)}\n{result.head(limit).to_string()}"
    else:
        text = str(result)
    return text[:4000]


def result_to_table(result):
    if isinstance(result, pd.DataFrame):
        return result.head(200)
    if isinstance(result, pd.Series):
        return result.head(200).to_frame().reset_index()
    return None


def _code_prompt(question: str, context: str, history: list[str]) -> str:
    prev = "\n".join(f"- {q}" for q in history[-3:]) or "- (none)"
    return f"""You are a senior data analyst. A cleaned pandas DataFrame named `df` is already loaded.
Already available as variables: pd (pandas), np (numpy), px (plotly.express). Do NOT import anything.

DATASET CONTEXT
{context}

PREVIOUS QUESTIONS (for follow-ups)
{prev}

Write Python code that answers the NEW question.
- Use the exact column names listed above.
- Put the final answer in a variable called `result` (number, string, Series or DataFrame).
  Keep tables small (top 20 rows unless asked otherwise).
- If a chart helps, put a plotly express figure in a variable called `fig`.
- Never modify `df` in place, no file/network/system access, no imports, no print().
- Date columns are datetime64: use the .dt accessor.
- Return ONLY one ```python code block, no explanation.

NEW QUESTION
{question}
"""


def ask_data_question(client, model: str, df: pd.DataFrame, question: str,
                      history: list[str] | None = None, include_samples: bool = True) -> dict:
    """Returns dict(answer, code, table, fig, error)."""
    history = history or []
    context = build_context(df, include_samples)
    code = extract_code(ask_gemini(client, model, _code_prompt(question, context, history), 0.1))

    result = fig = None
    last_error = ""
    for attempt in range(2):  # one automatic self-repair attempt
        try:
            result, fig = run_analysis_code(code, df)
            last_error = ""
            break
        except Exception as err:  # noqa: BLE001
            last_error = f"{type(err).__name__}: {err}"
            if attempt == 1:
                break
            fix_prompt = (_code_prompt(question, context, history)
                          + f"\n\nYour previous code failed.\nCODE:\n```python\n{code}\n```\n"
                            f"ERROR: {last_error}\nReturn the corrected code only.")
            code = extract_code(ask_gemini(client, model, fix_prompt, 0.1))

    if last_error:
        return {"answer": "Sorry, I could not calculate this reliably. Try rephrasing the question "
                          "(mention the column names).",
                "code": code, "table": None, "fig": None, "error": last_error}

    explain_prompt = f"""A manager asked a question about their data. The result was calculated with code.

QUESTION: {question}

CODE USED:
{code}

RESULT:
{result_to_text(result)}

Answer in 2-5 short sentences, in simple business language, in the SAME language/style as the
question (if it is Hinglish, answer in Hinglish). Use only numbers from RESULT. Mention any
assumption you made (e.g. which column you used) in one short sentence."""
    answer = ask_gemini(client, model, explain_prompt, 0.2)
    return {"answer": answer, "code": code, "table": result_to_table(result), "fig": fig, "error": ""}
