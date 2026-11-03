"""All device mutations here use a fake ADB object; no TV commands are sent."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from core.adb_manager import ADBDevice, ADBManager, ADBError
from core.application_analyzer import analyze_package
from core.safe_debloater import SafeDebloater, eligibility

SERIAL = "192.168.0.103:5555"
PACKAGE = "org.example.video"
DEVICE = {"manufacturer": "ARTEL", "model": "ARTEL 32D1200B", "android_version": "9",
          "fingerprint": "artel/verified/build"}
RULES = {"device_profiles": [{"model": DEVICE["model"], "android_version": "9",
          "fingerprint": DEVICE["fingerprint"], "packages": {PACKAGE: {
              "category": "Third-party applications", "risk": "LOW", "necessity": "optional",
              "purpose": "Verified optional video client", "confidence": "high",
              "dependencies_resolved": True, "evidence": ["Manual dependency investigation"]}}}]}


class FakeADB:
    def __init__(self):
        self.device = dict(DEVICE)
        self.disabled = False
        self.installed = True
        self.fail_change = False
        self.changes = []

    def devices(self):
        return [ADBDevice(SERIAL, "device")]

    def shell(self, serial, *args):
        assert serial == SERIAL
        if args[:1] == ("getprop",):
            return {"ro.product.manufacturer": self.device["manufacturer"],
                    "ro.product.model": self.device["model"],
                    "ro.build.version.release": self.device["android_version"],
                    "ro.build.fingerprint": self.device["fingerprint"]}.get(args[1], "")
        if args == ("cat", "/proc/meminfo"): return "MemTotal: 900000 kB\nMemAvailable: 400000 kB"
        if args == ("df", "/data"): return ""
        if args == ("pm", "list", "packages", "-f", "--user", "0"):
            return f"package:/data/app/{PACKAGE}/base.apk={PACKAGE}" if self.installed else ""
        if args == ("pm", "list", "packages", "-d", "--user", "0"):
            return f"package:{PACKAGE}" if self.disabled and self.installed else ""
        if args == ("pm", "list", "packages", "-s"): return ""
        if args == ("pm", "list", "packages", "-3"):
            return f"package:{PACKAGE}" if self.installed else ""
        raise RuntimeError(f"Unexpected shell call: {args}")

    def change_package_state(self, serial, package, operation, *, confirmed):
        self.changes.append((serial, package, operation, confirmed))
        if self.fail_change: raise ADBError("Mock ADB failure")
        self.disabled = operation == "disable"


class SafeDebloaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.adb = FakeADB()
        self.service = SafeDebloater(self.adb, Path(self.tmp.name), RULES)
        self.package = analyze_package({"package": PACKAGE, "path": f"/data/app/{PACKAGE}/base.apk",
                                        "third_party": True, "disabled": False}, DEVICE, RULES)

    def test_critical_high_medium_unknown_and_essential_blocked(self):
        for changes in ({"risk": "CRITICAL"}, {"risk": "HIGH"}, {"risk": "MEDIUM"},
                        {"risk": "UNKNOWN"}, {"necessity": "unknown"}, {"necessity": "essential"}):
            with self.subTest(changes=changes):
                self.assertTrue(eligibility({**self.package, **changes}, "dont_need"))

    def test_dependency_preference_and_confidence_protection(self):
        self.assertTrue(eligibility({**self.package, "dependencies_resolved": False}, "dont_need"))
        self.assertTrue(eligibility(self.package, "keep"))
        self.assertTrue(eligibility({**self.package, "confidence": "medium"}, "dont_need"))

    def test_dry_run_has_no_mutation(self):
        plan = self.service.dry_run(SERIAL, self.package, "dont_need")
        self.assertTrue(plan["eligible"])
        self.assertEqual(self.adb.changes, [])

    def test_backup_contains_identity_state_and_empty_history(self):
        path = self.service.backup(SERIAL, self.package)
        record = json.loads(path.read_text())
        self.assertEqual(record["device"], DEVICE)
        self.assertFalse(record["original_disabled"])
        self.assertEqual(record["history"], [])

    def test_confirmation_required(self):
        with self.assertRaisesRegex(RuntimeError, "confirmation"):
            self.service.disable(SERIAL, self.package, "dont_need", confirmed_package="wrong")
        self.assertEqual(self.adb.changes, [])

    def test_disable_and_restore_are_verified_and_logged(self):
        path = self.service.disable(SERIAL, self.package, "dont_need", confirmed_package=PACKAGE)
        self.assertTrue(self.adb.disabled)
        self.assertEqual(json.loads(path.read_text())["history"][0]["result"], "verified_disabled")
        self.service.restore(SERIAL, path, confirmed_package=PACKAGE)
        self.assertFalse(self.adb.disabled)
        self.assertEqual(json.loads(path.read_text())["history"][-1]["result"], "verified_enabled")
        self.assertEqual(len(self.adb.changes), 2)
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.json"))), 2)

    def test_device_identity_mismatch_blocks_restore(self):
        path = self.service.disable(SERIAL, self.package, "dont_need", confirmed_package=PACKAGE)
        self.adb.device["fingerprint"] = "other/firmware"
        with self.assertRaisesRegex(RuntimeError, "differs"):
            self.service.restore(SERIAL, path, confirmed_package=PACKAGE)
        self.assertEqual(len(self.adb.changes), 1)

    def test_package_missing_and_changed_state_block_operation(self):
        self.adb.installed = False
        with self.assertRaisesRegex(RuntimeError, "absent"):
            self.service.dry_run(SERIAL, self.package, "dont_need")
        self.adb.installed = True
        self.adb.disabled = True
        self.assertFalse(self.service.dry_run(SERIAL, self.package, "dont_need")["eligible"])

    def test_forged_analysis_and_profile_mismatch_block(self):
        forged = {**self.package, "risk": "LOW", "profile_match": True}
        self.adb.device["fingerprint"] = "other/firmware"
        self.assertFalse(self.service.dry_run(SERIAL, forged, "dont_need")["eligible"])
        self.assertEqual(self.adb.changes, [])

    def test_failed_adb_change_records_verified_original_state(self):
        self.adb.fail_change = True
        with self.assertRaisesRegex(RuntimeError, "Verified package state: enabled"):
            self.service.disable(SERIAL, self.package, "dont_need", confirmed_package=PACKAGE)
        records = list(Path(self.tmp.name).glob("*.json"))
        self.assertEqual(len(records), 1)
        entry = json.loads(records[0].read_text())["history"][0]
        self.assertEqual(entry["result"], "failed")
        self.assertFalse(entry["state_after"])

    def test_read_only_shell_blocks_unconfirmed_state_change(self):
        manager = ADBManager(adb_path="adb")
        with self.assertRaises(ADBError):
            manager.shell(SERIAL, "pm", "disable-user", "--user", "0", PACKAGE)
        with self.assertRaises(ADBError):
            manager.change_package_state(SERIAL, PACKAGE, "disable", confirmed=False)

    def test_confirmed_commands_are_exactly_one_package(self):
        manager = ADBManager(adb_path="adb")
        with patch("core.adb_manager.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="ok", stderr="")) as run:
            manager.change_package_state(SERIAL, PACKAGE, "disable", confirmed=True)
            self.assertEqual(run.call_args.args[0], ["adb", "-s", SERIAL, "shell", "pm", "disable-user", "--user", "0", PACKAGE])
            manager.change_package_state(SERIAL, PACKAGE, "enable", confirmed=True)
            self.assertEqual(run.call_args.args[0], ["adb", "-s", SERIAL, "shell", "pm", "enable", PACKAGE])

    def test_restore_requires_backup_directory(self):
        path = self.service.disable(SERIAL, self.package, "dont_need", confirmed_package=PACKAGE)
        with tempfile.TemporaryDirectory() as folder:
            elsewhere = Path(folder) / path.name
            elsewhere.write_bytes(path.read_bytes())
            with self.assertRaisesRegex(RuntimeError, "backup"):
                self.service.restore(SERIAL, elsewhere, confirmed_package=PACKAGE)
        self.assertEqual(len(self.adb.changes), 1)


if __name__ == "__main__":
    unittest.main()
