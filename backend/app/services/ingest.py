"""Read uploaded files, recognise columns and produce a clean customer table."""
from __future__ import annotations

import io
import re

import pandas as pd

from .features import BASE_FEATURES, aggregate_transactions

SYNONYMS: dict[str, list[str]] = {
    "customer_id": ["customer id", "customerid", "customer", "client id", "client", "user id", "member id", "cust id", "id"],
    "recency_days": ["recency", "recency days", "days since last purchase", "days since last order", "last purchase days"],
    "orders": ["orders", "frequency", "order count", "number of orders", "total orders", "purchases", "num orders"],
    "total_spend": ["total spend", "monetary", "spend", "total spent", "revenue", "total amount", "lifetime value", "ltv", "amount"],
    "tenure_days": ["tenure", "tenure days", "days as customer", "customer age days", "account age days"],
    "product_variety": ["product variety", "different products", "unique products", "distinct products", "products"],
    "invoice": ["invoice", "invoice no", "invoiceno", "invoice number", "order id", "orderid", "order number", "transaction id"],
    "invoice_date": ["invoice date", "invoicedate", "order date", "date", "purchase date", "transaction date"],
    "quantity": ["quantity", "qty", "units"],
    "unit_price": ["unit price", "unitprice", "price", "item price"],
    "product": ["product", "stock code", "stockcode", "sku", "product id", "item"],
}
CUSTOMER_REQUIRED = ["recency_days", "orders", "total_spend"]
TX_REQUIRED = ["customer_id", "invoice", "invoice_date", "quantity", "unit_price"]


class IngestError(ValueError):
    def __init__(self, message: str, columns: list[str] | None = None, missing: list[str] | None = None):
        super().__init__(message)
        self.columns, self.missing = columns or [], missing or []


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def read_table(content: bytes, filename: str, max_rows: int) -> pd.DataFrame:
    name = (filename or "").lower()
    try:
        if name.endswith((".xlsx", ".xlsm")):
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl", nrows=max_rows + 1)
        elif name.endswith((".csv", ".txt")):
            df = None
            for encoding in ("utf-8-sig", "latin-1"):
                try:
                    df = pd.read_csv(io.BytesIO(content), sep=None, engine="python", encoding=encoding,
                                     nrows=max_rows + 1)
                    break
                except UnicodeDecodeError:
                    continue
        else:
            raise IngestError("Please upload a .csv or .xlsx file.")
    except IngestError:
        raise
    except Exception as exc:
        raise IngestError("This file could not be read. Check that it is a valid CSV or Excel file.") from exc
    if df is None or df.empty:
        raise IngestError("This file has no rows.")
    if len(df) > max_rows:
        raise IngestError(f"This file has more than {max_rows:,} rows. Split it and upload again.")
    return df


def detect(columns: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    normalised = {c: _norm(c) for c in columns}
    for field_name, names in SYNONYMS.items():
        for candidate in names:
            match = next((c for c, n in normalised.items() if n == candidate and c not in found.values()), None)
            if match is not None:
                found[field_name] = match
                break
    return found


def to_customers(df: pd.DataFrame, mapping: dict[str, str] | None = None) -> tuple[pd.DataFrame, dict]:
    columns = [str(c) for c in df.columns]
    df = df.copy()
    df.columns = columns
    found = detect(columns)
    for key, value in (mapping or {}).items():
        if value not in columns or key not in SYNONYMS:
            raise IngestError(f"Column '{value}' is not in this file.", columns)
        found[key] = value

    tx_score = sum(k in found for k in TX_REQUIRED if k != "customer_id")
    customer_score = sum(k in found for k in CUSTOMER_REQUIRED)
    is_transactions = all(k in found for k in TX_REQUIRED) or (
        tx_score > customer_score and not all(k in found for k in CUSTOMER_REQUIRED))
    required = TX_REQUIRED if is_transactions else CUSTOMER_REQUIRED
    missing = [k for k in required if k not in found]
    if missing:
        raise IngestError("Some columns could not be recognised. Match them below.", columns, missing)

    # Only recognised columns are kept: names, emails and phone numbers never go further.
    clean = df[list(found.values())].rename(columns={v: k for k, v in found.items()})
    total_rows = len(clean)
    if is_transactions:
        customers = aggregate_transactions(clean)
        shape = "transactions"
    else:
        for col in BASE_FEATURES:
            if col in clean.columns:
                clean[col] = pd.to_numeric(clean[col], errors="coerce")
        clean["tenure_days"] = clean["tenure_days"] if "tenure_days" in clean else clean["recency_days"]
        clean["product_variety"] = clean["product_variety"] if "product_variety" in clean else clean["orders"]
        if "customer_id" not in clean:
            clean["customer_id"] = [f"row-{i + 1}" for i in range(len(clean))]
        customers = clean.dropna(subset=BASE_FEATURES)
        shape = "customers"
    customers = customers[(customers["orders"] >= 1) & (customers["total_spend"] > 0) &
                          (customers["recency_days"] >= 0)].copy()
    if customers.empty:
        raise IngestError("No usable customers were found. Orders and spend must be above zero.")
    customers["customer_id"] = customers["customer_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    customers["tenure_days"] = customers[["tenure_days", "recency_days"]].max(axis=1)
    customers = customers[["customer_id", *BASE_FEATURES]].reset_index(drop=True)
    return customers, {"shape": shape, "rows_read": total_rows, "customers": len(customers),
                       "skipped": (total_rows - len(customers)) if shape == "customers" else 0,
                       "columns_used": found}
