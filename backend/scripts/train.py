"""Compare clustering algorithms, fit the production model and write the model card data."""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.features import MODEL_FEATURES, add_derived, to_matrix  # noqa: E402
from app.services.segmentation import fit_model  # noqa: E402

customers = pd.read_csv(ROOT / "data" / "customers.csv", dtype={"customer_id": str})
frame = add_derived(customers)
X = StandardScaler().fit_transform(to_matrix(frame))

rows = []
for k in range(3, 7):
    for name, labels in {
        "K-Means": KMeans(k, n_init=20, random_state=42).fit_predict(X),
        "Gaussian Mixture": GaussianMixture(k, n_init=3, random_state=42).fit_predict(X),
        "Agglomerative (Ward)": AgglomerativeClustering(k).fit_predict(X),
    }.items():
        rows.append({"algorithm": name, "k": k,
                     "silhouette": round(float(silhouette_score(X, labels)), 3),
                     "davies_bouldin": round(float(davies_bouldin_score(X, labels)), 3),
                     "calinski_harabasz": round(float(calinski_harabasz_score(X, labels)), 1),
                     "smallest_group": round(float(np.bincount(labels).min() / len(labels)), 3)})

# Stability: refit on 80% bootstraps and compare assignments on all customers.
base = KMeans(4, n_init=20, random_state=42).fit(X)
rng = np.random.default_rng(42)
scores = []
for seed in range(20):
    idx = rng.choice(len(X), int(len(X) * 0.8), replace=False)
    km = KMeans(4, n_init=5, random_state=seed).fit(X[idx])
    scores.append(adjusted_rand_score(base.labels_, km.predict(X)))

model = fit_model(customers)
explained = np.linalg.svd(X - X.mean(axis=0), compute_uv=False) ** 2
model.meta = {
    "trained_on": date.today().isoformat(),
    "customers": len(customers),
    "features": MODEL_FEATURES,
    "chosen": {"algorithm": "K-Means", "k": 4},
    "comparison": rows,
    "stability_ari_mean": round(float(np.mean(scores)), 3),
    "stability_ari_min": round(float(np.min(scores)), 3),
    "pca_explained": [round(float(v), 3) for v in (explained / explained.sum())[:3]],
}
model.save(ROOT / "artifacts" / "segmora_model.json")
final = model.predict(customers)["segment"]
print("final model silhouette", round(float(silhouette_score(X, final)), 3), final.value_counts().to_dict())
for row in rows:
    print(row)
print({k: v for k, v in model.meta.items() if k != "comparison"}, model.keys)
