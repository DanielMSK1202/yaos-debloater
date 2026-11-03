"""Collect installed dependency notices for binary redistribution (macOS build host)."""
from pathlib import Path
from importlib.metadata import distribution
import shutil
root=Path(__file__).resolve().parents[1]
target=root/'third_party'
target.mkdir(exist_ok=True)
for name in ('customtkinter','darkdetect','pyinstaller'):
    dist=distribution(name)
    for file in dist.files or []:
        if Path(str(file)).name.lower() in ('license','license.txt','copying.txt'):
            shutil.copyfile(dist.locate_file(file),target/f'{name}-{Path(str(file)).name}')
adb=shutil.which('adb')
if not adb: raise SystemExit('ADB missing on build host')
notice=Path(adb).resolve().with_name('NOTICE.txt')
if not notice.exists(): raise SystemExit('Platform-tools NOTICE.txt missing; do not release bundled ADB without its notices.')
shutil.copyfile(notice,target/'android-platform-tools-NOTICE.txt')
# Homebrew runtime libraries collected by PyInstaller on this build machine.
for name in ('python@3.14','tcl-tk','openssl','xz','zstd','mpdecimal','libtommath'):
    folder=Path('/opt/homebrew/opt')/name
    for p in folder.iterdir() if folder.exists() else []:
        if p.is_file() and p.name.lower().startswith(('license','copying','copyright')):
            shutil.copyfile(p,target/f'{name.replace("@", "-")}-{p.name}')
print('Notices collected in',target)
