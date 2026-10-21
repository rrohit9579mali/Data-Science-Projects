"""
analytics_tools.py
==================
Safe, read-only analytics tools that Gemini can call (function calling / tool calling).

The model never gets to run arbitrary code here. It can only choose one of these
functions and fill in their arguments; every function validates its inputs against the
real DataFrame and returns either a small JSON-friendly result or an {"error": ...}
dict that lets the model correct itself.

`make_tools(df, state)` returns plain Python functions (type hints + docstrings are what
the Gemini SDK turns into tool declarations). `state` records the tool calls and the last
result table so the UI can show "how this was calculated" and draw a chart.
"""
from __future__ import annotations

import operator
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from cleaner import numeric_measure_columns

MAX_ROWS = 50
AGGS = ("sum", "mean", "median", "count", "min", "max", "nunique")
FREQ = {"D": "D", "W": "W", "M": "MS", "Q": "QS", "Y": "YS"}
CMP = {"==": operator.eq, "!=": operator.ne, ">": operator.gt, "<": operator.lt,
       ">=": operator.ge, "<=": operator.le}


@dataclass
class ToolState:
    calls: list = field(default_factory=list)   # [{"tool":..., "args":..., "ok":...}]
    table: pd.DataFrame | None = None            # last tabular result
    chart: dict | None = None                    # {"kind": "bar"|"line", "x":..., "y":...}


