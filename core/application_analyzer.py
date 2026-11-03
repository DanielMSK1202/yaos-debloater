"""Explainable, read-only package assessment. Rules are advisory, never removal advice."""
from __future__ import annotations

import json
from pathlib import Path

from core.app_paths import rules_path

RULES_PATH = rules_path()


def load_rules(path: str | Path = RULES_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def analyze_package(package: dict, device: dict, rules: dict | None = None) -> dict:
    rules = rules if rules is not None else load_rules()
    name = str(package.get("package", ""))
    fingerprint = str(device.get("fingerprint", ""))
    model = str(device.get("model", ""))
    android = str(device.get("android_version", ""))
    category = "Unknown applications"
    risk, confidence = "HIGH", "low"
    evidence = ["No matching local compatibility rule; unknown packages remain protected."]
    reason = "Available evidence does not establish the package purpose."
    data_sources = ["ADB package list", "Local compatibility rules"]
    purpose = "Unknown. A package ID alone does not establish application functionality."
    necessity, necessity_reason = "unknown", "Insufficient evidence to determine application necessity confidently."
    profile_match = False
    dependencies_resolved = False
    for scope in rules.get("device_profiles", []):
        if scope.get("model") != model or scope.get("android_version") != android:
            continue
        expected = scope.get("fingerprint")
        if not expected or expected != fingerprint:
            continue
        rule = scope.get("packages", {}).get(name)
        if rule:
            profile_match = True
            dependencies_resolved = rule.get("dependencies_resolved") is True
            category, risk = rule["category"], rule["risk"]
            necessity = rule.get("necessity", "unknown")
            reason = rule["purpose"]
            purpose = rule["purpose"]
            necessity_reason = rule.get("necessity_reason", rule["purpose"])
            evidence = [f"Exact local rule for {model}, Android {android}, fingerprint {fingerprint}.",
                        *rule.get("evidence", [])]
            confidence = rule.get("confidence", "medium")
            break
    else:
        # Generic platform protections are intentionally narrow and do not imply safety of other packages.
        if package.get("system") and name in {"android", "com.android.systemui", "com.android.settings", "com.android.packageinstaller"}:
            category, risk, confidence = "Android system components", "CRITICAL", "high"
            reason = "Core Android or system interface component."
            evidence = ["Package is marked system by Android package manager.", "Package ID matches a known core Android component."]
            necessity, necessity_reason = "essential", "Android system component; it may be required by the OS or interface."
        elif package.get("system") and (name.startswith("com.android.") or name.startswith("android.")):
            category, risk, confidence = "Essential Android services", "HIGH", "medium"
            reason = "Android service; dependencies and boot impact are not fully established."
            evidence = ["Package is marked system by Android package manager.", "Android namespace match."]
            necessity, necessity_reason = "essential", "Android system service. Its dependencies may be important for TV functionality."
        elif package.get("third_party"):
            category, risk, confidence = "Third-party applications", "MEDIUM", "low"
            reason = "User-installed application; usage and dependencies are unknown."
            evidence = ["Package is marked third-party by Android package manager."]
        if "com.google." in name or name.startswith("com.google."):
            category = "Google applications"
        elif "yandex" in name.casefold():
            category = "Yandex applications"
        elif name.startswith(("com.artel.", "uz.artel.")):
            category = "Manufacturer applications"
    permissions = package.get("requested_permissions") or []
    services = package.get("services") or []
    process = package.get("process_memory_kb")
    background = bool(services) or bool(package.get("running_process"))
    if package.get("system"):
        data_sources.append("ADB pm list packages -s")
    if package.get("third_party"):
        data_sources.append("ADB pm list packages -3")
    if package.get("disabled") is not None:
        data_sources.append("ADB pm list packages -d")
    for key in ("requested_permissions", "activities", "services", "receivers"):
        if package.get(key) is not None:
            data_sources.append("ADB dumpsys package " + name)
            break
    return {
        **package, "category": category, "risk": risk, "risk_reason": reason,
        "appears_to_do": purpose,
        "necessity": necessity, "necessity_reason": necessity_reason,
        "profile_match": profile_match, "dependencies_resolved": dependencies_resolved,
        "evidence": evidence, "confidence": confidence,
        "potential_consequences": ("Disabling may disrupt boot, the system interface, networking or dependent services."
                                   if risk in {"CRITICAL", "HIGH"} else
                                   "Disabling may remove functionality or affect dependent applications; investigate the consequences first."),
        "data_sources": sorted(set(data_sources)),
        "background_activity": {"value": background, "basis": "declared services/process evidence"},
        "disable_impact": "Disabling may disrupt dependent features or startup; investigate dependencies first.",
        "investigation_recommended": risk != "CRITICAL" or category == "Unknown applications",
        "memory_measurement_kb": process,
        "memory_measurement_basis": "ADB process measurement" if process is not None else None,
        "requested_permissions": permissions,
    }


def analyze_packages(packages: list[dict], device: dict, rules: dict | None = None) -> list[dict]:
    return [analyze_package(package, device, rules) for package in packages]


def risk_summary(results: list[dict]) -> dict[str, int]:
    return {risk: sum(result.get("risk") == risk for result in results)
            for risk in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
