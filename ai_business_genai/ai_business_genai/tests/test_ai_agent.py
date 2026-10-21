"""AI-layer tests use a fake Gemini client, so they run offline and need no API key."""
import json
from types import SimpleNamespace

import pytest

import ai_agent
from ai_agent import (ReportError, ask_with_tools, build_context, generate_structured_report,
                      run_analysis_code, validate_code)


class FakeModels:
    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def generate_content(self, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.handler(self, model, contents, config)


class FakeClient:
    def __init__(self, handler):
        self.models = FakeModels(handler)


def _resp(text):
    return SimpleNamespace(text=text)


GOOD_REPORT = {
    "headline": "South leads sales",
    "executive_summary": ["South has the highest sales.", "North and East are smaller."],
    "key_metrics": [{"name": "Total sales", "value": "1,200.00", "context": "all orders"}],
    "insights": [{"title": "South is strongest", "detail": "South sold 700.00.", "evidence": "sales by region"}],
    "risks": [],
    "recommended_actions": ["Grow North and East."],
}


# ------------------------------------------------------------ context -------- #
def test_context_contains_real_totals_and_breakdowns(sales_df):
    ctx = build_context(sales_df, include_samples=False)
    assert "1200.0" in ctx                      # column total, computed from the full data
    assert "sum of sales by region" in ctx and "South=700.00" in ctx
    assert "SAMPLE ROWS" not in ctx
    assert "SAMPLE ROWS" in build_context(sales_df, include_samples=True)


def test_context_excludes_id_columns_from_numeric_summary(sales_df):
    sales_df["customer_id"] = range(len(sales_df))
    ctx = build_context(sales_df, include_samples=False)
    summary = ctx.split("NUMERIC SUMMARY")[1].split("BREAKDOWNS")[0]
    assert "customer_id" not in summary


# ------------------------------------------------- structured report -------- #
def test_structured_report_happy_path(sales_df):
    client = FakeClient(lambda *_: _resp(json.dumps(GOOD_REPORT)))
    res = generate_structured_report(client, "m", sales_df, ["cleaned"], 0, include_samples=False)
    assert res.report.headline == "South leads sales"
    assert res.attempts == 1 and res.warnings == []
    cfg = client.models.calls[0]["config"]
    assert cfg.response_mime_type == "application/json"


def test_structured_report_retries_once_after_invalid_json(sales_df):
    answers = iter([_resp('{"headline": "x"}'), _resp(json.dumps(GOOD_REPORT))])
    client = FakeClient(lambda *_: next(answers))
    res = generate_structured_report(client, "m", sales_df, [], 0, include_samples=False)
    assert res.attempts == 2
    assert "rejected" in client.models.calls[1]["contents"]


def test_structured_report_gives_up_after_two_failures(sales_df):
    client = FakeClient(lambda *_: _resp("not json at all"))
    with pytest.raises(ReportError):
        generate_structured_report(client, "m", sales_df, [], 0, include_samples=False)
    assert len(client.models.calls) == 2


def test_structured_report_flags_invented_numbers(sales_df):
    bad = dict(GOOD_REPORT, key_metrics=[{"name": "Total sales", "value": "5,555,555.00", "context": "?"}])
    client = FakeClient(lambda *_: _resp(json.dumps(bad)))
    res = generate_structured_report(client, "m", sales_df, [], 0, include_samples=False)
    assert any("5,555,555" in w for w in res.warnings)


def test_report_schema_is_accepted_by_gemini_sdk():
    """The pydantic model must convert to a Gemini schema without errors."""
    from google import genai
    from google.genai import _transformers as t
    from schemas import BusinessReport
    client = genai.Client(api_key="dummy")
    schema = t.t_schema(client._api_client, BusinessReport)
    assert schema is not None


# --------------------------------------------------- tool calling ---------- #
def test_ask_with_tools_runs_tools_and_reports_grounding(sales_df):
    def handler(models, model, contents, config):
        by_name = {f.__name__: f for f in config.tools}
        out = by_name["aggregate"](value_column="sales", how="sum", group_by="region", top_n=2)
        assert out["rows"][0]["region"] == "South"
        return _resp("South has the highest sales (700.00).")

    client = FakeClient(handler)
    out = ask_with_tools(client, "m", sales_df, "top region by sales?")
    assert out["grounded"] is True
    assert out["tool_calls"][0]["tool"] == "aggregate"
    assert out["table"] is not None and out["chart"]["kind"] == "bar"
    assert ai_agent.chart_from_state(out["table"], out["chart"]) is not None
    assert "aggregate(" in ai_agent.format_tool_call(out["tool_calls"][0])


def test_ask_with_tools_marks_answers_without_tool_use_as_ungrounded(sales_df):
    client = FakeClient(lambda *_: _resp("It is probably South."))
    out = ask_with_tools(client, "m", sales_df, "top region?")
    assert out["grounded"] is False and out["table"] is None


def test_ask_with_tools_configures_function_calling_limits(sales_df):
    client = FakeClient(lambda *_: _resp("ok"))
    ask_with_tools(client, "m", sales_df, "q")
    cfg = client.models.calls[0]["config"]
    assert len(cfg.tools) == 7
    assert cfg.automatic_function_calling.maximum_remote_calls == 8


# ------------------------------------------- code-mode safety validator ----- #
@pytest.mark.parametrize("code", [
    "import os",
    "from os import system",
    "result = open('x')",
    "result = df.to_csv('a.csv')",
    "result = df.__class__",
    "result = ().__class__.__bases__",
    "result = getattr(df, 'a')",
    "result = eval('1+1')",
])
def test_validator_blocks_dangerous_code(code, sales_df):
    with pytest.raises(ValueError):
        run_analysis_code(code, sales_df)


def test_validator_allows_normal_pandas(sales_df):
    code = "result = df.groupby('region')['sales'].sum()\nfig = px.bar(result.reset_index(), x='region', y='sales')"
    result, fig = run_analysis_code(code, sales_df)
    assert result["South"] == 700.0 and fig is not None
    validate_code(code)


def test_code_must_define_result(sales_df):
    with pytest.raises(ValueError):
        run_analysis_code("x = 1", sales_df)
