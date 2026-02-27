# TrueScaler

TrueScaler detects pixel-art scale, crops whitespace/background, and downsamples images to true pixel size.

## Disclaimer

This is a personal project. Use at your own risk.

## Project Provenance

This repository has so far been primarily AI-generated, with human direction, review, and iterative edits.

## Architecture

- `truescaler.py`: Python CLI/orchestration (`argparse`, JSON input, directory traversal, progress output)
- `_truescaler_core`: required native C++ backend module (pybind11 + OpenCV)

## Requirements

- Python 3.10+
- Native build deps for source installs: C++ compiler, CMake, OpenCV development libraries
- Runtime Python packages:
  - `numpy`
  - `Pillow`
  - optional `pillow-heif` for HEIC/HEIF input support

## Install

From repo source (developer/local):

```bash
python -m pip install -e .
```

Run:

```bash
python truescaler.py --help
```

Single-command installer:

```bash
./install.sh
```

Offline release bundle:

```bash
./install.sh --bundle truescaler-bundle.tar.gz
```

GitHub release bundle:

```bash
./install.sh --from-github owner/repo
```

## Build Offline Bundle (maintainers)

```bash
bash scripts/build_offline_bundle.sh
```

With HEIC runtime wheel included:

```bash
INCLUDE_HEIF=1 bash scripts/build_offline_bundle.sh
```

Outputs:

- `dist/truescaler-bundle.tar.gz`
- `dist/truescaler-bundle-heif.tar.gz`
- `dist/wheels/*.whl` (native backend wheels)

## CI and Release

- CI (`.github/workflows/ci.yml`) installs/builds native backend with `pip install -e .`, verifies `_truescaler_core` import, then runs `pytest -q`.
- Release workflow (`.github/workflows/release-bundle.yml`) builds offline bundles and publishes:
  - `install.sh`
  - native wheel(s)
  - bundle archives

## Quick Start

```bash
python truescaler.py input.png
python truescaler.py images/ --out-dir downsamples/
python truescaler.py --json '{"inputs":["a.png"],"out_dir":"outs","out_format":"bmp"}'
```

Output naming:

`<input_stem>_<true_w>x<true_h>.<ext>`

## Documentation

- [`docs/cli-truescaler.md`](docs/cli-truescaler.md)
- [`docs/json-input.md`](docs/json-input.md)
- [`docs/troubleshooting.md`](docs/troubleshooting.md)

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

GPL-3.0 (`LICENSE`).

## Testing

```bash
pytest -q
```
