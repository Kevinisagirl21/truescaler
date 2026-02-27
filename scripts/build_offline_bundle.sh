#!/usr/bin/env bash
set -euo pipefail

# Build a release bundle containing:
# - CLI script and docs
# - prebuilt native backend wheel
# - runtime dependency wheels
# Installer script (install.sh) is shipped outside the bundle.

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

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "Error: pip is required." >&2
  exit 1
fi

tmp_root="$(mktemp -d)"
cleanup() { rm -rf "$tmp_root"; }
trap cleanup EXIT

bundle_dir="$tmp_root/$BUNDLE_NAME"
mkdir -p "$bundle_dir/wheels" "$DIST_DIR/wheels"

for f in truescaler.py README.md LICENSE pyproject.toml CMakeLists.txt; do
  if [[ ! -f "$REPO_ROOT/$f" ]]; then
    echo "Error: missing required file: $f" >&2
    exit 1
  fi
  cp -a "$REPO_ROOT/$f" "$bundle_dir/$f"
done

for d in cpp docs; do
  if [[ -d "$REPO_ROOT/$d" ]]; then
    cp -a "$REPO_ROOT/$d" "$bundle_dir/$d"
  fi
done

# Build native backend wheel for this platform.
"$PYTHON_BIN" -m pip wheel --no-deps --wheel-dir "$bundle_dir/wheels" "$REPO_ROOT"
cp -a "$bundle_dir/wheels"/*.whl "$DIST_DIR/wheels/"

deps=("numpy" "Pillow")
if [[ "$INCLUDE_HEIF" == "1" ]]; then
  deps+=("pillow-heif")
fi

echo "Downloading runtime wheels for: ${deps[*]}"
"$PYTHON_BIN" -m pip download --only-binary=:all: --dest "$bundle_dir/wheels" "${deps[@]}"

mkdir -p "$DIST_DIR"
tar -C "$tmp_root" -czf "$DIST_DIR/$BUNDLE_NAME.tar.gz" "$BUNDLE_NAME"

echo "Bundle created:"
echo "  $DIST_DIR/$BUNDLE_NAME.tar.gz"
echo "Native wheel(s):"
ls -1 "$DIST_DIR/wheels"/*.whl
