#!/usr/bin/env python3
"""Combined pixel-art scaler and whitespace cropper CLI.

Usage examples:
  python3 find_scale.py input.heic
  python3 find_scale.py input.png --output name --out-dir downsamples/
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import argparse
import math

import numpy as np
from PIL import Image

try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pillow_heif: Any = None


def run_lengths_line(line: np.ndarray) -> List[int]:
    """Return run-lengths of consecutive identical pixels in a 1D line."""
    lengths: List[int] = []
    prev = tuple(int(v) for v in line[0])
    count = 1
    for pix in line[1:]:
        p = tuple(int(v) for v in pix)
        if p == prev:
            count += 1
        else:
            lengths.append(count)
            count = 1
            prev = p
    lengths.append(count)
    return lengths


def detect_scale(arr: np.ndarray, axis: int = 1) -> int:
    """Estimate a 1D scale (pixels per true pixel) along axis."""
    lengths: List[int] = []
    if axis == 1:
        for row in arr:
            lengths.extend(run_lengths_line(row))
    else:
        for c in range(int(arr.shape[1])):
            col = arr[:, c]
            lengths.extend(run_lengths_line(col))

    if not lengths:
        return 1

    cnt: Any = Counter(lengths)
    candidates: Dict[int, int] = {int(l): int(c) for l, c in cnt.items() if int(l) > 1}
    if not candidates:
        return 1

    mode_len, _ = max(candidates.items(), key=lambda x: x[1])
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


def find_integer_block_scale(
    arr: np.ndarray,
    require_square: bool = False,
    tolerance: int = 0,
    max_checks: int = 1000,
) -> Tuple[int, int]:
    """Try to find integer block size (kx, ky) where each block is uniform."""
    h: int = int(arr.shape[0])
    w: int = int(arr.shape[1])
    div_w = divisors(w)
    div_h = divisors(h)
    div_w.sort(reverse=True)
    div_h.sort(reverse=True)

    checks = 0
    for k in div_w:
        for kk in div_h:
            if require_square and k != kk:
                continue
            if k == 1 and kk == 1:
                continue
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
                        sub = arr[oy: oy + true_h * kk, ox: ox + true_w * k]
                        blocks = sub.reshape(true_h, kk, true_w, k, -1)
                    except Exception:
                        continue
                    first = blocks[:, :1, :, :1, :]
                    if tolerance == 0:
                        ok = np.all(blocks == first, axis=(1, 3, 4))
                        if bool(ok.all()):
                            return k, kk
                    else:
                        diffs = np.max(np.abs(blocks - first), axis=(1, 3, 4))
                        if bool(np.all(diffs <= tolerance)):
                            return k, kk
    return 1, 1


def crop_whitespace_array(arr: np.ndarray, threshold: int = 245) -> np.ndarray:
    """Crop near-white border from an RGB numpy array and return the cropped array."""
    non_white_mask = np.any(arr < threshold, axis=2)
    rows = np.any(non_white_mask, axis=1)
    cols = np.any(non_white_mask, axis=0)
    if not bool(rows.any()) or not bool(cols.any()):
        return arr
    row_min, row_max = np.where(rows)[0][[0, -1]]
    col_min, col_max = np.where(cols)[0][[0, -1]]
    return arr[int(row_min):int(row_max) + 1, int(col_min):int(col_max) + 1]


def downsample_mode(a: np.ndarray, kx: int, ky: int, ox: int = 0, oy: int = 0) -> np.ndarray:
    """Downsample by picking the modal color in each kx-by-ky block."""
    h: int = int(a.shape[0])
    w: int = int(a.shape[1])
    h0 = h - oy
    w0 = w - ox
    true_h = h0 // ky
    true_w = w0 // kx
    sub = a[oy:oy + true_h * ky, ox:ox + true_w * kx]
    blocks = sub.reshape(true_h, ky, true_w, kx, -1)
    out = np.zeros((true_h, true_w, int(a.shape[2])), dtype=a.dtype)
    for i in range(true_h):
        for j in range(true_w):
            block = blocks[i, :, j, :, :].reshape(-1, int(a.shape[2]))
            tuples = [tuple(int(v) for v in x) for x in block]
            col = max(set(tuples), key=tuples.count)
            out[i, j] = np.array(col, dtype=a.dtype)
    return out


def estimate_period(a: np.ndarray, axis: int = 1, min_period: int = 2) -> int:
    """Estimate repeating spatial period using autocorrelation of edges."""
    gray: np.ndarray = (a.mean(axis=2)).astype(int) if a.ndim == 3 else a
    if axis == 1:
        sig = np.abs(np.diff(gray, axis=1)).sum(axis=0)
    else:
        sig = np.abs(np.diff(gray, axis=0)).sum(axis=1)
    ac = np.correlate(sig - sig.mean(), sig - sig.mean(), mode='full')
    ac = ac[len(ac) // 2 + 1:]
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


def process_file(
    path: str,
    out_dir: Optional[str] = None,
    out_name: Optional[str] = None,
    threshold: int = 245,
    tolerance: int = 0,
    require_square: bool = False,
    max_checks: int = 1000,
    write_downsample: bool = True,
) -> Dict[str, Any]:
    p = Path(path)
    im = Image.open(p).convert('RGB')
    arr = np.array(im)

    cropped = crop_whitespace_array(arr, threshold=threshold)

    kx, ky = find_integer_block_scale(cropped, require_square=require_square, tolerance=tolerance, max_checks=max_checks)
    if kx > 1 and ky > 1:
        scale_x = kx
        scale_y = ky
    else:
        scale_x = estimate_period(cropped, axis=1)
        scale_y = estimate_period(cropped, axis=0)

    true_w = int(cropped.shape[1] // scale_x)
    true_h = int(cropped.shape[0] // scale_y)

    if out_name:
        out_base = out_name
    else:
        out_base = p.stem + f'_{true_w}x{true_h}'

    if out_dir:
        out_dir_p = Path(out_dir)
        out_dir_p.mkdir(parents=True, exist_ok=True)
        out_path = out_dir_p / (out_base + '.png')
    else:
        out_path = p.with_name(out_base + '.png')

    print(f'{p.name}: scale {scale_x}x{scale_y} -> {true_w}x{true_h}, saving {out_path.name}')

    if write_downsample:
        small = downsample_mode(cropped, scale_x, scale_y)
        out_im = Image.fromarray(small.astype('uint8'), 'RGB')
        out_im.save(out_path)

    return {'scale_x': scale_x, 'scale_y': scale_y, 'true_w': true_w, 'true_h': true_h, 'out': str(out_path)}


def cli() -> List[Dict[str, Any]]:
    parser = argparse.ArgumentParser(description='Crop whitespace and detect pixel-art scale, then downsample.')
    parser.add_argument('inputs', nargs='+', help='Input image files (supports HEIC, PNG, JPG, etc.)')
    parser.add_argument('--out-dir', help='Directory to write outputs')
    parser.add_argument('--output', help='Output base name (no ext)')
    parser.add_argument('--threshold', type=int, default=245, help='Whitespace crop threshold (0-255)')
    parser.add_argument('--tolerance', type=int, default=0, help='Color tolerance for integer-block detection')
    parser.add_argument('--require-square', action='store_true', help='Require square blocks')
    parser.add_argument('--max-checks', type=int, default=10000, help='Max checks for block search')
    parser.add_argument('--no-save', action='store_true', help="Don't write downsampled image, just report scale")
    args = parser.parse_args()

    results: List[Dict[str, Any]] = []
    for inp in args.inputs:
        res = process_file(
            inp,
            out_dir=args.out_dir,
            out_name=args.output,
            threshold=args.threshold,
            tolerance=args.tolerance,
            require_square=args.require_square,
            max_checks=args.max_checks,
            write_downsample=not args.no_save,
        )
        results.append(res)
    return results


if __name__ == '__main__':
    cli()
