# services/suite_service.py
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

SUITE_PATH = Path(__file__).resolve().parent.parent / "config" / "test_suite.yaml"


def _load() -> dict:
    with open(SUITE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"items": {}}


def _save(data: dict):
    with open(SUITE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def list_suites() -> List[dict]:
    data = _load()
    result = []
    for name, cfg in data.get("items", {}).items():
        result.append({
            "name": name,
            "enabled": cfg.get("enabled", False),
            "current_app": cfg.get("current_app", ""),
            "device_udid": cfg.get("device_udid"),
            "description": cfg.get("description"),
            "parameter": cfg.get("parameter", {}),
        })
    return result


def get_suite(name: str) -> Optional[dict]:
    for s in list_suites():
        if s["name"] == name:
            return s
    return None


def update_suite(name: str, patch: Dict[str, Any]) -> Optional[dict]:
    data = _load()
    items = data.get("items", {})
    if name not in items:
        return None
    cfg = items[name]
    if "enabled" in patch:
        cfg["enabled"] = patch["enabled"]
    if "current_app" in patch:
        cfg["current_app"] = patch["current_app"]
    if "device_udid" in patch:
        cfg["device_udid"] = patch["device_udid"]
    if "parameter" in patch and isinstance(patch["parameter"], dict):
        cfg.setdefault("parameter", {}).update(patch["parameter"])
    _save(data)
    return get_suite(name)