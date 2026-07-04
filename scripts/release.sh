#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/release.sh <version> [--dry-run]

Creates a reviewed omni-srv-admin release:
  1. verifies git/gh prerequisites and clean worktree
  2. updates cli/omni/__init__.py and cli/setup.py
  3. prepends CHANGELOG.md notes from commits since the last tag
  4. commits chore(release): vX.Y.Z
  5. creates annotated tag vX.Y.Z
  6. pushes branch + tag and creates the GitHub release with notes

The version may be passed as 0.2.0 or v0.2.0.
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

raw_version="$1"
dry_run="${2:-}"
version="${raw_version#v}"
tag="v${version}"

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$ ]]; then
  echo "Invalid semantic version: $raw_version" >&2
  exit 2
fi
if [[ -n "$dry_run" && "$dry_run" != "--dry-run" ]]; then
  echo "Unknown option: $dry_run" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}
require_cmd git
require_cmd python
require_cmd gh

branch="$(git branch --show-current)"
if [[ -z "$branch" ]]; then
  echo "Detached HEAD is not allowed for release." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated. Run gh auth login first." >&2
  exit 1
fi

git fetch --tags origin
if git rev-parse "$tag" >/dev/null 2>&1; then
  echo "Tag already exists locally: $tag" >&2
  exit 1
fi
if git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1; then
  echo "Tag already exists on origin: $tag" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Worktree must be clean before starting a release." >&2
  git status --short
  exit 1
fi

last_tag="$(git describe --tags --abbrev=0 2>/dev/null || true)"
range="HEAD"
if [[ -n "$last_tag" ]]; then
  range="${last_tag}..HEAD"
fi

notes_file="$(mktemp)"
{
  echo "## ${tag} - $(date -u +%Y-%m-%d)"
  echo
  echo "### Implementações e correções"
  if git log --format='- %s (%h)' "$range" | grep -q .; then
    git log --format='- %s (%h)' "$range"
  else
    echo "- Release de manutenção/versionamento."
  fi
  echo
} > "$notes_file"

python - "$version" <<'PY'
from pathlib import Path
import json
import re
import sys
version = sys.argv[1]
files = [Path('cli/omni/__init__.py'), Path('cli/setup.py')]
for path in files:
    text = path.read_text(encoding='utf-8')
    if path.name == '__init__.py':
        text = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{version}"', text)
    else:
        text = re.sub(r'version="[^"]+"', f'version="{version}"', text)
    path.write_text(text, encoding='utf-8', newline='\n')

matrix_path = Path('modules/fleet-control-plane/configs/omni-version-matrix.json')
if matrix_path.exists():
    matrix = json.loads(matrix_path.read_text(encoding='utf-8'))
    matrix['desired_version'] = version
    matrix['updated_at'] = __import__('datetime').datetime.utcnow().strftime('%Y-%m-%d')
    for host in (matrix.get('hosts') or {}).values():
        if isinstance(host, dict):
            host['desired_version'] = version
    matrix_path.write_text(json.dumps(matrix, indent=2) + '\n', encoding='utf-8')
PY

if [[ -f CHANGELOG.md ]]; then
  tmp_changelog="$(mktemp)"
  cat "$notes_file" CHANGELOG.md > "$tmp_changelog"
  mv "$tmp_changelog" CHANGELOG.md
else
  {
    echo "# Changelog"
    echo
    cat "$notes_file"
  } > CHANGELOG.md
fi

python -m compileall -q cli/omni

if [[ "$dry_run" == "--dry-run" ]]; then
  echo "Dry-run release $tag prepared. Diff follows:"
  git diff -- cli/omni/__init__.py cli/setup.py CHANGELOG.md
  rm -f "$notes_file"
  exit 0
fi

git add cli/omni/__init__.py cli/setup.py CHANGELOG.md modules/fleet-control-plane/configs/omni-version-matrix.json
git commit -m "chore(release): ${tag}"
git tag -a "$tag" -F "$notes_file"
git push origin "$branch"
git push origin "$tag"
gh release create "$tag" --title "$tag" --notes-file "$notes_file" --verify-tag
rm -f "$notes_file"
echo "Release published: $tag"
