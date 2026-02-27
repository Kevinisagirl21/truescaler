#!/usr/bin/env python3
"""TrueScaler CLI (Python argparse/orchestration + C++ processing backend)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    import _truescaler_core as core  # pyright: ignore[reportMissingModuleSource]
except Exception as exc:  # pragma: no cover - required native backend
    raise RuntimeError(
        "Required C++ backend module '_truescaler_core' is not available. "
        "Build/install it first with:\n"
        "  python -m pip install -e .\n"
        "Or build a wheel and install it:\n"
        "  python -m build\n"
        "  python -m pip install dist/*.whl"
    ) from exc


def process_file(
    path: str,
    out_dir: Optional[str] = None,
    out_name: Optional[str] = None,
    threshold: int = 245,
    tolerance: int = 0,
    require_square: bool = False,
    max_checks: int = 1000,
    write_downsample: bool = True,
    verbose: bool = True,
    out_format: str = "png",
) -> Dict[str, Any]:
    """Thin wrapper around native C++ backend."""
    native_out_dir = out_dir or ""
    native_out_name = out_name or ""
    return core.process_file_cpp(
        str(path),
        native_out_dir,
        native_out_name,
        int(threshold),
        int(tolerance),
        bool(require_square),
        int(max_checks),
        bool(write_downsample),
        bool(verbose),
        str(out_format),
    )


def cli() -> Optional[List[Dict[str, Any]]]:
    epilog = (
        "Examples:\n"
        "  python3 truescaler.py input.heic\n"
        "  python3 truescaler.py input.png --out-dir downsamples/ --output myname\n"
        "  python3 truescaler.py *.png --no-save  # just report scales\n"
        "  python3 truescaler.py images/ --no-prgresss  # disable progress bar\n"
        "JSON API examples:\n"
        "  python3 truescaler.py --json '{\"inputs\":[\"a.png\"],\"out_dir\":\"outs\",\"out_format\":\"bmp\"}' --json-log\n"
        "  JSON keys: inputs,out_dir,output,threshold,tolerance,require_square,max_checks,no_save,recursive,out_format,progress,prgresss\n"
    )

    parser = argparse.ArgumentParser(
        description="Detect pixel-art scale, crop whitespace/background, and downsample to true pixel size.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("inputs", nargs="*", help="Input image files or directories (supports HEIC/PNG/JPG/BMP/WEBP). Optional with --json/--json-file.")
    parser.add_argument("--out-dir", help="Directory to write outputs (default: alongside each input)")
    parser.add_argument("--output", help="Output base name (no extension). For multiple inputs, original stem is recommended.")
    parser.add_argument("--threshold", type=int, default=245, help="Whitespace crop threshold (0-255) (default: 245)")
    parser.add_argument("--tolerance", type=int, default=0, help="Color tolerance for integer-block detection (max channel diff) (default: 0)")
    parser.add_argument("--require-square", action="store_true", help="Require square blocks (kx==ky) (default: False)")
    parser.add_argument("--max-checks", type=int, default=10000, help="Max checks for block search (default: 10000)")
    parser.add_argument("--no-save", action="store_true", help="Do not write downsampled image; only report detected scale/size.")
    parser.add_argument("--json", help="JSON argument object (mutually exclusive with --json-file).")
    parser.add_argument("--json-file", help="Path to JSON argument object file (mutually exclusive with --json).")
    parser.add_argument("--json-log", action="store_true", help="Emit results as JSON only (no progress/status lines).")

    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recursively search directories when input is a directory (default: True)",
    )
    parser.add_argument("--extensions", default="png,jpg,jpeg,bmp,heic,webp", help="Comma-separated list of extensions to include when searching directories (default: png,jpg,jpeg,bmp,heic,webp)")
    parser.add_argument("--out-format", default="png", help="Output image format: png or bmp (default: png)")
    parser.add_argument("--prgresss", "--progress", dest="progress", action="store_true", default=True, help="Show progress bar while processing (default: True)")
    parser.add_argument("--no-prgresss", "--no-progress", dest="progress", action="store_false", help="Disable progress bar output")

    args = parser.parse_args()

    if args.json and args.json_file:
        parser.error("--json and --json-file are mutually exclusive; provide only one.")

    def load_json_payload() -> Optional[Dict[str, Any]]:
        payload_obj: Any
        if args.json_file:
            try:
                with open(args.json_file, "r", encoding="utf8") as f:
                    payload_obj = json.load(f)
            except FileNotFoundError:
                parser.error(f"JSON file not found: {args.json_file}")
            except json.JSONDecodeError as exc:
                parser.error(f"Invalid JSON in --json-file: {exc}")
        elif args.json:
            try:
                payload_obj = json.loads(args.json)
            except json.JSONDecodeError as exc:
                parser.error(f"Invalid JSON in --json: {exc}")
        else:
            return None
        if not isinstance(payload_obj, dict):
            parser.error("JSON payload must be an object with key/value pairs.")
        payload_raw = cast(Dict[object, Any], payload_obj)
        payload_dict: Dict[str, Any] = {}
        for key_obj, val_obj in payload_raw.items():
            if not isinstance(key_obj, str):
                parser.error("JSON payload object keys must be strings.")
            payload_dict[key_obj] = val_obj
        return payload_dict

    def validate_json_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        allowed_keys = {
            "inputs", "out_dir", "output", "threshold", "tolerance",
            "require_square", "max_checks", "no_save", "recursive", "out_format", "progress", "prgresss",
        }
        unknown = sorted(k for k in payload.keys() if k not in allowed_keys)
        if unknown:
            parser.error(
                f"Unknown keys in JSON payload: {', '.join(unknown)}. "
                f"Allowed keys: {', '.join(sorted(allowed_keys))}."
            )

        def ensure_type(key: str, expected: str) -> None:
            if key not in payload:
                return
            val = payload[key]
            if expected == "inputs":
                if not isinstance(val, list):
                    parser.error("JSON key 'inputs' must be a list of strings.")
                items = cast(List[object], val)
                if any(not isinstance(entry_obj, str) for entry_obj in items):
                    parser.error("JSON key 'inputs' must be a list of strings.")
            elif expected == "str":
                if not isinstance(val, str):
                    parser.error(f"JSON key '{key}' must be a string.")
            elif expected == "int":
                if not isinstance(val, int) or isinstance(val, bool):
                    parser.error(f"JSON key '{key}' must be an integer.")
            elif expected == "bool":
                if not isinstance(val, bool):
                    parser.error(f"JSON key '{key}' must be a boolean.")

        ensure_type("inputs", "inputs")
        ensure_type("out_dir", "str")
        ensure_type("output", "str")
        ensure_type("out_format", "str")
        ensure_type("threshold", "int")
        ensure_type("tolerance", "int")
        ensure_type("max_checks", "int")
        ensure_type("require_square", "bool")
        ensure_type("no_save", "bool")
        ensure_type("recursive", "bool")
        ensure_type("progress", "bool")
        ensure_type("prgresss", "bool")
        return payload

    def resolve_output_format(raw_format: str) -> str:
        fmt = raw_format.strip().lower()
        allowed = {"png", "bmp"}
        if fmt not in allowed:
            parser.error(f"Unsupported --out-format '{raw_format}'. Supported formats: png,bmp")
        return fmt

    def print_progress(done: int, total: int, width: int = 32) -> None:
        if total <= 0:
            return
        ratio = max(0.0, min(1.0, float(done) / float(total)))
        filled = int(width * ratio)
        bar = "#" * filled + "-" * (width - filled)
        print(f"\rProgress [{bar}] {done}/{total}", end="", flush=True)
        if done >= total:
            print()

    json_payload = load_json_payload()
    if json_payload is not None:
        json_payload = validate_json_payload(json_payload)

    if json_payload is not None:
        inputs = json_payload.get("inputs", [])
        out_dir = json_payload.get("out_dir", args.out_dir)
        output = json_payload.get("output", args.output)
        threshold = json_payload.get("threshold", args.threshold)
        tolerance = json_payload.get("tolerance", args.tolerance)
        require_square = json_payload.get("require_square", args.require_square)
        max_checks = json_payload.get("max_checks", args.max_checks)
        no_save = json_payload.get("no_save", args.no_save)
        recursive = json_payload.get("recursive", args.recursive)
        out_format = json_payload.get("out_format", args.out_format)
        progress = json_payload.get("progress", json_payload.get("prgresss", args.progress))
    else:
        inputs = args.inputs
        out_dir = args.out_dir
        output = args.output
        threshold = args.threshold
        tolerance = args.tolerance
        require_square = args.require_square
        max_checks = args.max_checks
        no_save = args.no_save
        recursive = args.recursive
        out_format = args.out_format
        progress = args.progress

    out_fmt = resolve_output_format(str(out_format))

    if not inputs:
        parser.error("No input files provided (use positional inputs or --json/--json-file).")

    def find_images_in_dir(d: str, exts: List[str], recursive: bool) -> List[str]:
        res: List[str] = []
        for root, _dirs, files in os.walk(d):
            for f in files:
                if any(f.lower().endswith("." + e) for e in exts):
                    res.append(os.path.join(root, f))
            if not recursive:
                break
        return res

    work_items: List[str] = []
    exts = [e.strip().lower() for e in args.extensions.split(",") if e.strip()]
    for inp in inputs:
        p = Path(inp)
        paths = [str(p)]
        if p.is_dir():
            paths = find_images_in_dir(str(p), exts, recursive)
        work_items.extend(paths)

    results: List[Dict[str, Any]] = []
    total = len(work_items)
    show_progress = bool(progress) and not args.json_log and total > 0
    for idx, path in enumerate(work_items, start=1):
        base_out_name = output if output else None
        res = process_file(
            path,
            out_dir=out_dir,
            out_name=base_out_name,
            threshold=threshold,
            tolerance=tolerance,
            require_square=require_square,
            max_checks=max_checks,
            write_downsample=not no_save,
            verbose=False,
            out_format=out_fmt,
        )
        if not args.json_log and not show_progress:
            if no_save:
                print(f"{Path(path).name}: scale {res['scale_x']}x{res['scale_y']} -> {res['true_w']}x{res['true_h']}, no output (--no-save)")
            else:
                print(f"{Path(path).name}: scale {res['scale_x']}x{res['scale_y']} -> {res['true_w']}x{res['true_h']}, saved {res['out']}")

        results.append({
            "input": path,
            "output": res.get("out"),
            "scale_x": res["scale_x"],
            "scale_y": res["scale_y"],
            "true_w": res["true_w"],
            "true_h": res["true_h"],
        })

        if show_progress:
            print_progress(idx, total)

    if args.json_log:
        print(json.dumps(results, indent=2))
    else:
        return results


if __name__ == "__main__":
    cli()
