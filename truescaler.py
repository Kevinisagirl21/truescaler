#!/usr/bin/env python3
"""Combined pixel-art scaler and whitespace cropper CLI.

Usage examples:
  python3 truescaler.py input.heic
  python3 truescaler.py input.png --output name --out-dir downsamples/
"""

from __future__ import annotations

from PIL import Image
import numpy as np
from collections import Counter
from typing import Any, Deque
import math
import argparse
from pathlib import Path
import json
try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pillow_heif: Any = None
import os
from typing import List, Tuple, Optional, Dict, cast


def run_lengths_line(line: np.ndarray) -> List[int]:
    """Return run-lengths of consecutive identical pixels in a 1D line.

    The input `line` is an array of RGB pixel values. This helper is used by
    `detect_scale` to find repeated run lengths (true-pixel widths).
    """
    lengths: List[int] = []
    prev = tuple(line[0])
    count = 1
    for pix in line[1:]:
        p = tuple(pix)
        if p == prev:
            count += 1
        else:
            lengths.append(count)
            count = 1
            prev = p
    lengths.append(count)
    return lengths


def detect_scale(arr: np.ndarray, axis: int = 1) -> int:
    """Estimate a 1D scale (pixels per true pixel) along axis.

    axis=1 examines horizontal rows, axis=0 examines vertical columns.
    The method collects run-lengths of identical pixels, picks common
    candidate lengths (>1) and refines the result by taking the gcd of
    the smallest candidate lengths. This helps when the pattern contains
    multiples (e.g. runs of 48, 96, ...), returning the fundamental scale.
    """
    lengths: List[int] = []
    if axis == 1:
        # horizontal: gather run lengths from each row
        for row in arr:
            lengths.extend(run_lengths_line(row))
    else:
        # vertical: gather run lengths from each column
        for c in range(arr.shape[1]):
            col = arr[:, c]
            lengths.extend(run_lengths_line(col))

    if not lengths:
        return 1

    # Counter typing can be noisy under strict checking; use Any for local var
    cnt: Any = Counter(lengths)
    # ignore single-pixel noise; prefer lengths > 1
    candidates: dict[int, int] = {int(l): int(c) for l, c in cnt.items() if int(l) > 1}
    if not candidates:
        return 1

    # mode of run-lengths is a good initial estimate
    mode_len, _ = max(candidates.items(), key=lambda x: x[1])

    # compute gcd of several small candidate lengths to find fundamental
    small_lengths: List[int] = sorted(int(k) for k in candidates.keys())
    g: int = small_lengths[0]
    for l in small_lengths[1:10]:
        g = math.gcd(g, l)
        if g == 1:
            break
    return g if g > 1 else mode_len


