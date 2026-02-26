# `truescaler.py` CLI Reference

`truescaler.py` is the primary CLI for this project.

It can process individual files, directory trees, or JSON-defined jobs.

## Usage

```bash
truescaler [options] [inputs ...]
```

## Positional Inputs

- `inputs`: image files or directories
- Supported input extensions when scanning directories: `png,jpg,jpeg,bmp,heic,webp` (default list)
- Positional inputs are optional only when `--json` or `--json-file` provides `inputs`

## Options

- `--out-dir OUT_DIR`
  - Write outputs to this directory (default: alongside each input)
- `--output OUTPUT`
  - Output base name (no extension) used during processing
- `--threshold THRESHOLD`
  - Whitespace crop threshold (default: `245`)
- `--tolerance TOLERANCE`
  - Integer-block detection color tolerance (default: `0`)
- `--require-square`
  - Require square block scale (`kx == ky`)
- `--max-checks MAX_CHECKS`
  - Upper bound for block-search checks (default: `10000`)
- `--no-save`
  - Detect/report scale and true size without writing output image
- `--json JSON`
  - JSON object string for arguments (mutually exclusive with `--json-file`)
- `--json-file JSON_FILE`
  - Path to JSON object file (mutually exclusive with `--json`)
- `--json-log`
  - Print JSON results only; suppress progress/status text
- `--recursive` / `--no-recursive`
  - Directory recursion toggle (default: recursive enabled)
- `--extensions EXTENSIONS`
  - Comma-separated extension allowlist for directory scans
- `--out-format OUT_FORMAT`
  - Output format: `png` or `bmp` (default: `png`)
- `--prgresss` / `--progress`
  - Enable progress bar (default enabled)
- `--no-prgresss` / `--no-progress`
  - Disable progress bar

## Behavior Notes

- Directory inputs are expanded to matching files before processing.
- Default recursion is on; use `--no-recursive` for top-level-only.
- Final saved filename pattern is:
  - `<input_stem>_<true_w>x<true_h>.<ext>`
- For `png` output, alpha can be preserved.
- For `bmp` output, transparent pixels are composited over white.
- With `--no-save`, output files are not written, but dimensions/scales are still reported.

## Examples

Single file:

```bash
truescaler sprite.png
```

Directory recursive (default):

```bash
truescaler assets/ --out-dir downsamples/
```

Directory non-recursive:

```bash
truescaler assets/ --no-recursive --out-dir downsamples/
```

No file write, detect/report only:

```bash
truescaler sprite.png --no-save --no-prgresss
```

BMP output:

```bash
truescaler sprite.png --out-dir outs --out-format bmp
```

JSON payload:

```bash
truescaler --json '{"inputs":["sprite.png"],"out_dir":"outs","out_format":"bmp","progress":false}' --json-log
```
