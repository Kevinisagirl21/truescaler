# `find_scale.py` CLI Reference

`find_scale.py` is the simpler secondary CLI.

Use it when you want a lightweight command without JSON mode or directory recursion features.

## Usage

```bash
truescaler-find-scale [options] inputs [inputs ...]
```

## Options

- `--out-dir OUT_DIR`
  - Directory for output images
- `--output OUTPUT`
  - Output base name (no extension)
- `--threshold THRESHOLD`
  - Whitespace crop threshold (default: `245`)
- `--tolerance TOLERANCE`
  - Integer-block color tolerance (default: `0`)
- `--require-square`
  - Require square block scale
- `--max-checks MAX_CHECKS`
  - Max block-search checks (default: `10000`)
- `--no-save`
  - Report scale and dimensions only

## Examples

```bash
truescaler-find-scale input.png
truescaler-find-scale input.png --out-dir downsamples/
truescaler-find-scale a.png b.png --no-save
```

## How It Differs From `truescaler.py`

- No `--json` / `--json-file` mode.
- No `--recursive` directory expansion options.
- No `--extensions` filtering.
- No output format selector (`--out-format`).
- No progress control flags.

Choose `find_scale.py` for quick direct file processing.  
Choose `truescaler.py` for full workflow control.
