#!/usr/bin/env bash
set -euo pipefail

# TrueScaler single-command installer.
# Default install layout:
#   ~/.local/share/truescaler/venv
#   ~/.local/share/truescaler/src/truescaler.py
#   ~/.local/share/truescaler/wheels/*
#   ~/.local/bin/truescaler
#
# Optional offline bundle usage:
#   bash install.sh --bundle truescaler-bundle.tar.gz
# Optional GitHub release usage:
#   bash install.sh --from-github owner/repo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PREFIX="${PREFIX:-$HOME/.local}"
APP_DIR="${APP_DIR:-$PREFIX/share/truescaler}"
BIN_DIR="${BIN_DIR:-$PREFIX/bin}"
INCLUDE_HEIF="${INCLUDE_HEIF:-0}"
USE_SYSTEM_SITE_PACKAGES="${USE_SYSTEM_SITE_PACKAGES:-1}"
BUNDLE_ARCHIVE=""
GITHUB_REPO=""
GITHUB_TAG="latest"
BUNDLE_NAME="${BUNDLE_NAME:-truescaler-bundle.tar.gz}"
tmp_extract=""
tmp_download=""

cleanup_tmp() {
  if [[ -n "$tmp_extract" && -d "$tmp_extract" ]]; then
    rm -rf "$tmp_extract"
  fi
  if [[ -n "$tmp_download" && -f "$tmp_download" ]]; then
    rm -f "$tmp_download"
  fi
}
trap cleanup_tmp EXIT

