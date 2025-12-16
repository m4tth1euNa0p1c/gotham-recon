# core/utils/json_safe.py
"""
JSON-safe serialization utilities for CrewAI objects.
Handles CrewOutput and other non-serializable objects gracefully.
"""
from typing import Any


def make_json_safe(obj: Any) -> Any:
    """
    Recursively transform a Python object into a JSON-safe structure.

    - dict/list: traverse recursively
    - str/int/float/bool/None: pass through as-is
    - CrewAI objects, CrewOutput, etc.: convert to str()

    Args:
        obj: Any Python object

    Returns:
        JSON-serializable version of the object
    """
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, tuple):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    else:
        # Fallback: readable string representation of the object
        try:
            return str(obj)
        except Exception:
            return f"<non-serializable: {type(obj).__name__}>"
