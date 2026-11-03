"""Parser fixtures model the captured Android 9 dumpsys package output format."""
import json
import tempfile
import unittest
from pathlib import Path

from core.application_analyzer import analyze_package, analyze_packages, risk_summary
from core.package_manager import parse_package_details, parse_process_list
from core.report_manager import export_report
from core.user_preferences import load_preferences, save_preference


DUMPSYS_FIXTURE = """Package [com.example.tv] (123):
  versionCode=27 minSdk=23
  versionName=1.4.2
  requested permissions:
    android.permission.INTERNET
    android.permission.ACCESS_NETWORK_STATE
  Activities:
    com.example.tv/.MainActivity
  Services:
    com.example.tv/.SyncService
  Receivers:
    com.example.tv/.BootReceiver
"""


class AnalyzerTests(unittest.TestCase):
    def test_permissions_and_components_parse(self):
        details = parse_package_details(DUMPSYS_FIXTURE, "com.example.tv")
        self.assertEqual(details["requested_permissions"], ["android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE"])
        self.assertEqual(details["activities"], ["com.example.tv/.MainActivity"])
        self.assertEqual(details["services"], ["com.example.tv/.SyncService"])
        self.assertEqual(details["receivers"], ["com.example.tv/.BootReceiver"])

    def test_process_memory_parse(self):
        rows = parse_process_list("USER PID PPID VSZ RSS WCHAN ADDR S NAME\nsystem 42 1 10 2048 0 0 S com.example.tv")
        self.assertEqual(rows[0], {"name": "com.example.tv", "rss_kb": 2048})

    def test_missing_metadata_remains_unavailable(self):
        details = parse_package_details("Package [mystery]", "mystery")
        self.assertIsNone(details["requested_permissions"])
        self.assertIsNone(details["activities"])
        self.assertIsNone(details["services"])
        self.assertIsNone(details["receivers"])

    def test_unknown_package_is_high_and_reviewed(self):
        result = analyze_package({"package": "vendor.mystery", "system": False}, {})
        self.assertEqual(result["risk"], "HIGH")
        self.assertEqual(result["necessity"], "unknown")
        self.assertTrue(result["investigation_recommended"])
        self.assertTrue(result["evidence"])

    def test_third_party_is_not_automatically_optional_or_unnecessary(self):
        result = analyze_package({"package": "org.example.video", "third_party": True}, {})
        self.assertEqual(result["risk"], "MEDIUM")
        self.assertEqual(result["necessity"], "unknown")

    def test_user_preference_persists_separately(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preferences.json"
            save_preference("org.example.video", "dont_need", path)
            self.assertEqual(load_preferences(path), {"org.example.video": "dont_need"})

    def test_critical_rule_protects_known_platform_component(self):
        result = analyze_package({"package": "android", "system": True}, {})
        self.assertEqual(result["risk"], "CRITICAL")
        self.assertIn("Android", result["risk_reason"])

    def test_device_rule_requires_exact_model_android_and_fingerprint(self):
        rules = {"device_profiles": [{"model": "ARTEL 32D1200B", "android_version": "9",
                  "fingerprint": "artel/build/one", "packages": {"vendor.app": {
                      "category": "Manufacturer applications", "risk": "LOW", "purpose": "TV utility",
                      "confidence": "medium", "evidence": ["Local rule"]}}}]}
        package = {"package": "vendor.app", "third_party": True}
        exact = analyze_package(package, {"model": "ARTEL 32D1200B", "android_version": "9",
                                         "fingerprint": "artel/build/one"}, rules)
        mismatch = analyze_package(package, {"model": "Other TV", "android_version": "9",
                                            "fingerprint": "artel/build/one"}, rules)
        self.assertEqual(exact["risk"], "LOW")
        self.assertEqual(mismatch["risk"], "MEDIUM")

    def test_json_export_includes_analysis_and_limitations(self):
        results = analyze_packages([{"package": "mystery.pkg"}], {"model": "TV"})
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "report.json"
            export_report(target, {"fingerprint": "fp"}, results)
            report = json.loads(target.read_text())
        self.assertEqual(report["analysis_summary"]["total_analyzed"], 1)
        self.assertEqual(report["packages"][0]["risk"], "HIGH")
        self.assertTrue(report["limitations"])

    def test_risk_summary_counts_all_buckets(self):
        self.assertEqual(risk_summary([{"risk": "LOW"}, {"risk": "HIGH"}]),
                         {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 0, "LOW": 1})


if __name__ == "__main__":
    unittest.main()
