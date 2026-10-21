import io

import numpy as np
import pandas as pd

from cleaner import CleaningOptions, clean_data, read_file, to_excel_bytes


def _clean(messy_xlsx_bytes, **opts):
    raw, header_idx = read_file(messy_xlsx_bytes, "t.xlsx")
    return raw, header_idx, clean_data(raw, CleaningOptions(**opts), row_offset=header_idx + 2)


def test_title_row_is_skipped_and_header_detected(messy_xlsx_bytes):
    raw, header_idx, _ = _clean(messy_xlsx_bytes)
    assert header_idx == 1
    assert "Employee ID" in list(raw.columns)


def test_column_names_standardised(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    assert list(res.df.columns) == ["employee_id", "region", "sales_amount", "order_date", "phone"]


def test_currency_text_becomes_numbers(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    s = res.df["sales_amount"]
    assert s.dtype == float
    assert 5000.0 in s.values and 3000.0 in s.values
    assert -500.0 in s.values           # "(500)" accounting negative
    assert s.isna().sum() == 1          # "N/A" stays blank, not zero


def test_missing_values_are_not_filled_by_default(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    assert res.df["sales_amount"].isna().sum() == 1


def test_median_fill_is_opt_in(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes, missing_strategy="median")
    assert res.df["sales_amount"].isna().sum() == 0


def test_phone_keeps_leading_zero(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    assert res.df["phone"].iloc[0] == "0987654321"


def test_dates_parsed_day_first_and_invalid_left_blank(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    d = res.df["order_date"]
    assert pd.api.types.is_datetime64_any_dtype(d)
    assert d.iloc[0] == pd.Timestamp("2026-01-15")
    assert d.isna().sum() == 1
    assert "Invalid date" in set(res.issues["issue"])


def test_case_variants_unified(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    assert set(res.df["region"].dropna()) == {"North", "South"}


def test_exact_duplicates_removed_but_kept_aside(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    assert len(res.removed_rows) == 1
    assert len(res.df) == 5            # 7 rows - 1 empty row - 1 exact duplicate
    assert res.df["employee_id"].tolist() == ["E101", "E102", "E102", "E103", "E104"]


def test_negative_value_is_flagged_not_changed(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    neg = res.issues[res.issues["issue"] == "Negative value"]
    assert len(neg) >= 1
    assert (res.df["sales_amount"] < 0).sum() >= 1   # value untouched


def test_excel_report_has_expected_sheets(messy_xlsx_bytes):
    _, _, res = _clean(messy_xlsx_bytes)
    sheets = pd.ExcelFile(io.BytesIO(to_excel_bytes(res))).sheet_names
    for name in ("Cleaned_Data", "Cleaning_Log", "Review_Needed", "Column_Profile"):
        assert name in sheets


def test_csv_with_leading_zero_ids_and_currency():
    csv = b"Order ID,Amount,Date\n001,\"1,200\",05-06-2026\n002,N/A,06-06-2026\n003,300,07-06-2026\n"
    raw, _ = read_file(csv, "a.csv")
    res = clean_data(raw)
    assert res.df["order_id"].tolist() == ["001", "002", "003"]
    assert res.df["amount"].iloc[0] == 1200.0
    assert np.isnan(res.df["amount"].iloc[1])
    assert res.df["date"].iloc[0] == pd.Timestamp("2026-06-05")


def test_clean_data_does_not_modify_input(messy_xlsx_bytes):
    raw, _ = read_file(messy_xlsx_bytes, "t.xlsx")
    before = raw.copy()
    clean_data(raw)
    pd.testing.assert_frame_equal(raw, before)
