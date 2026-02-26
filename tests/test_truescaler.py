from pathlib import Path
from PIL import Image
import importlib.util

# Dynamically load truescaler.py from repo root so tests work under pytest
spec = importlib.util.spec_from_file_location('truescaler', str(Path(__file__).resolve().parent.parent / 'truescaler.py'))
if spec is None or spec.loader is None:
    raise ImportError('Could not load truescaler.py for tests')
truescaler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(truescaler)


def test_process_known_scaled_images(tmp_path: Path):
    # Use the repo test-images created under .tests/test-images
    # test images may live in either 'tests/test-images' or '.tests/test-images'
    base = Path('tests/test-images')
    if not base.exists():
        base = Path('.tests/test-images')
    assert base.exists(), f'no test images found in {base}'

    # Known scaled images should be detected to their true sizes
    cases = [
        ('scaled_13x19_48.png', 13, 19),
        ('scaled_13x19_48.BMP', 13, 19),
        ('scaled_4x3_8.png', 4, 3),
        ('scaled_4x3_8.BMP', 4, 3),
        ('scaled_4x3_8.HEIC', 4, 3),
    ]
    out_dir = tmp_path / 'outs'
    out_dir.mkdir()
    for name, tw, th in cases:
        p = base / name
        assert p.exists(), f'missing test file {p}'
        res = truescaler.process_file(str(p), out_dir=str(out_dir), write_downsample=True, verbose=False)
        assert res['true_w'] == tw and res['true_h'] == th
        outp = Path(res['out'])
        assert outp.exists()
        im = Image.open(outp)
        assert im.size == (tw, th)


def test_process_various_formats_run(tmp_path: Path):
    base = Path('.tests/test-images')
    files = list(base.glob('*'))
    out_dir = tmp_path / 'outs_all'
    out_dir.mkdir()
    # Ensure processing runs for every file and outputs an image
    for f in files:
        res = truescaler.process_file(str(f), out_dir=str(out_dir), write_downsample=True, verbose=False)
        outp = Path(res['out'])
        assert outp.exists()
        im = Image.open(outp)
        # size must be positive
        assert im.size[0] > 0 and im.size[1] > 0
