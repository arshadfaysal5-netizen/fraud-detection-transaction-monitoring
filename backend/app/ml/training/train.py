"""Model training + registry.

Trains a gradient-boosting classifier (LightGBM first, scikit-learn
RandomForest fallback so the pipeline runs anywhere), calibrates probabilities,
scores the holdout set and persists the artifact + registry.json.

Usage:
    python -m app.ml.training.train
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import numpy as np

from app.core.config import settings
from app.core.db import SessionLocal
from app.ml.training.dataset_builder import build_from_db, build_synthetic

logger = logging.getLogger(__name__)

REQUIRED_POSITIVE = 40


def _make_model(use_lightgbm: bool = True) -> tuple[object, str]:
    if use_lightgbm:
        try:
            from lightgbm import LGBMClassifier

            return (
                LGBMClassifier(
                    n_estimators=200,
                    learning_rate=0.05,
                    num_leaves=31,
                    max_depth=-1,
                    min_child_samples=20,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    verbose=-1,
                ),
                "lightgbm",
            )
        except Exception as exc:  # noqa: BLE001  (ImportError, missing libgomp, etc.)
            logger.info("LightGBM unavailable (%s) — using RandomForest fallback", exc)
    from sklearn.ensemble import RandomForestClassifier

    return (
        RandomForestClassifier(
            n_estimators=150, max_depth=12, min_samples_leaf=4, random_state=42, class_weight="balanced"
        ),
        "random_forest",
    )


def _to_labeled(dataset: dict) -> tuple[np.ndarray, np.ndarray]:
    return dataset["X"], dataset["y"]


def train_and_save(dataset: dict | None = None) -> dict:
    source_label = "production-monitoring"
    db = SessionLocal()
    try:
        if dataset is None:
            try:
                dataset = build_from_db(db)
            except Exception as exc:  # noqa: BLE001  (uninitialized DB, etc.)
                logger.info("DB dataset builder unavailable (%s); using synthetic", exc)
                dataset = None
        if dataset is None or int(np.sum(dataset["y"])) < REQUIRED_POSITIVE:
            logger.info("Real labeled data insufficient — training on synthetic dataset")
            dataset = build_synthetic(n=10_000)
            source_label = "synthetic"
    finally:
        db.close()

    X, y = _to_labeled(dataset)

    # chronologically-honest split approximation: shuffle split for synthetic
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
    from sklearn.model_selection import train_test_split

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    base, model_flavor = _make_model(use_lightgbm=True)
    model = CalibratedClassifierCV(estimator=base, method="isotonic", cv=3)
    model.fit(X_train, y_train)

    prob = model.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, prob))
    ap = float(average_precision_score(y_test, prob))
    precision, recall, thresholds = precision_recall_curve(y_test, prob)

    # operating point maximizing F1
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-9)
    best = int(np.argmax(f1[:-1]))
    opt_threshold = float(thresholds[best])
    opt_precision, opt_recall = float(precision[best]), float(recall[best])

    model_path = settings.model_path
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    import joblib

    joblib.dump(model, model_path)

    version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    registry = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source": source_label,
        "n_samples": int(len(y)),
        "n_positive": int(np.sum(y)),
        "model": f"{model_flavor}+isotonic",
        "threshold": opt_threshold,
        "metrics": {
            "roc_auc": round(auc, 4),
            "average_precision": round(ap, 4),
            "precision_at_best_f1": round(opt_precision, 4),
            "recall_at_best_f1": round(opt_recall, 4),
            "optimal_threshold": round(opt_threshold, 4),
        },
    }
    registry_path = os.path.join(os.path.dirname(model_path), "registry.json")
    with open(registry_path, "w") as fh:
        json.dump(registry, fh, indent=2)

    logger.info(
        "Model %s saved to %s — AUC-PR %.3f, P %.3f / R %.3f @ thr %.3f",
        version, model_path, ap, opt_precision, opt_recall, opt_threshold,
    )
    return registry


if __name__ == "__main__":
    from app.core.logging import setup_logging

    setup_logging()
    result = train_and_save()
    print(json.dumps(result, indent=2))