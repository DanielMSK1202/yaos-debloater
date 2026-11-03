# Publish YaOS Debloater to GitHub

No GitHub account has been authenticated by this preparation process. Nothing has
been pushed or uploaded. Never paste a GitHub token into this repository or chat.

## 1. Create the repository

Sign into your intended primary account at https://github.com/new.
Choose the name `yaos-debloater`, visibility **Public**, and leave the initialization
options (README, license and .gitignore) unchecked: these files already exist locally.
Copy the repository HTTPS URL shown after creation.

## 2. Upload source

Open Terminal in the project folder:

```bash
cd /Users/shukurullokh/Downloads/yaos-debloater
git init -b main
# Use your GitHub name and GitHub noreply address if Git asks for identity:
git config user.name "YOUR_GITHUB_NAME"
git config user.email "YOUR_GITHUB_NOREPLY_EMAIL"
.venv/bin/python scripts/check_publication.py
git add .
git status --short
git diff --cached --stat
```

Before committing, verify there are no `reports/`, `previews/`, `android/`, `.tools/`,
`.venv/`, `build/`, `dist/`, `backups/`, `core/user_preferences.json`,
`performance-*.json`, keys, local logs or credentials in the staged list.
The supplied `.gitignore` excludes those paths. If a sensitive file was previously
tracked, .gitignore alone does not remove it from Git history; stop and review.

```bash
git commit -m "Publish YaOS Debloater 0.6.1"
git remote add origin https://github.com/YOUR_ACCOUNT/yaos-debloater.git
git push -u origin main
```

GitHub requires an authenticated credential helper, SSH setup or GitHub CLI login;
a normal GitHub account password is not accepted for HTTPS pushes. An optional route:

```bash
brew install gh
gh auth login
# Choose GitHub.com, HTTPS, and browser login. Check the account:
gh auth status
gh auth setup-git
git push -u origin main
```

If you prefer the browser, use **Add file → Upload files**, but upload only the public
source files listed below; dragging the entire local folder bypasses .gitignore.

Public source directories: `core/` (excluding user_preferences.json), `gui/`, `tests/`,
`assets/`, `third_party/`, `.github/`. Public scripts: `scripts/build_macos.sh`,
`scripts/create_dmg.sh`, `scripts/collect_notices.py`, `scripts/check_publication.py`. Root files: `main.py`,
`requirements.txt`, `requirements-build.txt`, `YaOS-Debloater.spec`, `.gitignore`,
`LICENSE`, `README.md`, `PUBLISHING.md`.

## 3. Publish the downloadable app

Create a release at `https://github.com/YOUR_ACCOUNT/yaos-debloater/releases/new`.
Use tag **v0.6.1**, title **YaOS Debloater 0.6.1**, and describe it as a locally signed,
not notarized Apple Silicon build tested on ARTEL Android 9. Upload:

- `dist/YaOS-Debloater-0.6.1-macos-arm64.dmg`
- `dist/SHA256SUMS.txt`

The `.app` is already inside the DMG. Do not upload your full project directory,
diagnostic reports, or authentication files. GitHub automatically provides source
archives from the tag, so no manual source ZIP is needed.

Optional CLI after logging in and pushing source:

```bash
gh release create v0.6.1 dist/YaOS-Debloater-0.6.1-macos-arm64.dmg dist/SHA256SUMS.txt --title "YaOS Debloater 0.6.1" --notes "English interface. Apple Silicon macOS build. Locally signed; not Apple notarized. Tested on ARTEL Android 9. Review all package changes carefully."
```

## 4. Future builds

The **macOS app** workflow can be run under **Actions → macOS app → Run workflow**.
It also runs for version tags. It uploads build artifacts, not an automatic public
release. Verify downloaded artifacts before adding them to Releases. Update the
version in the PyInstaller spec, DMG script and documentation for each release.
