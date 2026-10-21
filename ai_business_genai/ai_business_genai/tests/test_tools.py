import pytest

from analytics_tools import ToolState, make_tools


@pytest.fixture()
def tools(sales_df):
    state = ToolState()
    fns = {f.__name__: f for f in make_tools(sales_df, state)}
    return fns, state


def test_aggregate_total(tools):
    fns, _ = tools
    assert fns["aggregate"]("sales", "sum")["result"] == 1200.0


def test_aggregate_group_sorted_desc(tools):
    fns, state = tools
    out = fns["aggregate"]("sales", "sum", group_by="region")
    assert out["rows"][0] == {"region": "South", "sum_sales": 700.0}
    assert state.chart["kind"] == "bar"
    assert state.table is not None


def test_aggregate_top_n_and_ascending(tools):
    fns, _ = tools
    out = fns["aggregate"]("sales", "sum", group_by="region", top_n=1, ascending=True)
    assert out["rows"] == [{"region": "East", "sum_sales": 200.0}]


def test_filter_text_case_insensitive(tools):
    fns, _ = tools
    assert fns["aggregate"]("sales", "sum", filter_column="region", filter_value="north")["result"] == 300.0


def test_filter_numeric_and_date(tools):
    fns, _ = tools
    assert fns["aggregate"]("sales", "count", filter_column="sales", filter_op=">", filter_value="150")["result"] == 3
    out = fns["aggregate"]("sales", "sum", filter_column="order_date", filter_op=">=", filter_value="2025-03-01")
    assert out["result"] == 600.0


def test_column_name_is_resolved_leniently(tools):
    fns, _ = tools
    assert fns["aggregate"]("Sales", "sum")["result"] == 1200.0


def test_unknown_column_returns_error_with_hints(tools):
    fns, state = tools
    out = fns["aggregate"]("revenue", "sum")
    assert "error" in out and "sales" in out["available_columns"]
    assert state.calls[-1]["ok"] is False


def test_bad_aggregation_and_non_numeric_value(tools):
    fns, _ = tools
    assert "error" in fns["aggregate"]("sales", "bogus")
    assert "error" in fns["aggregate"]("region", "sum")


def test_no_rows_after_filter(tools):
    fns, _ = tools
    out = fns["aggregate"]("sales", "sum", filter_column="region", filter_value="Mars")
    assert out["rows_used"] == 0


def test_time_trend_monthly(tools):
    fns, state = tools
    out = fns["time_trend"]("order_date", "sales", "sum", "M")
    assert [r["sum_sales"] for r in out["rows"]] == [300.0, 300.0, 600.0]
    assert state.chart["kind"] == "line"


def test_time_trend_rejects_non_date(tools):
    fns, _ = tools
    assert "error" in fns["time_trend"]("region", "sales")


def test_correlation_and_value_counts_and_top_rows(tools):
    fns, _ = tools
    assert fns["correlation"]("sales", "profit")["correlation"] > 0.5
    assert fns["value_counts"]("category")["rows"][0] == {"category": "Tech", "count": 4}
    top = fns["top_rows"]("profit", n=1, ascending=True)
    assert top["rows"][0]["profit"] == -20.0


def test_describe_and_summarize(tools):
    fns, _ = tools
    info = fns["describe_dataset"]()
    assert "sales" in info["measure_columns"] and "order_id" not in info["measure_columns"]
    assert fns["summarize_column"]("sales")["sum"] == 1200.0
    assert fns["summarize_column"]("order_date")["earliest"] == "2025-01-05"


def test_tool_results_are_json_serialisable(tools):
    import json
    fns, _ = tools
    json.dumps(fns["aggregate"]("sales", "mean", group_by="region"))
    json.dumps(fns["time_trend"]("order_date", "sales"))
    json.dumps(fns["describe_dataset"]())
