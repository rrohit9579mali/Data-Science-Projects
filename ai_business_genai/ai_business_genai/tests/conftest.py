import io
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def messy_xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Sales Report 2026"])  # title row
    ws.append(["Employee ID", " Region ", "Sales Amount", "Order Date", "Phone", "Notes"])
    for row in [
        ["E101", "North", "₹5,000", "15-01-2026", "0987654321", None],
        ["E102", "north ", "N/A", "16-01-2026", "0987654322", None],
        ["E102", "NORTH", "3,000", "16-01-2026", "0987654322", None],
        ["E103", "South", "-2000", "Invalid", "0987654323", None],
        ["E101", "North", "₹5,000", "15-01-2026", "0987654321", None],  # exact duplicate
        [None, None, None, None, None, None],                             # empty row
        ["E104", "South", "(500)", "17/01/2026", "0987654324", None],
    ]:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def sales_df() -> pd.DataFrame:
    return pd.DataFrame({
        "order_id": ["A1", "A2", "A3", "A4", "A5", "A6"],
        "region": ["North", "North", "South", "South", "East", "East"],
        "category": ["Tech", "Furniture", "Tech", "Tech", "Furniture", "Tech"],
        "sales": [100.0, 200.0, 300.0, 400.0, 50.0, 150.0],
        "profit": [10.0, -20.0, 30.0, 40.0, 5.0, 15.0],
        "order_date": pd.to_datetime(["2025-01-05", "2025-01-20", "2025-02-10",
                                      "2025-03-01", "2025-03-15", "2025-03-20"]),
    })
