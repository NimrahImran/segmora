"""Turn labelled customers into the payload every dashboard view reads."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import add_derived
from .segmentation import SEGMENT_META, SegmentModel

ORDER = ["vip", "regular", "deal", "new"]
MAX_POINTS = 1600


def _priority(frame: pd.DataFrame, limit: int = 25) -> list[dict]:
    """Rank who to contact first: value at risk, with a stated reason and next step."""
    df = frame.copy()
    df["value_rank"] = df["total_spend"].rank(pct=True)
    df["usual_gap"] = (df["tenure_days"] / (df["orders"] - 1).clip(lower=1)).where(df["orders"] > 1)
    df["overdue"] = df["recency_days"] / df["usual_gap"]
    scored = []
    for row in df.itertuples():
        if row.segment in ("vip", "regular") and row.orders > 1 and row.overdue >= 1.5 and row.recency_days >= 21:
            score, reason, action = (
                row.value_rank * min(row.overdue, 4) / 4 * 100,
                f"Usually buys every {round(row.usual_gap)} days, quiet for {int(row.recency_days)}",
                "Call personally" if row.segment == "vip" else "Send a come-back offer",
            )
        elif row.segment == "new" and row.recency_days <= 60:
            score, reason, action = (
                row.value_rank * 55, f"First order {int(row.recency_days)} days ago, no second order yet",
                "Send a welcome offer",
            )
        else:
            continue
        scored.append({"customer_id": row.customer_id, "segment": row.segment, "score": round(float(score), 1),
                       "total_spend": round(float(row.total_spend), 2), "reason": reason, "action": action})
    return sorted(scored, key=lambda r: -r["score"])[:limit]


def build(model: SegmentModel, customers: pd.DataFrame, source: dict, currency: str = "",
          span_override: np.ndarray | None = None) -> dict:
    labelled = customers.reset_index(drop=True).join(model.predict(customers.reset_index(drop=True)))
    frame = add_derived(labelled)
    total_spend = float(frame["total_spend"].sum())
    segments = []
    for key in ORDER:
        part = frame[frame["segment"] == key]
        n = len(part)
        segments.append({
            "key": key, **SEGMENT_META[key], "customers": n,
            "customer_share": round(n / len(frame), 4),
            "revenue": round(float(part["total_spend"].sum()), 2),
            "revenue_share": round(float(part["total_spend"].sum()) / total_spend, 4),
            "medians": {} if n == 0 else {
                c: round(float(part[c].median()), 2)
                for c in ["recency_days", "orders", "total_spend", "tenure_days", "product_variety", "avg_order_value"]},
        })
    coords = model.project(labelled[["recency_days", "orders", "total_spend", "tenure_days", "product_variety"]])
    span = (span_override if span_override is not None else np.percentile(np.abs(coords), 98, axis=0)).clip(min=1e-6)
    coords = np.clip(coords / span, -1.2, 1.2)
    sample = np.random.default_rng(7).permutation(len(labelled))[:MAX_POINTS]
    points = [{"id": labelled.at[int(i), "customer_id"], "s": labelled.at[int(i), "segment"],
               "x": round(float(coords[i, 0]), 3), "y": round(float(coords[i, 1]), 3),
               "z": round(float(coords[i, 2]), 3),
               "spend": round(float(labelled.at[int(i), "total_spend"]), 2),
               "orders": int(labelled.at[int(i), "orders"])} for i in sample]
    return {
        "source": source, "currency": currency, "customers": len(frame),
        "total_revenue": round(total_spend, 2), "segments": segments, "points": points, "span": [round(float(v), 4) for v in span],
        "priority": _priority(frame),
        "table": labelled.round(2).to_dict("records"),
    }
