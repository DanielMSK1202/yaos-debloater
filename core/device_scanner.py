from __future__ import annotations

import re
from typing import Any

from core.adb_manager import ADBManager


def parse_meminfo(text: str) -> dict[str, int | None]:
    values: dict[str, int | None] = {"total_kb": None, "available_kb": None}
    for line in text.splitlines():
        match = re.match(r"\s*(MemTotal|MemAvailable|MemFree):\s*(\d+)\s*kB", line, re.I)
        if match:
            key = "total_kb" if match.group(1).lower() == "memtotal" else "available_kb"
            if key == "available_kb" or values[key] is None:
                values[key] = int(match.group(2))
    return values


def parse_df(text: str) -> dict[str, Any]:
    """Parse common Android toolbox/toybox df output; choose /data when present."""
    rows = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 5:
            continue
        # Android versions differ in whether the filesystem column is first.
        nums = [(i, int(field.rstrip("%"))) for i, field in enumerate(fields) if field.rstrip("%").isdigit()]
        if len(nums) < 3:
            continue
        percent = next((n for i, n in nums if fields[i].endswith("%")), None)
        if percent is None:
            percent = nums[3][1] if len(nums) > 3 else None
        mount = fields[-1]
        if mount == "/data" or mount.startswith("/data/"):
            rows.append({"filesystem": fields[0], "size": nums[0][1], "used": nums[1][1],
                         "available": nums[2][1], "used_percent": percent, "mount": mount})
    return rows[0] if rows else {}


def _prop(adb: ADBManager, serial: str, name: str) -> str:
    try:
        return adb.shell(serial, "getprop", name).strip()
    except Exception:
        return ""


def scan_device(adb: ADBManager, serial: str) -> dict[str, Any]:
    """Collect identity, memory and /data capacity using read-only shell commands."""
    props = {
        "manufacturer": _prop(adb, serial, "ro.product.manufacturer"),
        "model": _prop(adb, serial, "ro.product.model"),
        "android_version": _prop(adb, serial, "ro.build.version.release"),
        "sdk": _prop(adb, serial, "ro.build.version.sdk"),
        "device": _prop(adb, serial, "ro.product.device"),
        "fingerprint": _prop(adb, serial, "ro.build.fingerprint"),
    }
    try:
        memory = parse_meminfo(adb.shell(serial, "cat", "/proc/meminfo"))
    except Exception as exc:
        memory = {"error": str(exc)}
    try:
        storage = parse_df(adb.shell(serial, "df", "/data"))
    except Exception as exc:
        storage = {"error": str(exc)}
    return {"serial": serial, **props, "memory": memory, "storage": storage}
