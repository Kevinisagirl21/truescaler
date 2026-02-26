# TrueScaler

TrueScaler detects pixel-art scale, crops whitespace/background, and downsamples images to true pixel size.

## CLI

- `truescaler.py`: full CLI with directory scanning, JSON input, progress control, and output format selection.

## Requirements

- Python 3.10+
- `Pillow`
- `numpy`
- Optional: `pillow_heif` for HEIC/HEIF input support

## Install (single command)

From the project directory (online install):

```bash
bash install.sh
```

Or from an offline release bundle (no end-user dependency download):

```bash
bash install.sh --bundle truescaler-bundle.tar.gz
```

Or directly from GitHub Releases (CI-built bundles):

```bash
bash install.sh --from-github owner/repo
```

Using release assets directly (installer script is published separately):

```bash
curl -fsSL -o install.sh https://github.com/owner/repo/releases/download/v1.2.3/install.sh
bash install.sh --from-github owner/repo --tag v1.2.3
```

Specific release tag:

```bash
bash install.sh --from-github owner/repo --tag v1.2.3
```

Install HEIC-enabled release asset (if published):

```bash
bash install.sh --from-github owner/repo --bundle-name truescaler-bundle-heif.tar.gz
```

This installs:

- virtualenv + dependencies under `~/.local/share/truescaler`
- commands in `~/.local/bin`:
  - `truescaler`

If `~/.local/bin` is not on your `PATH`, add:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Optional HEIC dependency install:

```bash
INCLUDE_HEIF=1 bash install.sh
```

## Build End-User Offline Bundle (maintainers)

Package source + dependency wheels into one archive:

```bash
bash scripts/build_offline_bundle.sh
```

With HEIC wheel included:

```bash
INCLUDE_HEIF=1 bash scripts/build_offline_bundle.sh
```

Output archive:

- `dist/truescaler-bundle.tar.gz`

## CI Release Packaging

GitHub Actions workflow:

- `.github/workflows/release-bundle.yml`

Behavior:

- On `workflow_dispatch`:
  - builds offline bundle artifacts and uploads them to workflow artifacts
- On tag push matching `v*`:
  - builds bundles
  - uploads artifacts
  - publishes release assets:
    - `install.sh`
    - `truescaler-bundle.tar.gz`
    - `truescaler-bundle-heif.tar.gz`

## Quick Start

```bash
truescaler input.png
truescaler images/ --out-dir downsamples/
truescaler images/ --no-recursive --out-dir downsamples/
truescaler images/ --no-prgresss
truescaler --json '{"inputs":["a.png"],"out_dir":"outs","out_format":"bmp"}'
truescaler --json-file args.json
```

Output files are written as:

`<input_stem>_<true_w>x<true_h>.<ext>`

Examples:

- `sprite_16x16.png`
- `character_32x48.bmp`

## Documentation

- [`docs/cli-truescaler.md`](docs/cli-truescaler.md): full `truescaler.py` CLI reference and examples
- [`docs/json-input.md`](docs/json-input.md): JSON payload contract for `truescaler.py`
- [`docs/troubleshooting.md`](docs/troubleshooting.md): common failure modes and fixes

## Testing

```bash
pytest -q
```

HEIC-specific tests require `pillow_heif` with HEIC codec support.
