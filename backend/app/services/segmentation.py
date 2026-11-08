"""Segmentation engine: fit, name, predict and explain.

Serving needs only NumPy, which keeps the serverless bundle small. Scikit-learn is used
offline in scripts/train.py to compare algorithms.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .features import BASE_FEATURES, MODEL_FEATURES, add_derived, to_matrix

K = 4
SEGMENT_META = {
    "vip": {"name": "VIP Shopper", "tagline": "Loves luxury, spends the most", "color": "#B98A6E"},
    "regular": {"name": "Loyal Regular", "tagline": "Comes back like a daily coffee", "color": "#E0481F"},
    "deal": {"name": "Deal Hunter", "tagline": "Saves money, waits for sales", "color": "#F0E0C8"},
    "new": {"name": "New Customer", "tagline": "Just started, ready to grow", "color": "#D99A2B"},
}
LABELS = {
    "recency_days": "days since last purchase",
    "orders": "orders",
    "total_spend": "total spend",
    "tenure_days": "days as a customer",
    "product_variety": "different products",
    "avg_order_value": "average order value",
}


def _distances(X: np.ndarray, centers: np.ndarray) -> np.ndarray:
    return np.sqrt(((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))


@dataclass
class SegmentModel:
    mean: np.ndarray
    scale: np.ndarray
    centers: np.ndarray
    pca_mean: np.ndarray
    pca_components: np.ndarray
    keys: list[str]
    temperature: float
    reference: np.ndarray  # sorted values per MODEL_FEATURES, for percentile lookups
    meta: dict = field(default_factory=dict)

    def _scaled(self, df: pd.DataFrame) -> np.ndarray:
        return (to_matrix(df) - self.mean) / self.scale

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return segment keys and a 0-1 match strength for every customer row."""
        dist = _distances(self._scaled(add_derived(df)), self.centers)
        idx = dist.argmin(axis=1)
        weights = np.exp(-(dist**2) / self.temperature)
        strength = weights.max(axis=1) / weights.sum(axis=1).clip(min=1e-300)
        return pd.DataFrame({"segment": [self.keys[i] for i in idx], "strength": strength.round(3)}, index=df.index)

    def project(self, df: pd.DataFrame) -> np.ndarray:
        return (self._scaled(add_derived(df)) - self.pca_mean) @ self.pca_components.T

    def percentile(self, feature: str, value: float) -> float:
        col = self.reference[:, MODEL_FEATURES.index(feature)]
        return float(np.searchsorted(col, value, side="right") / len(col) * 100)

    def explain(self, row: pd.Series, key: str) -> list[dict]:
        """Why this segment: features where the customer and the segment both stand out."""
        frame = add_derived(row[BASE_FEATURES].to_frame().T.astype(float))
        z_customer = self._scaled(frame)[0]
        z_segment = self.centers[self.keys.index(key)]
        order = np.argsort(-(z_segment * z_customer))
        reasons = []
        for i in order[:3]:
            feature = MODEL_FEATURES[i]
            value = float(frame.iloc[0][feature])
            reasons.append({"feature": feature, "label": LABELS[feature], "value": round(value, 2),
                            "percentile": round(self.percentile(feature, value)),
                            "direction": "high" if z_customer[i] > 0 else "low"})
        return reasons

    def save(self, path: Path) -> None:
        arrays = {k: getattr(self, k).round(8).tolist() for k in
                  ("mean", "scale", "centers", "pca_mean", "pca_components", "reference")}
        path.write_text(json.dumps({**arrays, "keys": self.keys, "temperature": self.temperature, "meta": self.meta}))

    @classmethod
    def load(cls, path: Path) -> SegmentModel:
        raw = json.loads(path.read_text())
        arrays = {k: np.array(raw[k], dtype=float) for k in
                  ("mean", "scale", "centers", "pca_mean", "pca_components", "reference")}
        return cls(**arrays, keys=raw["keys"], temperature=raw["temperature"], meta=raw["meta"])


def name_clusters(centers_raw: pd.DataFrame) -> list[str]:
    """Assign business names from behaviour, so labels do not depend on cluster order.

    VIP has the highest total spend; of the rest, New has the shortest tenure; of the
    remaining two, the lower average order value is Deal Hunter.
    """
    remaining = list(centers_raw.index)
    keys: dict[int, str] = {}
    vip = centers_raw.loc[remaining, "total_spend"].idxmax()
    keys[vip] = "vip"
    remaining.remove(vip)
    new = centers_raw.loc[remaining, "tenure_days"].idxmin()
    keys[new] = "new"
    remaining.remove(new)
    deal = centers_raw.loc[remaining, "avg_order_value"].idxmin()
    keys[deal] = "deal"
    remaining.remove(deal)
    keys[remaining[0]] = "regular"
    return [keys[i] for i in sorted(keys)]


def kmeans(X: np.ndarray, k: int, seed: int, n_init: int = 10, max_iter: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """K-Means with k-means++ starts; returns centers and labels of the best run."""
    rng = np.random.default_rng(seed)
    best: tuple[float, np.ndarray, np.ndarray] | None = None
    for _ in range(n_init):
        centers = [X[rng.integers(len(X))]]
        for _ in range(k - 1):
            d2 = (_distances(X, np.array(centers)) ** 2).min(axis=1)
            total = d2.sum()
            pick = rng.integers(len(X)) if total == 0 else rng.choice(len(X), p=d2 / total)
            centers.append(X[pick])
        c = np.array(centers)
        labels = np.zeros(len(X), dtype=int)
        for _ in range(max_iter):
            labels = _distances(X, c).argmin(axis=1)
            updated = np.array([X[labels == j].mean(axis=0) if (labels == j).any() else c[j] for j in range(k)])
            moved = np.abs(updated - c).max()
            c = updated
            if moved < 1e-5:
                break
        labels = _distances(X, c).argmin(axis=1)
        inertia = float((_distances(X, c).min(axis=1) ** 2).sum())
        if best is None or inertia < best[0]:
            best = (inertia, c, labels)
    assert best is not None
    return best[1], best[2]


def fit_model(customers: pd.DataFrame, seed: int = 42) -> SegmentModel:
    frame = add_derived(customers)
    matrix = to_matrix(frame)
    mean, scale = matrix.mean(axis=0), matrix.std(axis=0)
    scale[scale == 0] = 1.0
    X = (matrix - mean) / scale
    centers, labels = kmeans(X, K, seed)
    pca_mean = X.mean(axis=0)
    _, _, vt = np.linalg.svd(X - pca_mean, full_matrices=False)
    medians = frame[MODEL_FEATURES].groupby(labels).median().reindex(range(K)).fillna(0)
    assigned = _distances(X, centers).min(axis=1) ** 2
    reference = np.sort(frame[MODEL_FEATURES].to_numpy(dtype=float), axis=0)
    return SegmentModel(mean, scale, centers, pca_mean, vt[:3], name_clusters(medians),
                        float(np.median(assigned)) or 1.0, reference)
