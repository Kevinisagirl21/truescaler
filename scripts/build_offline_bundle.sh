#!/usr/bin/env bash
set -euo pipefail

# Build a release bundle with source files + predownloaded dependency wheels.
# Result:
#   dist/truescaler-bundle.tar.gz
#
# Usage:
#   bash scripts/build_offline_bundle.sh
#   INCLUDE_HEIF=1 bash scripts/build_offline_bundle.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DIST_DIR="${DIST_DIR:-$REPO_ROOT/dist}"
BUNDLE_NAME="${BUNDLE_NAME:-truescaler-bundle}"
INCLUDE_HEIF="${INCLUDE_HEIF:-0}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: Python executable '$PYTHON_BIN' was not found." >&2
  exit 1
fi

tmp_root="$(mktemp -d)"
cleanup() { rm -rf "$tmp_root"; }
trap cleanup EXIT

bundle_dir="$tmp_root/$BUNDLE_NAME"
mkdir -p "$bundle_dir/wheels"

for f in install.sh truescaler.py find_scale.py README.md; do
  if [[ ! -f "$REPO_ROOT/$f" ]]; then
    echo "Error: missing required file: $f" >&2
    exit 1
  fi
  cp -a "$REPO_ROOT/$f" "$bundle_dir/$f"
done

if [[ -d "$REPO_ROOT/docs" ]]; then
  cp -a "$REPO_ROOT/docs" "$bundle_dir/docs"
fi

deps=("numpy" "Pillow")
if [[ "$INCLUDE_HEIF" == "1" ]]; then
  deps+=("pillow-heif")
fi

echo "Downloading wheels for: ${deps[*]}"
"$PYTHON_BIN" -m pip download --only-binary=:all: --dest "$bundle_dir/wheels" "${deps[@]}"

mkdir -p "$DIST_DIR"
tar -C "$tmp_root" -czf "$DIST_DIR/$BUNDLE_NAME.tar.gz" "$BUNDLE_NAME"

echo "Bundle created:"
echo "  $DIST_DIR/$BUNDLE_NAME.tar.gz"
echo
echo "End-user install example:"
echo "  bash install.sh --bundle $DIST_DIR/$BUNDLE_NAME.tar.gz"

