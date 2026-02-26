import importlib.util
from pathlib import Path
from PIL import Image
import numpy as np
import pillow_heif  # type: ignore

# Dynamically load truescaler.py
spec = importlib.util.spec_from_file_location('truescaler', str(Path(__file__).resolve().parent.parent / 'truescaler.py'))
if spec is None or spec.loader is None:
    raise ImportError('Could not load truescaler.py for tests')
truescaler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(truescaler)

pillow_heif.register_heif_opener()


def _fixture_heic() -> Path:
    base = Path('tests/test-images')
    if not base.exists():
        base = Path('.tests/test-images')
    path = base / 'scaled_4x3_8.HEIC'
    assert path.exists(), f'missing HEIC fixture: {path}'
    return path


def test_heic_fixture_decode_regression(tmp_path: Path) -> None:
    """Verify committed HEIC fixture decodes and scales to known true size."""
    p = _fixture_heic()
    with Image.open(p) as im:
        assert im.size == (32, 24)

    res = truescaler.process_file(str(p), out_dir=str(tmp_path), write_downsample=True, verbose=False)
    assert res['true_w'] == 4 and res['true_h'] == 3
    outp = Path(res['out'])
    assert outp.exists()
    with Image.open(outp) as im:
        assert im.size == (4, 3)


def test_heic_roundtrip(tmp_path: Path) -> None:
    """Create a real HEIC image, process it, and verify downsample."""
    # small true image 13x19 scaled by 48
    w, h = 13, 19
    true = np.zeros((h, w, 3), dtype='uint8')
    for y in range(h):
        for x in range(w):
            true[y, x] = ((x * 19) % 256, (y * 13) % 256, ((x + y) * 7) % 256)
    k = 48
    img = np.repeat(np.repeat(true, k, axis=0), k, axis=1)

    p = tmp_path / 'test_heic.HEIC'
    pil_img = Image.fromarray(img)
    try:
        # Prefer Pillow's registered HEIC writer when available.
        pil_img.save(p, format='HEIC')
    except KeyError:
        # Fallback to pillow_heif native writer API; still writes real HEIC.
        try:
            heif = pillow_heif.from_pillow(pil_img)
            heif.save(str(p))
        except Exception as exc:  # pragma: no cover - env dependent codec support
            raise AssertionError(
                "HEIC encoding is required for test_heic_roundtrip. "
                "Install/enable libheif HEIC encoder support in pillow-heif."
            ) from exc

    res = truescaler.process_file(str(p), out_dir=str(tmp_path), write_downsample=True, verbose=False)
    assert res['true_w'] == w and res['true_h'] == h
    outp = Path(res['out'])
    assert outp.exists()
    im = Image.open(outp)
    assert im.size == (w, h)
