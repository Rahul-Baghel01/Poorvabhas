"""Configurable engine settings persisted in `system_settings`."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm import Session

from app.models import SystemSetting
from app.nlp.scl import DEFAULT_SIF_POTENTIAL_CLASSES
from app.nlp.scoring import DEFAULT_PRIORITY_THRESHOLDS, DEFAULT_PRIORITY_WEIGHTS, DEFAULT_REVIEW_THRESHOLDS

DEFAULTS: dict[str, Any] = {
    "priority_weights": DEFAULT_PRIORITY_WEIGHTS,
    "priority_thresholds": DEFAULT_PRIORITY_THRESHOLDS,
    "review_thresholds": DEFAULT_REVIEW_THRESHOLDS,
    "sif_potential_classes": list(DEFAULT_SIF_POTENTIAL_CLASSES),
    "recurrence_window_days": 90,
    "pattern_min_cluster_size": 5,
    "use_classifier": True,
}


def get_setting(db: Session, key: str) -> Any:
    row = db.get(SystemSetting, key)
    if row is None:
        return copy.deepcopy(DEFAULTS[key])
    return row.value


def all_settings(db: Session) -> dict[str, Any]:
    return {k: get_setting(db, k) for k in DEFAULTS}


def set_setting(db: Session, key: str, value: Any, user_name: str | None = None) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    row = db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=value, updated_by=user_name))
    else:
        row.value = value
        row.updated_by = user_name


def validate_priority_weights(weights: dict[str, Any]) -> dict[str, float]:
    keys = set(DEFAULT_PRIORITY_WEIGHTS)
    if set(weights) != keys:
        raise ValueError(f"weights must contain exactly: {', '.join(sorted(keys))}")
    out = {k: float(v) for k, v in weights.items()}
    if any(v < 0 for v in out.values()):
        raise ValueError("weights must be non-negative")
    if abs(sum(out.values()) - 100) > 0.01:
        raise ValueError(f"weights must sum to 100 (got {sum(out.values()):g})")
    return out
