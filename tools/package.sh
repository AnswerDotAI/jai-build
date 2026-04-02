#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
root_dir="$(cd "$script_dir/.." && pwd -P)"

: "${PYTHON:=python3}"

source_dir="$root_dir/jai"
smoke_test=0

usage() {
  cat <<'EOF'
Usage:
  tools/package.sh [--smoke-test] [source-dir]

Examples:
  tools/package.sh
  tools/package.sh jai
  tools/package.sh --smoke-test
  tools/package.sh --smoke-test /path/to/jai
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke-test)
      smoke_test=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      source_dir="$1"
      shift
      ;;
  esac
done

source_dir="$(cd "$source_dir" && pwd -P)"
work_dir="$(mktemp -d)"
venv_dir=""

cleanup() {
  rm -rf "$work_dir"
  if [[ -n "$venv_dir" ]]; then
    rm -rf "$venv_dir"
  fi
}
trap cleanup EXIT

cd "$root_dir"

./build.sh "$source_dir"

rm -rf jai_binary py-dist
mkdir -p jai_binary py-dist

tarball="$(find dist -maxdepth 1 -name 'jai-*-linux-*-glibc.tar.gz' | sort | head -n1)"
if [[ -z "$tarball" ]]; then
  echo "No release tarball found in dist/" >&2
  exit 1
fi

stage_dir="$(tar -tf "$tarball" | cut -d/ -f1 | sort -u)"
if [[ -z "$stage_dir" ]]; then
  echo "Unable to determine extracted directory name from $tarball" >&2
  exit 1
fi

tar -xzf "$tarball" -C "$work_dir"
cp "$work_dir/$stage_dir/jai" jai_binary/jai
chmod +x jai_binary/jai

"$PYTHON" -m pip install setuptools wheel
"$PYTHON" -m pip wheel . --no-deps --wheel-dir py-dist/

wheel="$(find py-dist -maxdepth 1 -name '*.whl' | sort | head -n1)"
if [[ -z "$wheel" ]]; then
  echo "No wheel found in py-dist/" >&2
  exit 1
fi

echo "Built tarball: $tarball"
echo "Built wheel:   $wheel"

if [[ $smoke_test -eq 1 ]]; then
  venv_dir="$(mktemp -d)"
  "$PYTHON" -m venv "$venv_dir"
  "$venv_dir/bin/python" -m pip install "$wheel"
  "$venv_dir/bin/python" - <<'PY'
import importlib.metadata as metadata
import jai_sandbox

print(f"package_version={metadata.version('jai-sandbox')}")
print(f"module_version={jai_sandbox.__version__}")
PY
  "$venv_dir/bin/jai" --version >/dev/null
  "$venv_dir/bin/jai" --print-defaults >/dev/null
  echo "Smoke test passed"
fi
