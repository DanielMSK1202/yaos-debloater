# YaOS Debloater

A macOS desktop app for inspecting Android Smart TVs over ADB, understanding installed
applications, collecting performance measurements, and reviewing individually confirmed
package state changes. The interface and built-in analysis explanations are in English.

## What works

- Authorized-device discovery and IP/port connection management.
- Real device, RAM, storage, package, permission and component scanning.
- Searchable application inventory, necessity assessment and separate disable risk.
- Local user preferences, evidence and analysis confidence.
- Background CPU/RAM/RSS/PSS sessions, charts, JSON export and session comparison.
- Fail-closed single-package disable review, state backup and restore.

Compatibility has been exercised on an ARTEL 32D1200B running Android 9/API 28.
Support for other firmware is not guaranteed. Unsupported telemetry is shown as
unavailable. Labels and device-returned text retain their original names/language.

## Safety

Scanning and performance collection are read-only. Safe Debloater is a separate,
explicitly confirmed operation. CRITICAL, HIGH, MEDIUM, unknown and essential
applications are blocked. LOW risk alone does not grant approval: an exact device
profile, high confidence, individually resolved dependencies, live package checks
and user preference are also required. The default rule database approves no candidates.

Each disable requires a dry run, a local state backup, typing the exact package ID,
and a confirmation dialog. Only `pm disable-user --user 0 PACKAGE` and restoration
with `pm enable PACKAGE` are allowed. There is no bulk disable, uninstall, app-data
clearing, root, firmware flashing or process killing.

**A package-state backup is not a backup of application data or firmware.**

## macOS download

Download the Apple Silicon `.dmg` from GitHub Releases when a release is published.
Open it and drag **YaOS Debloater.app** to **Applications**. The app includes Python,
Tcl/Tk and ADB; no terminal or Homebrew is required to run it.

The build is signed locally (ad hoc), not notarized by Apple. Gatekeeper behavior
on another Mac has not been validated. Signing and notarization require a separate
Apple Developer distribution setup. Do not disable Gatekeeper globally.

Local data: `~/Library/Application Support/YaOS Debloater/` (rules, preferences,
backups and `yaos.log`). No private ADB keys are bundled. Android platform-tools
uses the normal per-user ADB authentication state.

## Run from source

Use a Python 3 installation with Tk support, then:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --check
.venv/bin/python main.py
```

Source mode requires Android platform-tools (`adb`) on PATH or at its standard
Homebrew installation location. Connect the Mac and TV to the same network and
approve ADB authorization on the TV. Never expose network ADB to the internet.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests use synthetic, labeled fixtures and mocked ADB; they do not change a real TV.

## Build the macOS app and DMG

On an Apple Silicon Mac, install a Tk-enabled Python and Android platform-tools.
The verified local build used Homebrew Python 3.14 with `python-tk@3.14`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
bash scripts/build_macos.sh
```

Outputs: `dist/YaOS Debloater.app`, `dist/YaOS-Debloater-0.6.1-macos-arm64.dmg`
and `dist/SHA256SUMS.txt`. The `.app` is the actual application bundle; the `.dmg`
is a compressed disk image for downloading and drag-to-install distribution.
The build script collects third-party notices, runs tests, bundles the app,
verifies its local signature and dependency check, and creates the DMG.
The GitHub Actions workflow builds artifacts on tags or manual dispatch; hosted
CI has not been executed until this repository is published.

## Performance interpretation

Sampling pauses for five seconds after each completed reading. Detailed process
PSS and service snapshots are collected every sixth reading. RSS counts shared
resident pages; PSS apportions them. Cached RAM is reclaimable, not wasted.
CPU uses Android-reported windows, which can overlap or initially be stale.
Findings flag repeated CPU ≥80%, available RAM below 10%, process CPU ≥20% for
one PID/name across three observations, RSS ≥10% of total RAM, or storage ≥90% used.
These thresholds are investigation prompts, not benchmark scores or proof of a cause.
Session comparisons report measurements without promising improvements.

## Publishing and license

See [PUBLISHING.md](PUBLISHING.md) for account setup, source publishing and release
upload instructions. Original YaOS code is [MIT licensed](LICENSE). Third-party
components retain their own licenses; see [third_party](third_party/).
Diagnostic captures, personal data, firmware material and the separate LiteOS work
are excluded from the public repository.
