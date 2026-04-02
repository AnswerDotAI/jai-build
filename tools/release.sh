#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
root_dir="$(cd "$script_dir/.." && pwd -P)"
: "${PYTHON:=python3}"

push_tag=0
remote=origin

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push)
      push_tag=1
      shift
      ;;
    --remote)
      [[ $# -ge 2 ]] || { echo "Missing value for --remote" >&2; exit 1; }
      remote="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

cd "$root_dir"

if [[ -n "$(git status --short --untracked-files=normal)" ]]; then
  echo "Working tree is not clean. Commit, stash, or remove changes before tagging a release." >&2
  exit 1
fi

version="$("$PYTHON" tools/version.py package-version)"
tag="$("$PYTHON" tools/version.py tag)"
upstream_version="$("$PYTHON" tools/version.py upstream-version)"
source_ref="$("$PYTHON" tools/version.py source-ref)"

if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
  echo "Tag already exists: $tag" >&2
  exit 1
fi

echo "Creating release tag $tag"
echo "  package version: $version"
echo "  upstream version: $upstream_version"
echo "  source ref: $source_ref"

git tag -a "$tag" -m "Release $tag"

if [[ $push_tag -eq 1 ]]; then
  git push "$remote" "$tag"
else
  echo "Created $tag locally. Push it with: git push $remote $tag"
fi
