"""Single-package, fail-closed state changes with local state backup and verification."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.adb_manager import ADBManager
from core.application_analyzer import analyze_package, load_rules
from core.device_scanner import scan_device

from core.app_paths import data_dir

BACKUP_DIR = data_dir() / "backups"
IDENTITY = ("manufacturer", "model", "android_version", "fingerprint")


def eligibility(package: dict, preference: str | None) -> list[str]:
    reasons = []
    if package.get("risk") != "LOW": reasons.append("Only LOW risk permits further verification.")
    if package.get("necessity") not in {"optional", "potentially_unnecessary"}:
        reasons.append("The application has not been established as optional.")
    if package.get("necessity") == "essential": reasons.append("Essential applications are protected.")
    if preference != "dont_need": reasons.append("The user has not marked this application as unneeded.")
    if not package.get("profile_match"): reasons.append("No rule matches the exact model, Android version and firmware.")
    if not package.get("dependencies_resolved"): reasons.append("Dependencies have not been individually resolved.")
    if package.get("confidence") != "high": reasons.append("Analysis confidence is not high enough.")
    if package.get("disabled"): reasons.append("The application is already disabled.")
    return reasons


class SafeDebloater:
    def __init__(self, adb: ADBManager, backup_dir: Path = BACKUP_DIR, rules: dict | None = None):
        self.adb, self.backup_dir = adb, backup_dir
        self.rules = rules if rules is not None else load_rules()

    def _live(self, serial: str, package: str) -> tuple[dict, bool, dict]:
        if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
            raise ValueError("Invalid package identifier")
        if not any(d.serial == serial and d.state == "device" for d in self.adb.devices()):
            raise RuntimeError("ADB device is not authorized and connected")
        device = scan_device(self.adb, serial)
        if any(not device.get(key) for key in IDENTITY):
            raise RuntimeError("Incomplete device identity; operation blocked")
        installed = self.adb.shell(serial, "pm", "list", "packages", "-f", "--user", "0")
        paths = {line.partition("=")[2]: line.partition("=")[0].removeprefix("package:")
                 for line in installed.splitlines() if line.startswith("package:") and "=" in line}
        names = set(paths)
        if package not in names:
            raise RuntimeError("Package is absent for user 0")
        disabled = self.adb.shell(serial, "pm", "list", "packages", "-d", "--user", "0")
        disabled_names = {line.removeprefix("package:") for line in disabled.splitlines() if line.startswith("package:")}
        system = self.adb.shell(serial, "pm", "list", "packages", "-s")
        third_party = self.adb.shell(serial, "pm", "list", "packages", "-3")
        system_names = {line.removeprefix("package:") for line in system.splitlines() if line.startswith("package:")}
        third_party_names = {line.removeprefix("package:") for line in third_party.splitlines() if line.startswith("package:")}
        live_package = {"package": package, "path": paths[package], "system": package in system_names,
                        "third_party": package in third_party_names, "disabled": package in disabled_names}
        return device, package in disabled_names, live_package

    @staticmethod
    def _same_device(expected: dict, actual: dict) -> bool:
        return all(expected.get(key) and expected.get(key) == actual.get(key) for key in IDENTITY)

    def dry_run(self, serial: str, package: dict, preference: str | None) -> dict:
        reasons = eligibility(package, preference)
        device, disabled, live_package = self._live(serial, package["package"])
        fresh_analysis = analyze_package(live_package, device, self.rules)
        reasons.extend(eligibility(fresh_analysis, preference))
        if not live_package["system"] and not live_package["third_party"]:
            reasons.append("Android did not confirm the package type; disabling is blocked.")
        if package.get("path") != live_package["path"]:
            reasons.append("The package path changed since the scan; refresh the inventory.")
        if disabled: reasons.append("Live TV state: already disabled.")
        if package.get("disabled") != disabled: reasons.append("The state changed since the scan; refresh the inventory.")
        return {"eligible": not reasons, "reasons": reasons, "device": device,
                "package": package["package"], "original_disabled": disabled}

    def backup(self, serial: str, package: dict) -> Path:
        device, disabled, _ = self._live(serial, package["package"])
        record = {"schema_version": 1, "timestamp": datetime.now(timezone.utc).isoformat(),
                  "device": {key: device[key] for key in IDENTITY}, "serial": serial,
                  "package": package["package"], "original_disabled": disabled,
                  "history": [], "note": "Package-state backup only; application data is not backed up."}
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        target = self.backup_dir / f"{package['package']}-{uuid.uuid4().hex}.json"
        target.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target

    def disable(self, serial: str, package: dict, preference: str | None,
                *, confirmed_package: str) -> Path:
        if confirmed_package != package.get("package"):
            raise RuntimeError("Exact package confirmation is required")
        plan = self.dry_run(serial, package, preference)
        if not plan["eligible"]:
            raise RuntimeError("Operation blocked: " + "; ".join(plan["reasons"]))
        backup_path = self.backup(serial, package)
        record = json.loads(backup_path.read_text(encoding="utf-8"))
        current_device, current_disabled, _ = self._live(serial, package["package"])
        if not self._same_device(record["device"], plan["device"]) or not self._same_device(record["device"], current_device) or record["original_disabled"] or current_disabled:
            raise RuntimeError("Backup state does not match the verified device")
        try:
            self.adb.change_package_state(serial, package["package"], "disable", confirmed=True)
            _, now_disabled, _ = self._live(serial, package["package"])
            if not now_disabled: raise RuntimeError("ADB returned but package is still enabled")
            outcome = "verified_disabled"
        except Exception as exc:
            try: _, current, _ = self._live(serial, package["package"])
            except Exception: current = None
            record["history"].append({"time": datetime.now(timezone.utc).isoformat(),
                                      "operation": "disable", "result": "failed", "state_after": current,
                                      "error": str(exc)})
            backup_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            state_text = "disabled" if current is True else "enabled" if current is False else "unavailable"
            raise RuntimeError(f"Disable failed: {exc}. Verified package state: {state_text}. Backup: {backup_path.name}") from exc
        record["history"].append({"time": datetime.now(timezone.utc).isoformat(),
                                  "operation": "disable", "result": outcome})
        backup_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return backup_path

    def restore(self, serial: str, backup_path: Path, *, confirmed_package: str) -> None:
        backup_path = Path(backup_path)
        if backup_path.resolve().parent != self.backup_dir.resolve():
            raise RuntimeError("Restore file must be an application package-state backup")
        record = json.loads(backup_path.read_text(encoding="utf-8"))
        package = record["package"]
        if confirmed_package != package or record["original_disabled"] or record.get("serial") != serial:
            raise RuntimeError("Restore confirmation or original state is invalid")
        device, disabled, _ = self._live(serial, package)
        if not self._same_device(record["device"], device):
            raise RuntimeError("Device model, Android version, or firmware fingerprint differs from backup")
        if not disabled:
            raise RuntimeError("Package is already enabled; no restore needed")
        pre_restore_path = self.backup(serial, {"package": package})
        pre_restore = json.loads(pre_restore_path.read_text(encoding="utf-8"))
        if not self._same_device(record["device"], pre_restore["device"]) or not pre_restore["original_disabled"]:
            raise RuntimeError("Pre-restore backup does not match the verified device state")
        try:
            self.adb.change_package_state(serial, package, "enable", confirmed=True)
            _, still_disabled, _ = self._live(serial, package)
            if still_disabled: raise RuntimeError("Restore command did not enable the package")
            record["history"].append({"time": datetime.now(timezone.utc).isoformat(),
                                      "operation": "enable", "result": "verified_enabled",
                                      "pre_restore_backup": pre_restore_path.name})
        except Exception as exc:
            try: _, state, _ = self._live(serial, package)
            except Exception: state = None
            record["history"].append({"time": datetime.now(timezone.utc).isoformat(),
                                      "operation": "enable", "result": "failed", "state_after": state,
                                      "error": str(exc), "pre_restore_backup": pre_restore_path.name})
            state_text = "disabled" if state is True else "enabled" if state is False else "unavailable"
            raise RuntimeError(f"Restore failed: {exc}. Verified package state: {state_text}. Backup: {pre_restore_path.name}") from exc
        finally:
            backup_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