usage() {
  cat <<'EOF'
Usage:
  bash install.sh [--bundle <bundle.tar.gz>]
  bash install.sh --from-github <owner/repo> [--tag <tag>] [--bundle-name <name.tar.gz>]

Options:
  --bundle PATH   Install from an offline bundle archive created by scripts/build_offline_bundle.sh.
  --from-github   Download bundle from GitHub Releases for owner/repo.
  --tag TAG       Release tag to download from with --from-github (default: latest).
  --bundle-name   Bundle asset filename (default: truescaler-bundle.tar.gz).
  -h, --help      Show this help text.

Environment:
  PYTHON_BIN               Python executable (default: python3)
  PREFIX                   Install prefix (default: ~/.local)
  APP_DIR                  App directory (default: $PREFIX/share/truescaler)
  BIN_DIR                  Binary dir (default: $PREFIX/bin)
  INCLUDE_HEIF             Set to 1 to require/install pillow-heif
  USE_SYSTEM_SITE_PACKAGES Set to 1 to create venv with --system-site-packages (default: 1)
  BUNDLE_NAME              Default bundle asset name for --from-github
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle)
      if [[ $# -lt 2 ]]; then
        echo "Error: --bundle requires a path argument." >&2
        exit 1
      fi
      BUNDLE_ARCHIVE="$2"
      shift 2
      ;;
    --from-github)
      if [[ $# -lt 2 ]]; then
        echo "Error: --from-github requires owner/repo." >&2
        exit 1
      fi
      GITHUB_REPO="$2"
      shift 2
      ;;
    --tag)
      if [[ $# -lt 2 ]]; then
        echo "Error: --tag requires a value." >&2
        exit 1
      fi
      GITHUB_TAG="$2"
      shift 2
      ;;
    --bundle-name)
      if [[ $# -lt 2 ]]; then
        echo "Error: --bundle-name requires a value." >&2
        exit 1
      fi
      BUNDLE_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument '$1'." >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: Python executable '$PYTHON_BIN' was not found." >&2
  exit 1
fi
if [[ -n "$BUNDLE_ARCHIVE" && -n "$GITHUB_REPO" ]]; then
  echo "Error: choose only one source: --bundle or --from-github." >&2
  exit 1
fi
if [[ -n "$GITHUB_REPO" ]]; then
  if ! command -v curl >/dev/null 2>&1; then
    echo "Error: curl is required for --from-github." >&2
    exit 1
  fi
  tmp_download="$(mktemp /tmp/truescaler-bundle.XXXXXX.tar.gz)"
  if [[ "$GITHUB_TAG" == "latest" ]]; then
    dl_url="https://github.com/$GITHUB_REPO/releases/latest/download/$BUNDLE_NAME"
  else
    dl_url="https://github.com/$GITHUB_REPO/releases/download/$GITHUB_TAG/$BUNDLE_NAME"
  fi
  echo "Downloading bundle from: $dl_url"
  curl -fsSL "$dl_url" -o "$tmp_download"
  BUNDLE_ARCHIVE="$tmp_download"
fi

SOURCE_ROOT="$SCRIPT_DIR"
if [[ -n "$BUNDLE_ARCHIVE" ]]; then
  if [[ ! -f "$BUNDLE_ARCHIVE" ]]; then
    echo "Error: bundle archive not found: $BUNDLE_ARCHIVE" >&2
    exit 1
  fi
  if ! command -v tar >/dev/null 2>&1; then
    echo "Error: 'tar' is required to extract bundle archives." >&2
    exit 1
  fi
  tmp_extract="$(mktemp -d)"
  tar -xzf "$BUNDLE_ARCHIVE" -C "$tmp_extract"

  if [[ -d "$tmp_extract/truescaler-bundle" ]]; then
    SOURCE_ROOT="$tmp_extract/truescaler-bundle"
  else
    candidate="$(find "$tmp_extract" -maxdepth 3 -type f -name truescaler.py | head -n 1 || true)"
    if [[ -n "$candidate" ]]; then
      SOURCE_ROOT="$(cd "$(dirname "$candidate")" && pwd)"
    fi
  fi
fi

if [[ ! -f "$SOURCE_ROOT/truescaler.py" ]]; then
  echo "Error: could not locate truescaler.py in source root: $SOURCE_ROOT" >&2
  exit 1
fi

echo "Installing TrueScaler..."
echo "  PYTHON_BIN: $PYTHON_BIN"
echo "  APP_DIR:    $APP_DIR"
echo "  BIN_DIR:    $BIN_DIR"
echo "  USE_SYSTEM_SITE_PACKAGES: $USE_SYSTEM_SITE_PACKAGES"
if [[ -n "$BUNDLE_ARCHIVE" ]]; then
  echo "  BUNDLE:     $BUNDLE_ARCHIVE"
fi
if [[ -n "$GITHUB_REPO" ]]; then
  echo "  GITHUB_REPO:$GITHUB_REPO"
  echo "  GITHUB_TAG: $GITHUB_TAG"
fi

mkdir -p "$APP_DIR" "$BIN_DIR"

mkdir -p "$APP_DIR/src"
install -m 755 "$SOURCE_ROOT/truescaler.py" "$APP_DIR/src/truescaler.py"

if [[ -d "$SOURCE_ROOT/wheels" ]]; then
  rm -rf "$APP_DIR/wheels"
  mkdir -p "$APP_DIR/wheels"
  cp -a "$SOURCE_ROOT/wheels/." "$APP_DIR/wheels/"
fi

venv_args=()
if [[ "$USE_SYSTEM_SITE_PACKAGES" == "1" ]]; then
  venv_args+=("--system-site-packages")
fi
"$PYTHON_BIN" -m venv "${venv_args[@]}" "$APP_DIR/venv"

deps=("numpy" "Pillow")
if [[ "$INCLUDE_HEIF" == "1" ]]; then
  deps+=("pillow-heif")
fi

pip_ok=1
if [[ -d "$APP_DIR/wheels" ]]; then
  if ! "$APP_DIR/venv/bin/pip" install --no-index --find-links "$APP_DIR/wheels" "${deps[@]}"; then
    pip_ok=0
    echo "Warning: offline wheel install failed. Checking existing environment..." >&2
  fi
else
  if ! "$APP_DIR/venv/bin/pip" install "${deps[@]}"; then
    pip_ok=0
    echo "Warning: pip dependency installation failed. Checking existing environment..." >&2
  fi
fi

missing_modules=()
if ! "$APP_DIR/venv/bin/python" -c "import numpy" >/dev/null 2>&1; then
  missing_modules+=("numpy")
fi
if ! "$APP_DIR/venv/bin/python" -c "from PIL import Image" >/dev/null 2>&1; then
  missing_modules+=("Pillow")
fi
if [[ "$INCLUDE_HEIF" == "1" ]]; then
  if ! "$APP_DIR/venv/bin/python" -c "import pillow_heif" >/dev/null 2>&1; then
    missing_modules+=("pillow-heif")
  fi
fi

if (( ${#missing_modules[@]} > 0 )); then
  echo "Error: missing required Python packages: ${missing_modules[*]}" >&2
  if [[ "$pip_ok" == "0" ]]; then
    if [[ -d "$APP_DIR/wheels" ]]; then
      echo "Bundled wheel installation failed. Rebuild bundle with scripts/build_offline_bundle.sh." >&2
    else
      echo "pip install failed, likely due network access. Re-run when online or use an offline bundle." >&2
    fi
  fi
  exit 1
fi

cat >"$BIN_DIR/truescaler" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$APP_DIR/venv/bin/python" "$APP_DIR/src/truescaler.py" "\$@"
EOF
chmod +x "$BIN_DIR/truescaler"

echo
echo "Install complete."
echo "Commands:"
echo "  $BIN_DIR/truescaler"
echo
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "Note: $BIN_DIR is not currently in PATH."
  echo "Add it with:"
  echo "  export PATH=\"$BIN_DIR:\$PATH\""
fi
echo
echo "Try:"
echo "  truescaler --help"
