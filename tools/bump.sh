#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
root_dir="$(cd "$script_dir/.." && pwd -P)"
: "${PYTHON:=python3}"

if [[ $# -eq 0 ]]; then
  cat <<'EOF'
Usage:
  tools/bump.sh --upstream-version <version> [--source-ref <ref>] [--packaging-revision <n>]
  tools/bump.sh --next-packaging-revision
  tools/bump.sh --packaging-revision <n>

Examples:
  tools/bump.sh --upstream-version 0.3-pre --source-ref master
  tools/bump.sh --next-packaging-revision
EOF
  exit 1
fi

python_args=("$root_dir/tools/version.py" set)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --upstream-version|--source-ref|--packaging-revision)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
      python_args+=("$1" "$2")
      shift 2
      ;;
    --next-packaging-revision)
      python_args+=("$1")
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

"$PYTHON" "${python_args[@]}" >/dev/null
"$PYTHON" "$root_dir/tools/version.py" show
