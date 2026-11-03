from __future__ import annotations

import shutil
import subprocess
import re
from dataclasses import dataclass


class ADBError(RuntimeError):
    """An ADB operation failed or timed out."""


@dataclass(frozen=True)
class ADBDevice:
    serial: str
    state: str
    details: str = ""


class ADBManager:
    """Timeout-bounded ADB wrapper with narrowly scoped package state operations."""

    def __init__(self, adb_path: str | None = None, timeout: int = 12):
        self.adb_path = adb_path or shutil.which("adb") or "adb"
        self.timeout = timeout

    def run(self, *args: str, serial: str | None = None, timeout: int | None = None,
            _state_change: bool = False) -> str:
        if args == ("devices", "-l"):
            pass
        elif len(args) == 2 and args[0] == "connect":
            pass
        elif len(args) == 2 and args[0] == "disconnect":
            pass
        elif args and args[0] == "shell" and serial and self._is_read_only_shell(args[1:]):
            pass
        elif (_state_change and serial and len(args) >= 3 and args[0] == "shell" and
              (args[1:4] == ("pm", "enable", args[-1]) and len(args) == 4 or
               args[1:5] == ("pm", "disable-user", "--user", "0") and len(args) == 6)):
            pass
        else:
            raise ADBError("Blocked ADB command: only diagnostics and confirmed single-package state changes are allowed.")
        command = [self.adb_path]
        if serial:
            command += ["-s", serial]
        command.extend(args)
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=timeout or self.timeout, check=False)
        except FileNotFoundError as exc:
            raise ADBError("ADB executable was not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise ADBError(f"ADB command timed out: {' '.join(args)}") from exc
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise ADBError(detail or f"ADB exited with status {result.returncode}")
        return result.stdout.strip()

    def devices(self) -> list[ADBDevice]:
        output = self.run("devices", "-l")
        found: list[ADBDevice] = []
        for line in output.splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 2:
                found.append(ADBDevice(fields[0], fields[1], " ".join(fields[2:])))
        return found

    def connect(self, host: str, port: int) -> str:
        if not host.strip() or not 1 <= int(port) <= 65535:
            raise ValueError("Enter a valid host and port (1–65535).")
        response = self.run("connect", f"{host.strip()}:{int(port)}", timeout=20)
        if any(token in response.casefold() for token in ("failed to connect", "cannot connect", "unable to connect")):
            raise ADBError(response)
        return response

    def disconnect(self, serial: str) -> str:
        if not serial:
            raise ValueError("Select a device first.")
        return self.run("disconnect", serial)

    def shell(self, serial: str, *args: str) -> str:
        return self.run("shell", *args, serial=serial)

    def change_package_state(self, serial: str, package: str, operation: str, *, confirmed: bool) -> str:
        if not confirmed or not re.fullmatch(r"[A-Za-z0-9_.]+", package):
            raise ADBError("Package state change requires explicit confirmation for one valid package.")
        if operation == "disable":
            return self.run("shell", "pm", "disable-user", "--user", "0", package,
                            serial=serial, _state_change=True)
        if operation == "enable":
            return self.run("shell", "pm", "enable", package, serial=serial, _state_change=True)
        raise ADBError("Unsupported package operation.")

    @staticmethod
    def _is_read_only_shell(args: tuple[str, ...]) -> bool:
        from core.hardware_research import COMMANDS
        if args in COMMANDS:
            return True
        if args in {('dumpsys', 'cpuinfo'), ('dumpsys', 'meminfo'),
                    ('dumpsys', 'activity', 'services'), ('ps', '-A', '-o', 'PID,NAME,RSS')}:
            return True
        if len(args) == 2 and args[0] == "getprop":
            return True
        if args == ("cat", "/proc/meminfo") or args == ("df", "/data"):
            return True
        if len(args) == 4 and args[:3] == ("pm", "list", "packages") and args[3] in {"-s", "-3", "-d", "-f"}:
            return True
        if args in {("pm", "list", "packages", "-d", "--user", "0"),
                    ("pm", "list", "packages", "-f", "--user", "0")}:
            return True
        if len(args) == 3 and args[:2] == ("pm", "path") and args[2].startswith("[") is False:
            return True
        if len(args) == 3 and args[:2] == ("dumpsys", "package"):
            return True
        if args == ("ps",) or args == ("ps", "-A"):
            return True
        return False