def to_jsonable(obj):
    """Convert numpy / pandas values to plain Python so the SDK can serialise them."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (pd.Timestamp,)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if pd.isna(obj) else round(float(obj), 4)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if obj is pd.NaT:
        return None
    return obj


def _kind(s: pd.Series) -> str:
    if ptypes.is_datetime64_any_dtype(s):
        return "date"
    if ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s):
        return "number"
    return "text"


def make_tools(df: pd.DataFrame, state: ToolState) -> list:
    columns = list(df.columns)
    lookup = {str(c).lower(): c for c in columns}

    def resolve(name):
        if name in df.columns:
            return name
        key = str(name).strip().lower()
        return lookup.get(key) or lookup.get(key.replace(" ", "_"))

    def fail(message: str) -> dict:
        return {"error": message, "available_columns": columns}

    def log(tool: str, args: dict, ok: bool):
        state.calls.append({"tool": tool, "ok": ok,
                            "args": {k: v for k, v in args.items() if v not in ("", None)}})

    def apply_filter(frame, filter_column, filter_op, filter_value):
        """Returns (filtered_frame, error_message)."""
        if not filter_column:
            return frame, None
        col = resolve(filter_column)
        if col is None:
            return None, f"Unknown filter column '{filter_column}'"
        op = (filter_op or "==").strip().lower()
        s = frame[col]
        kind = _kind(s)
        try:
            if kind == "number":
                value = float(str(filter_value).replace(",", ""))
                if op not in CMP:
                    return None, f"Operator '{op}' not supported for numbers. Use one of {list(CMP)}"
                mask = CMP[op](s, value)
            elif kind == "date":
                value = pd.to_datetime(filter_value)
                if op not in CMP:
                    return None, f"Operator '{op}' not supported for dates. Use one of {list(CMP)}"
                mask = CMP[op](s, value)
            else:
                text = str(filter_value).strip().lower()
                low = s.astype("string").str.lower()
                if op == "==":
                    mask = low == text
                elif op == "!=":
                    mask = low != text
                elif op == "contains":
                    mask = low.str.contains(text, regex=False, na=False)
                else:
                    return None, f"Operator '{op}' not supported for text. Use ==, != or contains"
        except (ValueError, TypeError) as err:
            return None, f"Could not compare column '{col}' with value '{filter_value}': {err}"
        return frame[mask.fillna(False)], None

    # ------------------------------------------------------------------ tools #
    def describe_dataset() -> dict:
        """List every column with its type, number of missing values and a few example values.
        Call this first when you are unsure which column to use."""
        args: dict = {}
        info = []
        for c in columns:
            s = df[c]
            info.append({"column": c, "type": _kind(s), "missing": int(s.isna().sum()),
                         "unique": int(s.nunique(dropna=True)),
                         "examples": [str(v) for v in s.dropna().unique()[:3]]})
        log("describe_dataset", args, True)
        return to_jsonable({"rows": len(df), "columns": info,
                            "measure_columns": numeric_measure_columns(df)})

    def summarize_column(column: str) -> dict:
        """Statistics for ONE column: numbers -> count/sum/mean/median/min/max, text -> most
        frequent values, dates -> earliest and latest date.

        Args:
            column: exact column name.
        """
        args = {"column": column}
        col = resolve(column)
        if col is None:
            log("summarize_column", args, False)
            return fail(f"Unknown column '{column}'")
        s, kind = df[col], _kind(df[col])
        out: dict = {"column": col, "type": kind, "missing": int(s.isna().sum())}
        if kind == "number":
            out.update({k: s.agg(k) for k in ("count", "sum", "mean", "median", "min", "max")})
        elif kind == "date":
            out.update({"earliest": s.min(), "latest": s.max()})
        else:
            out["top_values"] = s.value_counts().head(10).to_dict()
        log("summarize_column", args, True)
        return to_jsonable(out)

    def aggregate(value_column: str, how: str = "sum", group_by: str = "", top_n: int = 10,
                  ascending: bool = False, filter_column: str = "", filter_op: str = "==",
                  filter_value: str = "") -> dict:
        """Aggregate a column, optionally per group and/or after filtering rows.
        Use this for totals, averages, counts, "top N products by sales", "sales by region" ...

        Args:
            value_column: column to aggregate (numeric, except when how='count' or 'nunique').
            how: one of sum, mean, median, count, min, max, nunique.
            group_by: optional column to group by (e.g. region, category). Empty = one overall number.
            top_n: how many groups to return (max 50).
            ascending: False = largest first, True = smallest first.
            filter_column: optional column to filter rows on before aggregating.
            filter_op: ==, !=, >, <, >=, <= (numbers/dates) or ==, !=, contains (text).
            filter_value: value to compare with (dates as YYYY-MM-DD).
        """
        args = dict(value_column=value_column, how=how, group_by=group_by, top_n=top_n,
                    ascending=ascending, filter_column=filter_column, filter_op=filter_op,
                    filter_value=filter_value)
        try:
            how_l = str(how).strip().lower()
            if how_l not in AGGS:
                raise ValueError(f"how must be one of {AGGS}")
            vcol = resolve(value_column)
            if vcol is None:
                raise ValueError(f"Unknown value_column '{value_column}'")
            if how_l not in ("count", "nunique") and _kind(df[vcol]) != "number":
                raise ValueError(f"'{vcol}' is not numeric; use how='count' or 'nunique' for it")
            frame, err = apply_filter(df, filter_column, filter_op, filter_value)
            if err:
                raise ValueError(err)
            if frame.empty:
                log("aggregate", args, True)
                return {"result": None, "note": "No rows match the filter", "rows_used": 0}
            label = f"{how_l}_{vcol}"
            if group_by:
                gcol = resolve(group_by)
                if gcol is None:
                    raise ValueError(f"Unknown group_by '{group_by}'")
                grouped = frame.groupby(gcol, dropna=False)[vcol].agg(how_l)
                n_groups = len(grouped)
                grouped = grouped.sort_values(ascending=bool(ascending)).head(max(1, min(int(top_n), MAX_ROWS)))
                table = grouped.rename(label).reset_index()
                state.table, state.chart = table, {"kind": "bar", "x": gcol, "y": label}
                log("aggregate", args, True)
                return to_jsonable({"groups_total": n_groups, "rows_used": len(frame),
                                    "rows": table.to_dict("records")})
            value = frame[vcol].agg(how_l)
            state.table, state.chart = pd.DataFrame({"metric": [label], "value": [value]}), None
            log("aggregate", args, True)
            return to_jsonable({"result": value, "rows_used": len(frame), "metric": label})
        except Exception as err:  # noqa: BLE001 - returned to the model so it can retry
            log("aggregate", args, False)
            return fail(str(err))

    def time_trend(date_column: str, value_column: str, how: str = "sum", freq: str = "M",
                   filter_column: str = "", filter_op: str = "==", filter_value: str = "") -> dict:
        """Trend of a numeric column over time (per day, week, month, quarter or year).

        Args:
            date_column: a date column.
            value_column: numeric column to aggregate (or any column when how='count').
            how: sum, mean, median, count, min or max.
            freq: D=day, W=week, M=month, Q=quarter, Y=year.
            filter_column: optional column to filter on first.
            filter_op: ==, !=, >, <, >=, <= (numbers/dates) or ==, !=, contains (text).
            filter_value: value to compare with.
        """
        args = dict(date_column=date_column, value_column=value_column, how=how, freq=freq,
                    filter_column=filter_column, filter_op=filter_op, filter_value=filter_value)
        try:
            how_l = str(how).strip().lower()
            if how_l not in AGGS[:-1]:
                raise ValueError(f"how must be one of {AGGS[:-1]}")
            dcol, vcol = resolve(date_column), resolve(value_column)
            if dcol is None or _kind(df[dcol]) != "date":
                raise ValueError(f"'{date_column}' is not a date column")
            if vcol is None:
                raise ValueError(f"Unknown value_column '{value_column}'")
            if how_l != "count" and _kind(df[vcol]) != "number":
                raise ValueError(f"'{vcol}' is not numeric")
            f = FREQ.get(str(freq).strip().upper())
            if f is None:
                raise ValueError(f"freq must be one of {list(FREQ)}")
            frame, err = apply_filter(df, filter_column, filter_op, filter_value)
            if err:
                raise ValueError(err)
            frame = frame.dropna(subset=[dcol])
            if frame.empty:
                log("time_trend", args, True)
                return {"result": None, "note": "No rows to analyse"}
            label = f"{how_l}_{vcol}"
            series = frame.set_index(dcol)[vcol].resample(f).agg(how_l)
            table = series.rename(label).reset_index()
            table[dcol] = table[dcol].dt.strftime("%Y-%m-%d")
            state.table, state.chart = table, {"kind": "line", "x": dcol, "y": label}
            log("time_trend", args, True)
            shown = table.tail(MAX_ROWS)
            return to_jsonable({"periods": len(table), "rows": shown.to_dict("records"),
                                "note": "only the last 50 periods shown" if len(table) > MAX_ROWS else ""})
        except Exception as err:  # noqa: BLE001
            log("time_trend", args, False)
            return fail(str(err))

    def value_counts(column: str, top_n: int = 10) -> dict:
        """How often each value of a column appears (e.g. orders per ship_mode).

        Args:
            column: any column.
            top_n: number of values to return (max 50).
        """
        args = {"column": column, "top_n": top_n}
        col = resolve(column)
        if col is None:
            log("value_counts", args, False)
            return fail(f"Unknown column '{column}'")
        counts = df[col].value_counts(dropna=False).head(max(1, min(int(top_n), MAX_ROWS)))
        table = counts.rename("count").rename_axis(col).reset_index()
        state.table, state.chart = table, {"kind": "bar", "x": col, "y": "count"}
        log("value_counts", args, True)
        return to_jsonable({"distinct_values": int(df[col].nunique(dropna=True)),
                            "rows": table.to_dict("records")})

    def correlation(column_a: str, column_b: str) -> dict:
        """Pearson correlation (-1 to 1) between two numeric columns, e.g. discount vs profit.

        Args:
            column_a: first numeric column.
            column_b: second numeric column.
        """
        args = {"column_a": column_a, "column_b": column_b}
        a, b = resolve(column_a), resolve(column_b)
        if a is None or b is None or _kind(df[a]) != "number" or _kind(df[b]) != "number":
            log("correlation", args, False)
            return fail("Both columns must exist and be numeric")
        pair = df[[a, b]].dropna()
        r = pair[a].corr(pair[b]) if len(pair) > 2 else float("nan")
        log("correlation", args, True)
        return to_jsonable({"correlation": r, "rows_used": len(pair)})

    def top_rows(sort_column: str, n: int = 10, ascending: bool = False, columns: str = "") -> dict:
        """Return the n rows with the largest (or smallest) value of a column - e.g. the
        10 most loss-making orders.

        Args:
            sort_column: numeric or date column to sort by.
            n: number of rows (max 50).
            ascending: False = largest first, True = smallest first.
            columns: optional comma-separated list of columns to show (max 8).
        """
        args = {"sort_column": sort_column, "n": n, "ascending": ascending, "columns": columns}
        col = resolve(sort_column)
        if col is None or _kind(df[col]) == "text":
            log("top_rows", args, False)
            return fail(f"'{sort_column}' must be an existing numeric or date column")
        show = [resolve(c.strip()) for c in columns.split(",") if c.strip()] if columns else columns_default(col)
        if any(c is None for c in show):
            log("top_rows", args, False)
            return fail("One of the requested columns does not exist")
        table = df.sort_values(col, ascending=bool(ascending)).head(max(1, min(int(n), MAX_ROWS)))[show[:8]]
        state.table, state.chart = table.reset_index(drop=True), None
        log("top_rows", args, True)
        return to_jsonable({"rows": table.to_dict("records")})

    def columns_default(sort_col):
        return [sort_col] + [c for c in columns if c != sort_col][:5]

    return [describe_dataset, summarize_column, aggregate, time_trend, value_counts,
            correlation, top_rows]
