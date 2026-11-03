import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.adb_manager import ADBDevice, ADBManager
from core.device_scanner import parse_df, parse_meminfo
from core.package_manager import parse_package_list, scan_packages
from core.report_manager import export_report
from gui.main_window import YaOSApp


class ParserTests(unittest.TestCase):
    def test_parse_package_output_paths_and_duplicate_merge(self):
        rows = parse_package_list(
            "package:/system/app/Settings/Settings.apk=com.android.settings\n"
            "package:com.android.settings\npackage:/data/app/a/base.apk=com.example.app",
            system={"com.android.settings"}, third_party={"com.example.app"},
            disabled={"com.example.app"})
        self.assertEqual(len(rows), 2)
        system = next(row for row in rows if row["package"] == "com.android.settings")
        app = next(row for row in rows if row["package"] == "com.example.app")
        self.assertEqual(system["path"], "/system/app/Settings/Settings.apk")
        self.assertTrue(system["system"])
        self.assertTrue(app["third_party"])
        self.assertTrue(app["disabled"])

    def test_package_scan_collects_android9_metadata_and_partial_warnings(self):
        manager = ADBManager("adb")
        def shell(_serial, *args):
            if args == ("pm", "list", "packages", "-f"):
                return "package:/system/app/One/One.apk=com.one\npackage:com.two"
            if args == ("pm", "list", "packages", "-s"):
                return "package:com.one"
            if args == ("pm", "list", "packages", "-3"):
                return "package:com.two"
            if args == ("pm", "list", "packages", "-d"):
                raise RuntimeError("flag unsupported")
            if args == ("pm", "path", "com.two"):
                return "package:/data/app/com.two/base.apk"
            if args[:2] == ("dumpsys", "package"):
                return "versionCode=12 minSdk=21\nversionName=2.4"
            raise AssertionError(args)
        with patch.object(manager, "shell", side_effect=shell):
            rows = scan_packages(manager, "tv")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["path"], "/system/app/One/One.apk")
        self.assertEqual(rows[1]["path"], "/data/app/com.two/base.apk")
        self.assertEqual(rows[1]["version_name"], "2.4")
        self.assertTrue(rows[0]["scan_warnings"])

    def test_meminfo(self):
        parsed = parse_meminfo("MemTotal: 927000 kB\nMemFree: 2000 kB\nMemAvailable: 312000 kB")
        self.assertEqual(parsed, {"total_kb": 927000, "available_kb": 312000})

    def test_df_data_mount(self):
        parsed = parse_df("Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-5 3670016 1200000 2470016 33% /data")
        self.assertEqual(parsed["mount"], "/data")
        self.assertEqual(parsed["used_percent"], 33)
        self.assertEqual(parsed["size"], 3670016)

    def test_devices(self):
        manager = ADBManager("adb")
        with patch.object(manager, "run", return_value="List of devices attached\n192.168.0.103:5555 device product:x model:TV"):
            self.assertEqual(manager.devices(), [ADBDevice("192.168.0.103:5555", "device", "product:x model:TV")])

    def test_write_commands_are_blocked(self):
        manager = ADBManager("adb")
        with self.assertRaisesRegex(Exception, "Blocked ADB command"):
            manager.run("shell", "pm", "uninstall", "com.example.app", serial="tv")
        with self.assertRaisesRegex(Exception, "Blocked ADB command"):
            manager.shell("tv", "su", "-c", "id")

    def test_connect_response_reports_failed_endpoint(self):
        manager = ADBManager("adb")
        with patch.object(manager, "run", return_value="failed to connect to 192.168.0.103:5555"):
            with self.assertRaisesRegex(Exception, "failed to connect"):
                manager.connect("192.168.0.103", 5555)

    def test_connect_response_accepts_connected_endpoint(self):
        manager = ADBManager("adb")
        with patch.object(manager, "run", return_value="connected to 192.168.0.103:5555"):
            self.assertIn("connected", manager.connect("192.168.0.103", 5555))


class DeviceStateTests(unittest.TestCase):
    @staticmethod
    def app_harness():
        app = SimpleNamespace(
            devices=[], selected_serial=None, device_data={"old": True}, package_data=[{"old": True}],
            device_menu=MagicMock(), scan_button=MagicMock(), disconnect_button=MagicMock(),
            export_button=MagicMock(), apps=SimpleNamespace(set_packages=MagicMock()),
            safe=SimpleNamespace(set_packages=MagicMock()),
            dashboard=SimpleNamespace(show_disconnected=MagicMock(), show_connected=MagicMock()),
            status=MagicMock(), _pending_auto_scan=False, _connect_checks=0,
            after=MagicMock(), refresh_devices=MagicMock(), scan=MagicMock(),
        )
        return app

    def test_disconnected_state_shows_empty_dashboard_and_disables_scan(self):
        app = self.app_harness()
        YaOSApp._devices_updated(app, [])
        app.dashboard.show_disconnected.assert_called_once_with()
        app.scan_button.configure.assert_called_with(state="disabled")
        app.device_menu.set.assert_called_with("No device connected")
        self.assertEqual(app.device_data, {})
        self.assertEqual(app.package_data, [])

    def test_connected_state_enables_scan_and_auto_scans(self):
        app = self.app_harness()
        app._pending_auto_scan = True
        device = ADBDevice("192.168.0.103:5555", "device")
        YaOSApp._devices_updated(app, [device])
        app.dashboard.show_connected.assert_called_once_with(device.serial)
        app.scan_button.configure.assert_called_with(state="normal")
        app.disconnect_button.configure.assert_called_with(state="normal")
        app.scan.assert_called_once_with()

    def test_package_classification_and_unsupported_flag(self):
        manager = ADBManager("adb")
        def shell(_serial, *args):
            if "-d" in args:
                raise RuntimeError("unsupported")
            return "package:com.example.app\n" if "-3" in args else "package:com.android.system\n"
        with patch.object(manager, "shell", side_effect=shell):
            packages = scan_packages(manager, "tv")
        self.assertEqual(len(packages), 2)
        self.assertTrue(next(p for p in packages if p["package"] == "com.example.app")["third_party"])

    def test_json_export(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            export_report(output, {"serial": "tv"}, [])
            data = json.loads(output.read_text())
            self.assertEqual(data["mode"], "read-only")
            self.assertEqual(data["device"]["serial"], "tv")


if __name__ == "__main__":
    unittest.main()
