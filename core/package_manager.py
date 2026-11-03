from __future__ import annotations

import re
from typing import Callable

from core.adb_manager import ADBManager


def parse_package_list(text: str, *, system: set[str] | None = None,
                       third_party: set[str] | None = None,
                       disabled: set[str] | None = None) -> list[dict]:
    """Parse Android pm list packages output, merging duplicate package records."""
    system, third_party, disabled = system or set(), third_party or set(), disabled or set()
    records: dict[str, dict] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        item = line[8:]
        path, sep, name = item.rpartition("=")
        if not sep:
            name, path = item, ""
        name = name.strip()
        if not name:
            continue
        records.setdefault(name, {"package": name, "application": name, "system": name in system,
                                 "third_party": name in third_party, "disabled": name in disabled,
                                 "path": path.strip(), "version_name": None, "version_code": None})
        row = records[name]
        row["system"] |= name in system
        row["third_party"] |= name in third_party
        row["disabled"] |= name in disabled
        if path and not row["path"]:
            row["path"] = path.strip()
    return sorted(records.values(), key=lambda row: row["package"].casefold())


def _names(output: str) -> set[str]:
    return {line.strip()[8:] for line in output.splitlines()
            if line.strip().startswith("package:") and line.strip()[8:]}


def _parse_version(output: str) -> tuple[str | None, str | None]:
    name = re.search(r"\bversionName=([^\s]+)", output)
    code = re.search(r"\bversionCode=(\d+)", output)
    return (name.group(1) if name else None, code.group(1) if code else None)


def parse_package_details(output: str, package_name: str) -> dict:
    """Extract details that Android's package-manager dump exposes on API 28."""
    version_name, version_code = _parse_version(output)
    permissions: list[str] | None = None
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "requested permissions:":
            permissions = []
            for candidate in lines[index + 1:]:
                value = candidate.strip()
                if not value or value.endswith(":"):
                    break
                if value.startswith("android.permission."):
                    permissions.append(value.split()[0])
            break
    components: dict[str, list[str] | None] = {"activities": None, "services": None, "receivers": None}
    patterns = {
        "activities": r"Activity\s*\{[^}]*?\s(" + re.escape(package_name) + r"/[^\s}]+)",
        "services": r"Service\s*\{[^}]*?\s(" + re.escape(package_name) + r"/[^\s}]+)",
        "receivers": r"Receiver\s*\{[^}]*?\s(" + re.escape(package_name) + r"/[^\s}]+)",
    }
    for key, pattern in patterns.items():
        found = sorted(set(re.findall(pattern, output)))
        if found:
            components[key] = found
    section_map = {"Activities:": "activities", "Services:": "services", "Receivers:": "receivers"}
    active = None
    for line in lines:
        stripped = line.strip()
        if stripped in section_map:
            active = section_map[stripped]
            if components[active] is None:
                components[active] = []
            continue
        if stripped.endswith(":"):
            active = None
            continue
        if active and "/" in stripped and package_name in stripped:
            components[active].append(stripped.split()[0])
    for key in components:
        if components[key] is not None:
            components[key] = sorted(set(components[key]))
    return {"version_name": version_name, "version_code": version_code,
            "requested_permissions": permissions, **components,
            "metadata_available": bool(version_name or version_code or permissions is not None or any(components.values()))}


def scan_packages(adb: ADBManager, serial: str,
                  progress: Callable[[int, int, str], None] | None = None) -> list[dict]:
    """Read Android 9 package lists, paths, and versions. Errors are retained per scan."""
    errors: list[str] = []
    outputs: dict[str, str] = {}
    for flag in ("-f", "-s", "-3", "-d"):
        try:
            outputs[flag] = adb.shell(serial, "pm", "list", "packages", flag)
        except Exception as exc:
            errors.append(f"pm list packages {flag}: {exc}")
    if "-f" not in outputs and "-s" not in outputs and "-3" not in outputs:
        raise RuntimeError("Package enumeration failed: " + "; ".join(errors))
    all_output = "\n".join(outputs.get(flag, "") for flag in ("-f", "-s", "-3", "-d"))
    rows = parse_package_list(all_output, system=_names(outputs.get("-s", "")),
                              third_party=_names(outputs.get("-3", "")),
                              disabled=_names(outputs.get("-d", "")))
    try:
        processes = parse_process_list(adb.shell(serial, "ps"))
    except Exception:
        processes = []
    total = len(rows)
    for index, row in enumerate(rows, 1):
        name = row["package"]
        matched = [proc for proc in processes if proc["name"] == name or proc["name"].startswith(name + ":")]
        row["running_processes"] = matched if processes else None
        row["running_process"] = bool(matched) if processes else None
        row["process_memory_kb"] = sum(proc["rss_kb"] for proc in matched if proc.get("rss_kb") is not None) or None
        if not row["path"]:
            try:
                path_output = adb.shell(serial, "pm", "path", name)
                row["path"] = next((line[8:].strip() for line in path_output.splitlines()
                                     if line.startswith("package:")), "")
            except Exception:
                pass
        try:
            details = parse_package_details(adb.shell(serial, "dumpsys", "package", name), name)
            row.update(details)
        except Exception as exc:
            row.update({"requested_permissions": None, "activities": None, "services": None,
                        "receivers": None, "metadata_error": str(exc)})
        row.setdefault("application_label_source", "package identifier; Android label unavailable")
        row.setdefault("process_memory_kb", None)
        row.setdefault("running_process", None)
        if progress and (index == total or index % 5 == 0):
            progress(index, total, name)
    if errors:
        for row in rows:
            row["scan_warnings"] = errors
    return rows


def parse_process_list(output: str) -> list[dict]:
    lines = output.splitlines()
    if not lines:
        return []
    header = lines[0].split()
    name_i = next((i for i, item in enumerate(header) if item.upper() in {"NAME", "CMD", "COMMAND"}), len(header) - 1)
    rss_i = next((i for i, item in enumerate(header) if item.upper() in {"RSS", "RES"}), None)
    result = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) <= name_i:
            continue
        rss = None
        if rss_i is not None and len(fields) > rss_i:
            try:
                rss = int(fields[rss_i])
            except ValueError:
                pass
        result.append({"name": fields[name_i], "rss_kb": rss})
    return result
