from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.application_analyzer import risk_summary


def make_report(device: dict[str, Any], packages: list[dict[str, Any]]) -> dict[str, Any]:
    analyzed = [row for row in packages if row.get("risk")]
    return {"application": "YaOS Debloater", "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "read-only", "device": device, "packages": packages,
            "analysis_summary": {"total_analyzed": len(analyzed), **risk_summary(analyzed),
                                 "unknown": sum(row.get("category") == "Unknown applications" for row in analyzed)},
            "limitations": ["Android does not expose reliable human-readable labels through the collected commands; package IDs are used as fallback.",
                            "Component declarations and process memory may be unavailable on some firmware builds.",
                            "Risk ratings are advisory, evidence-based, and do not imply that disabling a package is safe."]}


def export_report(path: str | Path, device: dict[str, Any], packages: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.write_text(json.dumps(make_report(device, packages), indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
