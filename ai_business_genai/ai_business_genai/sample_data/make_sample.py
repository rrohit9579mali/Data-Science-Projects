"""Generate sample_data/messy_sales.xlsx - a deliberately dirty sales sheet for demos and tests.

Run:  uv run python sample_data/make_sample.py
"""
from pathlib import Path

import numpy as np
from openpyxl import Workbook

rng = np.random.default_rng(42)
regions = ["North", "South", "East", "West"]
products = ["Laptop", "Phone", "Tablet", "Monitor", "Keyboard"]
price = {"Laptop": 55000, "Phone": 22000, "Tablet": 18000, "Monitor": 9000, "Keyboard": 1500}

wb = Workbook()
ws = wb.active
ws.title = "Sales"
ws.append(["ACME Retail - Monthly Sales Report 2026"])          # title row above the header
ws.append(["Order ID", " Region ", "Product", "Sales Amount", "Quantity", "Order Date", "Phone", "Notes"])

rows = []
for i in range(1, 301):
    product = str(rng.choice(products))
    qty = int(rng.integers(1, 6))
    amount = price[product] * qty * float(rng.uniform(0.9, 1.1))
    month, day = int(rng.integers(1, 10)), int(rng.integers(1, 28))
    region = str(rng.choice(regions))
    rows.append([f"ORD{1000 + i}",
                 str(rng.choice([f" {region}", region.lower(), region.upper(), region])),
                 product, f"₹{amount:,.0f}", qty, f"{day:02d}-{month:02d}-2026",
                 f"09{int(rng.integers(10**8, 10**9))}", None])

rows[5][3] = "N/A"                    # missing amount
rows[17][3] = "-45,000"               # negative amount (refund or error?)
rows[40][3] = "₹9,500,000"            # extreme outlier
rows[60][5] = "Invalid"               # bad date
rows[75][2] = None                    # missing product
rows.append(list(rows[10]))           # exact duplicate row
rows.append(list(rows[11]))           # exact duplicate row
rows.append([None] * 8)               # empty row
rows.append(["ORD1050", "North", "Laptop", "₹60,000", 1, "12-03-2026", "0912345678", None])  # same ID again
for r in rows:
    ws.append(r)

out = Path(__file__).with_name("messy_sales.xlsx")
wb.save(out)
print(f"wrote {out}")
