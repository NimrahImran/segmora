"""Build the customer table from the public UCI Online Retail invoice lines.

Run: python scripts/build_dataset.py data/raw.csv
Output: data/customers.csv (one row per customer; the raw file is not committed).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.features import aggregate_transactions  # noqa: E402

raw = pd.read_csv(sys.argv[1], encoding="latin-1", dtype={"InvoiceNo": str, "CustomerID": str})
n_lines = len(raw)
raw = raw.dropna(subset=["CustomerID"]).rename(
    columns={"CustomerID": "customer_id", "InvoiceNo": "invoice", "InvoiceDate": "invoice_date",
             "Quantity": "quantity", "UnitPrice": "unit_price", "StockCode": "product"})
raw["customer_id"] = raw["customer_id"].str.replace(r"\.0$", "", regex=True)
customers = aggregate_transactions(raw)
customers = customers[customers["total_spend"] > 0].round(2)
out = Path(__file__).resolve().parents[1] / "data" / "customers.csv"
customers.to_csv(out, index=False)
print(f"{n_lines} invoice lines -> {len(customers)} customers -> {out}")
