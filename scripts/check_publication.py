"""Dry-run Git staging in a temporary index; never contacts a remote."""
import subprocess
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='yaos-publication-') as tmp:
    subprocess.run(['git','init','--bare','--quiet',tmp],check=True)
    git=['git',f'--git-dir={tmp}',f'--work-tree={root}','-c','core.bare=false']
    subprocess.run(git+['add','--all'],check=True)
    files=subprocess.check_output(git+['ls-files'],text=True).splitlines()
    allowed_dirs=('core/','gui/','tests/','assets/','third_party/','.github/')
    allowed_files={'main.py','requirements.txt','requirements-build.txt','YaOS-Debloater.spec','.gitignore','LICENSE','README.md','PUBLISHING.md',
                   'scripts/build_macos.sh','scripts/create_dmg.sh','scripts/collect_notices.py','scripts/check_publication.py'}
    unexpected=[p for p in files if not p.startswith(allowed_dirs) and p not in allowed_files]
    forbidden=[p for p in files if p=='core/user_preferences.json' or p.startswith(('reports/','backups/','previews/','android/','.tools/','dist/','build/'))]
    if unexpected or forbidden:
        raise SystemExit(f'Review required ({len(unexpected+forbidden)} paths): '+repr((unexpected+forbidden)[:10]))
    output=root/'build/publication-files.txt';output.parent.mkdir(exist_ok=True)
    output.write_text('\n'.join(files)+'\n')
    print(f'Public source dry run: {len(files)} files. Private data and LiteOS excluded. Manifest: {output}')
