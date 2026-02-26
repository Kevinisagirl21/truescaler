# This is a work in progress...
# TrueScaler
## A personal project designed to convert screenshots into their original resolution.
### Use Cases
- downscaing high-res photos of a low resolution image(eg. upscaled image) back to original quality with little to no loss in image quality.
 
TrueScaler detects pixel-art scale, crops whitespace/background, and downsamples images to true pixel size.
## Disclaimer
### I am not resposible for any data loss that may occur as a result of misuse and/or issues that the code may have.

## Project Provenance

This repository has so far been primarily AI-generated, with human direction, review, and iterative edits.
This is not production-ready, so tread lightly, and be careful.

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

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for contribution guidelines.

## License

This project is licensed under GPL-3.0. See [`LICENSE`](LICENSE).

## Testing

```bash
pytest -q
```

HEIC-specific tests require `pillow_heif` with HEIC codec support.
