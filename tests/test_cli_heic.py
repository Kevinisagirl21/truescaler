import json
import subprocess
import sys
import shutil
from pathlib import Path

import pillow_heif  # type: ignore
from PIL import Image

SCRIPT = str(Path(__file__).resolve().parent.parent / 'truescaler.py')

pillow_heif.register_heif_opener()


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _fixture_heic() -> Path:
    base = Path('tests/test-images')
    if not base.exists():
        base = Path('.tests/test-images')
    path = base / 'scaled_4x3_8.HEIC'
    assert path.exists(), f'missing HEIC fixture: {path}'
    return path


def _copy_fixture_heic(path: Path) -> None:
    shutil.copy2(_fixture_heic(), path)


def test_cli_heic_single_file_processing(tmp_path: Path) -> None:
    p = tmp_path / 'single.HEIC'
    _copy_fixture_heic(p)
    out_dir = tmp_path / 'out_heic_single'
    r = _run([sys.executable, SCRIPT, str(p), '--out-dir', str(out_dir), '--no-prgresss'])
    assert r.returncode == 0
    outs = list(out_dir.glob('*'))
    assert len(outs) == 1
    with Image.open(outs[0]) as im:
        assert im.size == (4, 3)


def test_cli_heic_recursive_directory_processing(tmp_path: Path) -> None:
    in_dir = tmp_path / 'in_heic_recursive'
    in_dir.mkdir()
    root_heic = in_dir / 'root_heic.HEIC'
    nested_dir = in_dir / 'nested'
    nested_dir.mkdir()
    nested_heic = nested_dir / 'nested_heic.HEIC'
    _copy_fixture_heic(root_heic)
    _copy_fixture_heic(nested_heic)

    out_dir = tmp_path / 'out_heic_recursive'
    r = _run([sys.executable, SCRIPT, str(in_dir), '--out-dir', str(out_dir), '--no-prgresss'])
    assert r.returncode == 0
    outs = list(out_dir.glob('*'))
    assert len(outs) == 2


def test_cli_heic_json_mode_with_bmp_output(tmp_path: Path) -> None:
    p = tmp_path / 'json_heic.HEIC'
    _copy_fixture_heic(p)
    out_dir = tmp_path / 'out_heic_json_bmp'
    payload = {'inputs': [str(p)], 'out_dir': str(out_dir), 'out_format': 'bmp', 'progress': False}
    r = _run([sys.executable, SCRIPT, '--json', json.dumps(payload)])
    assert r.returncode == 0
    outs = list(out_dir.glob('*'))
    assert len(outs) == 1
    assert outs[0].suffix.lower() == '.bmp'
