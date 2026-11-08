"""Customer-level feature engineering shared by training and inference."""
from __future__ import annotations

import numpy as np
import pandas as pd

BASE_FEATURES = ["recency_days", "orders", "total_spend", "tenure_days", "product_variety"]
MODEL_FEATURES = [*BASE_FEATURES, "avg_order_value"]


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["avg_order_value"] = out["total_spend"] / out["orders"].clip(lower=1)
    return out


def to_matrix(df: pd.DataFrame) -> np.ndarray:
    """Log-transform: spend and order counts are heavily right-skewed."""
    return np.log1p(df[MODEL_FEATURES].clip(lower=0).to_numpy(dtype=float))


def aggregate_transactions(tx: pd.DataFrame) -> pd.DataFrame:
    """Roll invoice lines (customer, invoice, date, quantity, price) up to one row per customer.

    Recency is measured against the latest date in the file, so old exports are not
    all labelled as lapsed customers.
    """
    frame = tx.copy()
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="coerce", format="mixed")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="coerce")
    frame = frame.dropna(subset=["customer_id", "invoice_date", "quantity", "unit_price"])
    frame = frame[frame["unit_price"] > 0]
    frame["invoice"] = frame["invoice"].astype(str)
    frame["is_return"] = frame["invoice"].str.upper().str.startswith("C") | (frame["quantity"] < 0)
    sales = frame[~frame["is_return"]].copy()
    if sales.empty:
        return pd.DataFrame(columns=["customer_id", *BASE_FEATURES])
    sales["line_total"] = sales["quantity"] * sales["unit_price"]
    snapshot = sales["invoice_date"].max() + pd.Timedelta(days=1)
    product_col = "product" if "product" in sales.columns else "invoice"
    grouped = sales.groupby("customer_id").agg(
        last=("invoice_date", "max"),
        first=("invoice_date", "min"),
        orders=("invoice", "nunique"),
        total_spend=("line_total", "sum"),
        product_variety=(product_col, "nunique"),
    )
    grouped["recency_days"] = (snapshot - grouped["last"]).dt.days
    grouped["tenure_days"] = (snapshot - grouped["first"]).dt.days
    return grouped.reset_index()[["customer_id", *BASE_FEATURES]]
