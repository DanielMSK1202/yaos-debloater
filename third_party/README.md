# Third-party software

The MIT license at the repository root covers original YaOS code, not third-party software.
The included notices retain their original terms. `scripts/collect_notices.py` gathers
notices from the installed build dependencies and platform-tools package.

The macOS bundle contains CPython, Tcl/Tk, CustomTkinter, darkdetect, ADB and runtime
libraries collected by PyInstaller. PyInstaller has a bootloader exception; see its
included COPYING notice. ADB is bundled unmodified apart from architecture selection
and local code signing by PyInstaller. Its platform-tools NOTICE includes upstream
license notices. No ADB keys are included.

Public source does not contain diagnostic captures, device files, personal preferences,
backups, firmware, LiteOS assets, or proprietary TV configuration declarations.

Roboto font files shipped by CustomTkinter retain their upstream Apache 2.0 license in `Roboto-LICENSE.txt`.
