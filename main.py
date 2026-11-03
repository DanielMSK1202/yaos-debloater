"""YaOS Debloater desktop entry point."""

from __future__ import annotations

import argparse
import shutil
import sys
import logging
from core.app_paths import find_adb, data_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Android TV diagnostics and individually confirmed package recovery")
    parser.add_argument("--check", action="store_true", help="check runtime dependencies without opening the GUI")
    args = parser.parse_args()

    adb = find_adb()
    if not adb:
        print("ADB was not found. Install Android platform-tools and ensure adb is on PATH.", file=sys.stderr)
        return 2
    if args.check:
        try:
            import customtkinter  # noqa: F401
        except ImportError:
            print("CustomTkinter is missing. Install dependencies with: python3 -m pip install -r requirements.txt", file=sys.stderr)
            return 2
        try:
            import tkinter  # noqa: F401
        except ImportError as exc:
            print(f"Tk support is missing from this Python installation: {exc}", file=sys.stderr)
            return 2
        print(f"Runtime ready; ADB: {adb}")
        return 0

    try:
        import customtkinter  # noqa: F401
        import tkinter  # noqa: F401
    except ImportError as exc:
        print(f"GUI dependency unavailable: {exc}. Install requirements and use a Python build with Tk support.", file=sys.stderr)
        return 2

    from gui.main_window import YaOSApp

    if getattr(sys, "frozen", False):
        logging.basicConfig(filename=data_dir() / "yaos.log", level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
    try:
        app = YaOSApp(adb_path=adb)
        app.report_callback_exception = lambda kind, value, tb: logging.error("GUI callback failed", exc_info=(kind, value, tb))
        logging.info("YaOS GUI initialized; ADB=%s", adb)
        app.mainloop()
    except Exception:
        logging.exception("GUI initialization failed")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
