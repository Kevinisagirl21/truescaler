# Troubleshooting

## Unsupported Output Format

Symptom:

- Error like: `Unsupported --out-format 'jpg'. Supported formats: png,bmp`

Cause:

- `truescaler.py` only supports `png` and `bmp` for output.

Fix:

```bash
truescaler input.png --out-format png
truescaler input.png --out-format bmp
```

## Invalid JSON or JSON Type Errors

Symptoms:

- `Invalid JSON in --json`
- `Invalid JSON in --json-file`
- `Unknown keys in JSON payload`
- `JSON key '...' must be ...`

Causes:

- Malformed JSON.
- Unsupported keys.
- Wrong value types.

Fix:

- Validate JSON syntax.
- Use only documented keys from `docs/json-input.md`.
- Ensure key types match the contract.

## No Outputs Produced From Directory Input

Symptoms:

- Command succeeds but no files are written.

Common causes:

- Directory has no files matching allowed extensions.
- `--no-save` is enabled.
- `--no-recursive` excluded nested files.

Checks:

```bash
truescaler images/ --extensions png,jpg,jpeg,bmp,heic,webp --no-prgresss
truescaler images/ --no-recursive --no-prgresss
truescaler images/ --no-save --no-prgresss
```

## HEIC/HEIF Files Fail To Open

Symptoms:

- HEIC images fail to load even though other formats work.

Cause:

- Optional HEIC support depends on `pillow_heif` and codec availability.

Fix:

- Install `pillow_heif`.
- Verify your runtime has HEIC codec support.
- Re-run with a known HEIC sample.

## Quick Diagnostics

Check CLI flags:

```bash
truescaler --help
```

Check test suite:

```bash
pytest -q
```

## `truescaler` Command Not Found

Symptom:

- Shell says `truescaler: command not found`

Cause:

- Installer put binaries in `~/.local/bin`, but that directory is not in `PATH`.

Fix:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then verify:

```bash
truescaler --help
```

## GitHub Release Install Fails

Symptom:

- `curl` fails during `--from-github`
- HTTP 404 for release asset

Causes:

- Wrong `owner/repo`
- Tag does not exist
- Asset name mismatch
- Network/access restrictions

Fix:

```bash
bash install.sh --from-github owner/repo
bash install.sh --from-github owner/repo --tag v1.2.3
bash install.sh --from-github owner/repo --bundle-name truescaler-bundle-heif.tar.gz
```
