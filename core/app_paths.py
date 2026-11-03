"""Bundle resources are immutable; user data belongs in Application Support."""
from pathlib import Path
import shutil
import sys


def data_dir():
    if getattr(sys, 'frozen', False):
        path = Path.home() / 'Library' / 'Application Support' / 'YaOS Debloater'
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path(__file__).resolve().parent.parent


def rules_path():
    source = Path(__file__).with_name('analysis_rules.json')
    if not getattr(sys, 'frozen', False): return source
    target = data_dir() / 'analysis_rules.json'
    if not target.exists(): shutil.copyfile(source, target)
    return target


def find_adb():
    if getattr(sys, 'frozen', False):
        bundled = Path(sys._MEIPASS) / 'bin' / 'adb'
        if bundled.is_file(): return str(bundled)
    return shutil.which('adb') or next((str(p) for p in (Path('/opt/homebrew/bin/adb'), Path('/usr/local/bin/adb')) if p.is_file()), None)
