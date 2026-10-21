import pytest
from pydantic import ValidationError

from schemas import BusinessReport, check_grounding, extract_numbers, report_to_markdown

FACTS = "sales sum 1,200.00 mean 200.00 ; sum of sales by region: North=300.00, South=700.00"


def _report(**overrides):
    base = dict(
        headline="South leads sales",
        executive_summary=["South brings most revenue.", "North is smaller."],
        key_metrics=[{"name": "Total sales", "value": "1,200.00", "context": "All orders"}],
        insights=[{"title": "South is strongest", "detail": "South sold 700.00.", "evidence": "sales by region"}],
        risks=[{"title": "Missing values", "severity": "low", "detail": "A few blanks."}],
        recommended_actions=["Review blanks."],
    )
    base.update(overrides)
    return BusinessReport(**base)


def test_valid_report_passes():
    assert _report().headline == "South leads sales"


def test_invalid_severity_rejected():
    with pytest.raises(ValidationError):
        _report(risks=[{"title": "x", "severity": "catastrophic", "detail": "y"}])


def test_too_few_summary_points_rejected():
    with pytest.raises(ValidationError):
        _report(executive_summary=["only one"])


def test_blank_action_rejected():
    with pytest.raises(ValidationError):
        _report(recommended_actions=["  "])


def test_extract_numbers_handles_commas_and_negatives():
    assert extract_numbers("Profit fell to -2,500.50 from 1,000") == [-2500.5, 1000.0]


def test_grounded_report_has_no_warnings():
    assert check_grounding(_report(), FACTS) == []


def test_invented_number_is_flagged():
    bad = _report(key_metrics=[{"name": "Total sales", "value": "9,999.00", "context": "made up"}])
    warnings = check_grounding(bad, FACTS)
    assert len(warnings) == 1 and "9,999" in warnings[0]


def test_small_counts_and_years_are_ignored():
    rep = _report(executive_summary=["Top 3 regions in 2025 matter.", "Second point."])
    assert check_grounding(rep, FACTS) == []


def test_markdown_contains_sections_and_warnings():
    md = report_to_markdown(_report(), ["something unverified"])
    for part in ("# South leads sales", "## Key metrics", "## Recommended actions", "something unverified"):
        assert part in md
