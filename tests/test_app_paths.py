import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.app_paths import data_dir, find_adb

class BundlePathTests(unittest.TestCase):
    def test_bundle_uses_internal_adb_without_path(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'bin'/'adb';p.parent.mkdir();p.write_text('fixture')
            with patch('sys.frozen',True,create=True),patch('sys._MEIPASS',folder,create=True):
                self.assertEqual(find_adb(),str(p))

    def test_frozen_user_data_outside_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('sys.frozen',True,create=True),patch('pathlib.Path.home',return_value=Path(folder)):
                p=data_dir()
                self.assertEqual(p,Path(folder)/'Library/Application Support/YaOS Debloater')
                self.assertTrue(p.is_dir())

class EnglishInterfaceTests(unittest.TestCase):
    def test_builtin_ui_and_explanations_have_no_russian_literals(self):
        import re
        root=Path(__file__).resolve().parents[1]
        for folder in ('gui','core'):
            for source in (root/folder).glob('*.py'):
                self.assertIsNone(re.search('[\u0400-\u04ff]',source.read_text()),str(source))