def divisors(n: int) -> List[int]:
    """Return sorted divisors of integer n."""
    d: List[int] = []
    for i in range(1, int(n**0.5) + 1):
        if n % i == 0:
            d.append(i)
            if i != n // i:
                d.append(n // i)
    return sorted(d)


def find_integer_block_scale(arr: np.ndarray, require_square: bool = False, tolerance: int = 0, max_checks: int = 1000) -> Tuple[int, int]:
    """Try to find integer block size (kx, ky) where each block is uniform.

    The function enumerates divisors of width/height and tests block
    uniformity for different offsets so the grid need not align at (0,0).
    If `require_square` is True only consider kx==ky. `tolerance` allows
    small color deviations (max absolute channel difference).
    """
    h: int = int(arr.shape[0])
    w: int = int(arr.shape[1])
    div_w = divisors(w)
    div_h = divisors(h)
    div_w.sort(reverse=True)
    div_h.sort(reverse=True)

    checks = 0
    # prefer larger k (smaller true image) so sort divisors descending
    for k in div_w:
        for kk in div_h:
            if require_square and k != kk:
                continue
            if k == 1 and kk == 1:
                continue
            # try different top-left offsets in case pattern is shifted
            for oy in range(0, min(kk, h)):
                for ox in range(0, min(k, w)):
                    checks += 1
                    if checks > max_checks:
                        return 1, 1
                    h0 = h - oy
                    w0 = w - ox
                    if h0 <= 0 or w0 <= 0:
                        continue
                    if h0 % kk != 0 or w0 % k != 0:
                        continue
                    true_h = h0 // kk
                    true_w = w0 // k
                    try:
                        # reshape into blocks: (true_h, kk, true_w, k, channels)
                        sub = arr[oy: oy + true_h * kk, ox: ox + true_w * k]
                        blocks = sub.reshape(true_h, kk, true_w, k, -1)
                    except Exception:
                        continue
                    first = blocks[:, :1, :, :1, :]
                    if tolerance == 0:
                        ok = np.all(blocks == first, axis=(1, 3, 4))
                        if ok.all():
                            return k, kk
                    else:
                        diffs = np.max(np.abs(blocks - first), axis=(1, 3, 4))
                        if np.all(diffs <= tolerance):
                            return k, kk
    return 1, 1


def crop_whitespace_array(arr: np.ndarray, threshold: int = 245) -> np.ndarray:
    """Crop near-white border from an RGB numpy array and return the cropped array.

    `threshold` controls what is considered "white"; pixels with any channel
    below threshold are treated as non-white.
    """
    non_white_mask = np.any(arr < threshold, axis=2)
    rows = np.any(non_white_mask, axis=1)
    cols = np.any(non_white_mask, axis=0)
    if not rows.any() or not cols.any():
        return arr
    row_min, row_max = np.where(rows)[0][[0, -1]]
    col_min, col_max = np.where(cols)[0][[0, -1]]
    return arr[row_min:row_max+1, col_min:col_max+1]


def remove_background(arr: np.ndarray, tolerance: int = 10, bg_color: Optional[Tuple[int, int, int]] = None) -> np.ndarray:
    """Remove background by making pixels near `bg_color` transparent.

    If `bg_color` is None, the function samples the four borders and picks
    the most common color as background. `tolerance` is max absolute
    channel difference to consider a pixel background.
    Returns an RGBA numpy array.
    """
    h, w = arr.shape[0], arr.shape[1]
    # ensure integer math
    a = arr.astype(int)
    # sample border pixels
    border_pixels = np.concatenate([
        a[0, :], a[-1, :], a[:, 0], a[:, -1]
    ], axis=0)
    if bg_color is None:
        # pick most common border color
        vals, counts = np.unique(border_pixels.reshape(-1, 3), axis=0, return_counts=True)
        bg_color = tuple(vals[np.argmax(counts)])

    bg = np.array(bg_color, dtype=int)
    # compute mask of background-like pixels (L-inf across channels)
    diff = np.abs(a - bg[None, None, :])
    mask = np.all(diff <= tolerance, axis=2)

    # flood-fill from borders over mask to ensure contiguous bg regions
    visited = np.zeros_like(mask, dtype=bool)
    flood = np.zeros_like(mask, dtype=bool)
    from collections import deque
    q: Deque[tuple[int, int]] = deque()
    # enqueue border coords that match mask
    for x in range(w):
        if mask[0, x]:
            q.append((0, x))
        if mask[h - 1, x]:
            q.append((h - 1, x))
    for y in range(h):
        if mask[y, 0]:
            q.append((y, 0))
        if mask[y, w - 1]:
            q.append((y, w - 1))

    while q:
        y, x = q.popleft()
        if visited[y, x]:
            continue
        visited[y, x] = True
        if not mask[y, x]:
            continue
        flood[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and mask[ny, nx]:
                q.append((ny, nx))

    # create RGBA output with alpha=0 for flood-filled background
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = arr
    rgba[..., 3] = np.where(flood, 0, 255).astype(np.uint8)
    return rgba


def downsample_mode(a: 'np.ndarray', kx: int, ky: int, ox: int = 0, oy: int = 0) -> 'np.ndarray':
    """Downsample by picking the modal color in each kx-by-ky block.

    This is robust to small variations inside a block (e.g. due to compression
    or slight anti-aliasing) because it picks the most common pixel color.
    """
    H: int = int(a.shape[0]); W: int = int(a.shape[1])
    h0 = H - oy; w0 = W - ox
    true_h = h0 // ky; true_w = w0 // kx
    sub = a[oy:oy + true_h*ky, ox:ox + true_w*kx]
    blocks = sub.reshape(true_h, ky, true_w, kx, -1)
    out = np.zeros((true_h, true_w, a.shape[2]), dtype=a.dtype)
    for i in range(true_h):
        for j in range(true_w):
            block = blocks[i, :, j, :, :].reshape(-1, a.shape[2])
            tuples = [tuple(x) for x in block]
            col = max(set(tuples), key=tuples.count)
            out[i, j] = np.array(col, dtype=a.dtype)
    return out


def estimate_period(a: np.ndarray, axis: int = 1, min_period: int = 2) -> int:
    """Estimate repeating spatial period using autocorrelation of edges.

    The function converts the image to a 1D edge-strength signal and
    looks for local peaks in the autocorrelation. It prefers the smallest
    significant peak (the fundamental period) to avoid harmonics.
    """
    gray: np.ndarray = (a.mean(axis=2)).astype(int) if a.ndim == 3 else a  # type: ignore
    if axis == 1:
        sig = np.abs(np.diff(gray, axis=1)).sum(axis=0)
    else:
        sig = np.abs(np.diff(gray, axis=0)).sum(axis=1)
    ac = np.correlate(sig - sig.mean(), sig - sig.mean(), mode='full')
    ac = ac[len(ac)//2 + 1:]
    if len(ac) == 0:
        return 1
    peaks: List[int] = []
    for i in range(1, len(ac) - 1):
        if ac[i] > ac[i - 1] and ac[i] > ac[i + 1]:
            peaks.append(int(i + 1))
    if not peaks:
        return max(1, int(np.argmax(ac)) + 1)
    maxv = ac.max()
    thresh = maxv * 0.2
    significant: List[int] = [int(p) for p in peaks if ac[int(p) - 1] >= thresh and int(p) >= min_period]
    if significant:
        return int(min(significant))
    small_peaks: List[int] = [int(p) for p in peaks if int(p) >= min_period]
    return int(min(small_peaks)) if small_peaks else max(1, int(np.argmax(ac)) + 1)


def process_file(path: str, out_dir: Optional[str] = None, out_name: Optional[str] = None, threshold: int = 245, tolerance: int = 0, require_square: bool = False, max_checks: int = 1000, write_downsample: bool = True, verbose: bool = True) -> Dict[str, Any]:
    p = Path(path)
    im = Image.open(p).convert('RGB')
    arr = np.array(im)

    cropped = crop_whitespace_array(arr, threshold=threshold)

    # Remove background (make transparent) using a small tolerance.
    # For downsampling/detection we use RGB cropped; later we may save RGBA.
    rgba = remove_background(cropped, tolerance=10)
    rgb_for_detection = rgba[..., :3]

    kx, ky = find_integer_block_scale(cropped, require_square=require_square, tolerance=tolerance, max_checks=max_checks)
    if kx > 1 and ky > 1:
        scale_x = kx
        scale_y = ky
    else:
        scale_x = estimate_period(cropped, axis=1)
        scale_y = estimate_period(cropped, axis=0)

    true_w = cropped.shape[1] // scale_x
    true_h = cropped.shape[0] // scale_y

    if out_name:
        out_base = out_name
    else:
        out_base = p.stem + f'_{true_w}x{true_h}'

    # ensure output directory exists
    if out_dir:
        out_dir_p = Path(out_dir)
        out_dir_p.mkdir(parents=True, exist_ok=True)
        out_path = out_dir_p / (out_base + '.png')
    else:
        out_path = p.with_name(out_base + '.png')

    if verbose:
        print(f'{p.name}: scale {scale_x}x{scale_y} -> {true_w}x{true_h}, saving {out_path.name}')

    if write_downsample:
        # Downsample using the RGB data (ignore alpha for mode selection)
        small = downsample_mode(rgb_for_detection, scale_x, scale_y)
        # map small into RGBA by checking if corresponding block was fully transparent
        # build alpha map at block-level
        H, W = cropped.shape[0], cropped.shape[1]
        true_h = H // scale_y
        true_w = W // scale_x
        alpha_out = np.zeros((true_h, true_w), dtype=np.uint8)
        # compute block alpha: if majority of block pixels opaque -> opaque
        for i in range(true_h):
            for j in range(true_w):
                block = rgba[i*scale_y:(i+1)*scale_y, j*scale_x:(j+1)*scale_x, 3]
                alpha_out[i, j] = 255 if np.mean(block) > 127 else 0

        # compose final image based on output extension: prefer PNG to keep alpha
        ext = out_path.suffix.lower().lstrip('.')
        if ext == 'png':
            out_arr = np.zeros((true_h, true_w, 4), dtype=np.uint8)
            out_arr[..., :3] = small
            out_arr[..., 3] = alpha_out
            out_im = Image.fromarray(out_arr, mode='RGBA')
            out_im.save(out_path)
        else:
            # composite over white background and save as RGB
            rgb_out = small.copy()
            mask3 = (alpha_out[..., None] == 0)
            rgb_out[mask3] = 255
            out_im = Image.fromarray(rgb_out.astype('uint8'), 'RGB')
            out_im.save(out_path)

    return {'scale_x': scale_x, 'scale_y': scale_y, 'true_w': true_w, 'true_h': true_h, 'out': str(out_path)}


def cli():
    epilog = (
        'Examples:\n'
        '  python3 truescaler.py input.heic\n'
        '  python3 truescaler.py input.png --out-dir downsamples/ --output myname\n'
        "  python3 truescaler.py *.png --no-save  # just report scales\n"
        '  python3 truescaler.py images/ --no-prgresss  # disable progress bar\n'
        'JSON API examples:\n'
        "  python3 truescaler.py --json '{\"inputs\":[\"a.png\"],\"out_dir\":\"outs\",\"out_format\":\"bmp\"}' --json-log\n"
        '  JSON keys: inputs,out_dir,output,threshold,tolerance,require_square,max_checks,no_save,recursive,out_format,progress,prgresss\n'
    )

    parser = argparse.ArgumentParser(
        description='Detect pixel-art scale, crop whitespace/background, and downsample to true pixel size.',
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
    parser.add_argument('--json-file', help='Path to JSON argument object file (mutually exclusive with --json).')
    parser.add_argument('--json-log', action='store_true', help='Emit results as JSON only (no progress/status lines).')

    parser.add_argument(
        '--recursive',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Recursively search directories when input is a directory (default: True)',
    )
    parser.add_argument('--extensions', default='png,jpg,jpeg,bmp,heic,webp', help='Comma-separated list of extensions to include when searching directories (default: png,jpg,jpeg,bmp,heic,webp)')
    parser.add_argument('--out-format', default='png', help='Output image format: png or bmp (default: png)')
    parser.add_argument('--prgresss', '--progress', dest='progress', action='store_true', default=True, help='Show progress bar while processing (default: True)')
    parser.add_argument('--no-prgresss', '--no-progress', dest='progress', action='store_false', help='Disable progress bar output')

    args = parser.parse_args()

    if args.json and args.json_file:
        parser.error("--json and --json-file are mutually exclusive; provide only one.")

    def load_json_payload() -> Optional[Dict[str, Any]]:
        payload_obj: Any
        if args.json_file:
            try:
                with open(args.json_file, 'r', encoding='utf8') as f:
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
        return cast(Dict[str, Any], payload_obj)

    def validate_json_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        allowed_keys = {
            'inputs', 'out_dir', 'output', 'threshold', 'tolerance',
            'require_square', 'max_checks', 'no_save', 'recursive', 'out_format', 'progress', 'prgresss',
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
            if expected == 'inputs':
                items = cast(List[object], val) if isinstance(val, list) else []
                if not isinstance(val, list) or any(not isinstance(x, str) for x in items):
                    parser.error("JSON key 'inputs' must be a list of strings.")
            elif expected == 'str':
                if not isinstance(val, str):
                    parser.error(f"JSON key '{key}' must be a string.")
            elif expected == 'int':
                if not isinstance(val, int) or isinstance(val, bool):
                    parser.error(f"JSON key '{key}' must be an integer.")
            elif expected == 'bool':
                if not isinstance(val, bool):
                    parser.error(f"JSON key '{key}' must be a boolean.")

        ensure_type('inputs', 'inputs')
        ensure_type('out_dir', 'str')
        ensure_type('output', 'str')
        ensure_type('out_format', 'str')
        ensure_type('threshold', 'int')
        ensure_type('tolerance', 'int')
        ensure_type('max_checks', 'int')
        ensure_type('require_square', 'bool')
        ensure_type('no_save', 'bool')
        ensure_type('recursive', 'bool')
        ensure_type('progress', 'bool')
        ensure_type('prgresss', 'bool')
        return payload

    def resolve_output_format(raw_format: str) -> Tuple[str, str]:
        fmt = raw_format.strip().lower()
        allowed = {'png', 'bmp'}
        if fmt not in allowed:
            parser.error(f"Unsupported --out-format '{raw_format}'. Supported formats: png,bmp")
        return fmt, fmt

    def print_progress(done: int, total: int, width: int = 32) -> None:
        if total <= 0:
            return
        ratio = max(0.0, min(1.0, float(done) / float(total)))
        filled = int(width * ratio)
        bar = '#' * filled + '-' * (width - filled)
        print(f"\rProgress [{bar}] {done}/{total}", end='', flush=True)
        if done >= total:
            print()

    # Merge JSON input (if provided) into args
    json_payload = load_json_payload()
    if json_payload is not None:
        json_payload = validate_json_payload(json_payload)

    if json_payload is not None:
        # JSON may contain: inputs, out_dir, output, threshold, tolerance, require_square, max_checks, no_save
        inputs = json_payload.get('inputs', [])
        out_dir = json_payload.get('out_dir', args.out_dir)
        output = json_payload.get('output', args.output)
        threshold = json_payload.get('threshold', args.threshold)
        tolerance = json_payload.get('tolerance', args.tolerance)
        require_square = json_payload.get('require_square', args.require_square)
        max_checks = json_payload.get('max_checks', args.max_checks)
        no_save = json_payload.get('no_save', args.no_save)
        recursive = json_payload.get('recursive', args.recursive)
        out_format = json_payload.get('out_format', args.out_format)
        progress = json_payload.get('progress', json_payload.get('prgresss', args.progress))
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

    out_fmt, out_ext = resolve_output_format(str(out_format))

    if not inputs:
        parser.error('No input files provided (use positional inputs or --json/--json-file).')

    # expand directories if requested
    def find_images_in_dir(d: str, exts: List[str], recursive: bool) -> List[str]:
        res: List[str] = []
        for root, _dirs, files in os.walk(d):
            for f in files:
                if any(f.lower().endswith('.' + e) for e in exts):
                    res.append(os.path.join(root, f))
            if not recursive:
                break
        return res

    work_items: List[str] = []
    exts = [e.strip().lower() for e in args.extensions.split(',') if e.strip()]
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
        # build output filename as ${original_name}_${width}x${height}.${ext} (process_file will append)
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
        )
        # rename/convert result to include requested format if we actually saved
        if not no_save:
            out_path = Path(res['out'])
            final_name = f"{Path(path).stem}_{res['true_w']}x{res['true_h']}.{out_ext}"
            final_path = out_path.with_name(final_name)
            # If output already has the final name/format, avoid deleting and reopening it.
            if final_path != out_path:
                if final_path.exists():
                    final_path.unlink()
                with Image.open(out_path) as im:
                    if out_fmt == 'png':
                        im.save(final_path)
                    else:
                        if im.mode == 'RGBA':
                            bg = Image.new('RGB', im.size, (255, 255, 255))
                            bg.paste(im, mask=im.split()[3])
                            bg.save(final_path)
                        else:
                            im.save(final_path)
            # remove intermediate file if name changed
            if str(final_path) != res['out']:
                try:
                    Path(res['out']).unlink()
                except Exception:
                    pass
            if not args.json_log and not show_progress:
                print(f"{Path(path).name}: scale {res['scale_x']}x{res['scale_y']} -> {res['true_w']}x{res['true_h']}, saved {final_path}")
            results.append({'input': path, 'output': str(final_path), 'scale_x': res['scale_x'], 'scale_y': res['scale_y'], 'true_w': res['true_w'], 'true_h': res['true_h']})
        else:
            # no_save: don't try to open or convert files, just report
            if not args.json_log and not show_progress:
                print(f"{Path(path).name}: scale {res['scale_x']}x{res['scale_y']} -> {res['true_w']}x{res['true_h']}, no output (--no-save)")
            results.append({'input': path, 'output': res.get('out'), 'scale_x': res['scale_x'], 'scale_y': res['scale_y'], 'true_w': res['true_w'], 'true_h': res['true_h']})
        if show_progress:
            print_progress(idx, total)

    if args.json_log:
        print(json.dumps(results, indent=2))
    else:
        return results


if __name__ == '__main__':
    cli()
