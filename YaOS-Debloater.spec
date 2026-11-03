# Build on macOS: .venv/bin/pyinstaller --clean --noconfirm YaOS-Debloater.spec
from pathlib import Path
import shutil
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
adb = shutil.which('adb')
if not adb:
    raise RuntimeError('Install platform-tools before building: ADB is included in the app.')
ctk_datas, ctk_bins, ctk_hiddenimports = collect_all('customtkinter')
a = Analysis([str(root / 'main.py')], pathex=[str(root)],
    binaries=ctk_bins + [(adb, 'bin')],
    datas=ctk_datas + [(str(root / 'core/analysis_rules.json'), 'core'),
                         (str(root / 'LICENSE'), 'licenses'), (str(root / 'third_party'), 'licenses/third_party')],
    hiddenimports=ctk_hiddenimports, hookspath=[], runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='YaOS Debloater',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch='arm64', codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='YaOS Debloater')
app = BUNDLE(coll, name='YaOS Debloater.app', icon=str(root / 'assets/yaos.icns'),
    bundle_identifier='org.yaos.debloater', info_plist={
        'CFBundleDisplayName':'YaOS Debloater', 'CFBundleShortVersionString':'0.6.1',
        'CFBundleVersion':'7', 'NSHighResolutionCapable':True,
        'NSLocalNetworkUsageDescription':'YaOS connects to your Android TV over ADB for diagnostics and explicitly confirmed package management.',
    })
