"""
schemas.py
==========
Structured output for the AI business report + a "grounding check".

Why this exists
---------------
Free-text LLM reports can contain invented numbers. Here the model must return JSON that
matches `BusinessReport` (validated by Pydantic), and every number it quotes is compared
with the statistics we computed ourselves. Numbers that cannot be found are shown to the
user as "unverified" instead of being silently trusted.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Metric(BaseModel):
    name: str = Field(description="Short metric name, e.g. 'Total sales'")
    value: str = Field(description="Value copied EXACTLY from the statistics, no K/M abbreviations")
    context: str = Field(description="One short sentence explaining what the number means")


class Insight(BaseModel):
    title: str = Field(description="Short headline of the insight")
    detail: str = Field(description="1-3 sentences in simple business language")
    evidence: str = Field(description="Column(s) and number(s) from the statistics that support it")


class Risk(BaseModel):
    title: str
    severity: Literal["low", "medium", "high"]
    detail: str


class BusinessReport(BaseModel):
    headline: str = Field(description="One-line takeaway for a manager")
    executive_summary: list[str] = Field(min_length=2, max_length=6)
    key_metrics: list[Metric] = Field(min_length=1, max_length=10)
    insights: list[Insight] = Field(min_length=1, max_length=8)
    risks: list[Risk] = Field(max_length=8)
    recommended_actions: list[str] = Field(min_length=1, max_length=6)

    @field_validator("headline")
    @classmethod
    def _headline_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("headline must not be empty")
        return v.strip()

    @field_validator("executive_summary", "recommended_actions")
    @classmethod
    def _no_blank_items(cls, items: list[str]) -> list[str]:
        cleaned = [i.strip() for i in items if i and i.strip()]
        if len(cleaned) != len(items):
            raise ValueError("list items must not be blank")
        return cleaned


# --------------------------------------------------------------------------- #
# Grounding check
# --------------------------------------------------------------------------- #
_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def extract_numbers(text: str) -> list[float]:
    out = []
    for raw in _NUM_RE.findall(text or ""):
        try:
            out.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return out


def _is_noise(n: float) -> bool:
    """Years and tiny counts (<=12, e.g. 'top 3', 'Q4') are not worth verifying."""
    return float(n).is_integer() and (abs(n) <= 12 or 1900 <= abs(n) <= 2100)


def check_grounding(report: BusinessReport, facts: str, rel_tol: float = 0.01) -> list[str]:
    """Return human-readable warnings for numbers that do not appear in `facts`."""
    known = extract_numbers(facts)

    def supported(x: float) -> bool:
        return any(abs(x - k) <= max(rel_tol * abs(k), 0.011) or abs(abs(x) - abs(k)) < 0.011
                   for k in known)

    fields: list[tuple[str, str]] = []
    fields += [("Headline", report.headline)]
    fields += [(f"Summary point {i}", t) for i, t in enumerate(report.executive_summary, 1)]
    fields += [(f"Metric '{m.name}'", m.value) for m in report.key_metrics]
    fields += [(f"Insight '{i.title}'", f"{i.detail} {i.evidence}") for i in report.insights]
    fields += [(f"Risk '{r.title}'", r.detail) for r in report.risks]

    warnings = []
    for where, text in fields:
        bad = [n for n in extract_numbers(text) if not _is_noise(n) and not supported(n)]
        if bad:
            shown = ", ".join(f"{n:,.2f}".rstrip("0").rstrip(".") for n in bad[:4])
            warnings.append(f"{where}: number(s) {shown} not found in the computed statistics")
    return warnings


def report_to_markdown(report: BusinessReport, warnings: list[str] | None = None) -> str:
    lines = [f"# {report.headline}", "", "## Executive summary"]
    lines += [f"- {p}" for p in report.executive_summary]
    lines += ["", "## Key metrics", "", "| Metric | Value | Meaning |", "|---|---|---|"]
    lines += [f"| {m.name} | {m.value} | {m.context} |" for m in report.key_metrics]
    lines += ["", "## Insights"]
    for i in report.insights:
        lines += [f"### {i.title}", i.detail, f"*Evidence: {i.evidence}*", ""]
    lines += ["## Risks & data-quality warnings"]
    lines += [f"- **{r.severity.upper()}** - {r.title}: {r.detail}" for r in report.risks] or ["- None identified"]
    lines += ["", "## Recommended actions"]
    lines += [f"{n}. {a}" for n, a in enumerate(report.recommended_actions, 1)]
    if warnings:
        lines += ["", "## Unverified numbers (please double-check)"] + [f"- {w}" for w in warnings]
    return "\n".join(lines) + "\n"
