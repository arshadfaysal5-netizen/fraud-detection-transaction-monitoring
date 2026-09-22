"""ML model loading and runtime inference with graceful fallback.

The runtime loads the trained artifact (joblib) at first use. When no model has
been trained yet it returns None, and the risk engine leans on the rule engine
only. The registry JSON carries version + metrics used by admin dashboards.
"""

from __future__ import annotations

import json
import logging
import os

from app.core.config import settings
from app.ml.common import ALL_COLUMNS, FEATURE_COLUMNS, vector_from_features

logger = logging.getLogger(__name__)


class ModelRunner:
    def __init__(self) -> None:
        self._model = None
        self._info: dict | None = None
        self._loaded = False

    @property
    def info(self) -> dict | None:
        self._ensure_loaded()
        return self._info

    @property
    def available(self) -> bool:
        self._ensure_loaded()
        return self._model is not None

    @property
    def version(self) -> str | None:
        self._ensure_loaded()
        return (self._info or {}).get("version")

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        import joblib  # delayed import: ml extra is optional at runtime

        model_path = settings.model_path
        registry_path = os.path.join(os.path.dirname(model_path), "registry.json")
        if not os.path.exists(model_path):
            logger.info("No trained model at %s — rule-only risk scoring active", model_path)
            return
        try:
            self._model = joblib.load(model_path)
            if os.path.exists(registry_path):
                with open(registry_path) as fh:
                    self._info = json.load(fh)
            logger.info(
                "Loaded ML model version=%s", (self._info or {}).get("version", "?")
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load model %s: %s", model_path, exc)
            self._model = None

    def predict_proba(self, features: dict) -> float:
        """Return fraud probability in [0, 1]. Raises if model unavailable."""
        self._ensure_loaded()
        if self._model is None:
            raise RuntimeError("ML model not available")
        vec = [vector_from_features(features)]
        prob = self._model.predict_proba(vec)[0]
        # Model trained with positive label = fraud
        return float(prob[1] if prob.shape[0] > 1 else prob[0])

    def explain(self, features: dict) -> dict:
        """Top contributing factors for the transaction (feature-importance proxy)."""
        self._ensure_loaded()
        if self._model is None:
            return {}
        import numpy as np

        x = np.array(vector_from_features(features), dtype=float)
        try:
            importances = dict(zip(ALL_COLUMNS, self._model.feature_importances_))
        except Exception:  # noqa: BLE001  (e.g. linear model)
            importances = {}
        if importances:
            contributions = sorted(
                ((imp, col) for col, imp in importances.items()),
                reverse=True,
            )[:5]
            return {
                "attributions": [
                    {"feature": col, "value": round(float(features.get(col.replace("txn_type_", ""), 0) or 0), 2)}
                    for _, col in contributions
                ]
            }
        return {}


runner = ModelRunner()