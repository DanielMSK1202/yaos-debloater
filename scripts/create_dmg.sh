#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
app='dist/YaOS Debloater.app'
[[ -d "$app" ]] || { echo 'Build the macOS app first.' >&2; exit 1; }
stage="$(mktemp -d "$PWD/build/dmg-stage.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
ditto "$app" "$stage/YaOS Debloater.app"
ln -s /Applications "$stage/Applications"
cp LICENSE "$stage/LICENSE.txt"
hdiutil create -volname 'YaOS Debloater' -srcfolder "$stage" -format UDZO -ov 'dist/YaOS-Debloater-0.6.1-macos-arm64.dmg'
shasum -a 256 'dist/YaOS-Debloater-0.6.1-macos-arm64.dmg' > dist/SHA256SUMS.txt
