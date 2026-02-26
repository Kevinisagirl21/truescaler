# `truescaler.py` JSON Input Contract

`truescaler.py` accepts JSON arguments through:

- `--json '<object>'`
- `--json-file path/to/args.json`

These flags are mutually exclusive.

## Top-Level Requirements

- Payload must be a JSON object.
- Unknown keys are rejected with an error.
- Type mismatches are rejected with an error.

## Allowed Keys and Types

- `inputs`: list of strings
- `out_dir`: string
- `output`: string
- `threshold`: integer
- `tolerance`: integer
- `require_square`: boolean
- `max_checks`: integer
- `no_save`: boolean
- `recursive`: boolean
- `out_format`: string (`png` or `bmp`)
- `progress`: boolean
- `prgresss`: boolean

## Precedence Rules

- `--json` and `--json-file` cannot be used together.
- For progress keys inside JSON:
  - `progress` takes precedence over `prgresss`.
  - If `progress` is absent, `prgresss` is used.
- JSON values override corresponding CLI flag defaults.

## Valid Examples

Inline JSON:

```bash
truescaler --json '{"inputs":["a.png"],"out_dir":"outs","out_format":"bmp","progress":false}'
```

JSON file:

```json
{
  "inputs": ["images/a.png", "images/b.png"],
  "out_dir": "outs",
  "threshold": 245,
  "tolerance": 0,
  "recursive": true,
  "out_format": "png",
  "progress": false
}
```

```bash
truescaler --json-file args.json --json-log
```

## Invalid Examples

Unknown key:

```bash
truescaler --json '{"inputs":["a.png"],"foo":123}'
```

Invalid type:

```bash
truescaler --json '{"inputs":"a.png"}'
```

Invalid format value:

```bash
truescaler --json '{"inputs":["a.png"],"out_format":"jpg"}'
```
