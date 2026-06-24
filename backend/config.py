from __future__ import annotations

import math
import os
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on"}


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    text = value.strip().lower()
    if not text:
        return default
    return text in TRUE_VALUES


def env_int(name: str, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        value = int(float(str(os.getenv(name, str(default))).strip()))
    except (TypeError, ValueError):
        value = default
    return int(_clamp(value, default, min_value, max_value))


def env_float(name: str, default: float, min_value: float | None = None, max_value: float | None = None) -> float:
    try:
        value = float(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        value = default
    return float(_clamp(value, default, min_value, max_value))


def _clamp(value: Any, default: int | float, min_value: Any, max_value: Any) -> int | float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value
