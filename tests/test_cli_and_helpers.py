import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Load truescaler module by path
spec = importlib.util.spec_from_file_location('truescaler', str(Path(__file__).resolve().parent.parent / 'truescaler.py'))
if spec is None or spec.loader is None:
    raise ImportError('Could not load truescaler.py for tests')
truescaler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(truescaler)
SCRIPT = str(Path(__file__).resolve().parent.parent / 'truescaler.py')


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _make_scaled_image(path: Path) -> None:
    true = np.array([[[255, 0, 0], [0, 255, 0]], [[0, 0, 255], [255, 255, 0]]], dtype=np.uint8)
    k = 6
    img = np.repeat(np.repeat(true, k, axis=0), k, axis=1)
    Image.fromarray(img).save(path)


def _make_nested_image_tree(root: Path, ext: str = 'png') -> tuple[Path, Path]:
    root_img = root / f'root_image.{ext}'
    nested_dir = root / 'nested'
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_img = nested_dir / f'nested_image.{ext}'
    _make_scaled_image(root_img)
    _make_scaled_image(nested_img)
    return root_img, nested_img


def test_process_file_wrapper_contract(tmp_path: Path) -> None:
    p = tmp_path / 'contract.bmp'
    _make_scaled_image(p)
    out_dir = tmp_path / 'out_contract'
    out_dir.mkdir()
    res = truescaler.process_file(str(p), out_dir=str(out_dir), write_downsample=True, verbose=False)
    assert set(res.keys()) == {'scale_x', 'scale_y', 'true_w', 'true_h', 'out'}
    assert Path(str(res['out'])).exists()


def test_cli_no_save_and_json(tmp_path: Path) -> None:
    p = tmp_path / 'cli_test.bmp'
    _make_scaled_image(p)

    cmd = [sys.executable, SCRIPT, str(p), '--no-save', '--no-prgresss']
    r = _run(cmd)
    assert r.returncode == 0
    assert 'scale' in r.stdout.lower()

    payload = {'inputs': [str(p)], 'no_save': True, 'progress': False}
    cmd = [sys.executable, SCRIPT, '--json', json.dumps(payload)]
    r2 = _run(cmd)
    assert r2.returncode == 0
    assert 'scale' in r2.stdout.lower()


def test_cli_progress_default_shows_progress_bar(tmp_path: Path) -> None:
    p = tmp_path / 'progress_default.bmp'
    _make_scaled_image(p)
    r = _run([sys.executable, SCRIPT, str(p)])
    assert r.returncode == 0
    assert 'Progress [' in r.stdout
    assert '1/1' in r.stdout


def test_cli_no_progress_shows_status_line(tmp_path: Path) -> None:
    p = tmp_path / 'no_progress.bmp'
    _make_scaled_image(p)
    r = _run([sys.executable, SCRIPT, str(p), '--no-prgresss'])
    assert r.returncode == 0
    assert 'scale' in r.stdout.lower()
    assert 'Progress [' not in r.stdout


def test_cli_json_log_pure_json_even_with_progress_enabled(tmp_path: Path) -> None:
    p = tmp_path / 'json_log.bmp'
    _make_scaled_image(p)
    payload = {'inputs': [str(p)], 'out_dir': str(tmp_path / 'out_json_log'), 'out_format': 'bmp', 'prgresss': True}
    r = _run([sys.executable, SCRIPT, '--json', json.dumps(payload), '--json-log'])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert isinstance(data, list) and len(data) == 1
    assert data[0]['output'].lower().endswith('.bmp')
    assert 'Progress [' not in r.stdout
    assert r.stderr == ''


def test_cli_directory_recursive_default(tmp_path: Path) -> None:
    in_dir = tmp_path / 'in_recursive'
    in_dir.mkdir()
    _make_nested_image_tree(in_dir, ext='png')
    out_dir = tmp_path / 'out_recursive'
    r = _run([sys.executable, SCRIPT, str(in_dir), '--out-dir', str(out_dir), '--no-prgresss'])
    assert r.returncode == 0
    outs = list(out_dir.glob('*'))
    assert len(outs) == 2


def test_cli_no_recursive_limits_to_top_level(tmp_path: Path) -> None:
    in_dir = tmp_path / 'in_no_recursive'
    in_dir.mkdir()
    _make_nested_image_tree(in_dir, ext='png')
    out_dir = tmp_path / 'out_no_recursive'
    r = _run([sys.executable, SCRIPT, str(in_dir), '--no-recursive', '--out-dir', str(out_dir), '--no-prgresss'])
    assert r.returncode == 0
    outs = list(out_dir.glob('*'))
    assert len(outs) == 1


def test_cli_json_progress_alias_precedence(tmp_path: Path) -> None:
    p = tmp_path / 'alias_precedence.bmp'
    _make_scaled_image(p)
    payload = {'inputs': [str(p)], 'no_save': True, 'progress': False, 'prgresss': True}
    r = _run([sys.executable, SCRIPT, '--json', json.dumps(payload)])
    assert r.returncode == 0
    assert 'Progress [' not in r.stdout
    assert 'scale' in r.stdout.lower()


def test_cli_json_and_json_file_conflict(tmp_path: Path) -> None:
    jf = tmp_path / 'args.json'
    jf.write_text('{"inputs":[]}', encoding='utf8')
    cmd = [sys.executable, SCRIPT, '--json', '{"inputs":[]}', '--json-file', str(jf)]
    r = _run(cmd)
    assert r.returncode != 0
    assert 'mutually exclusive' in r.stderr.lower()


def test_cli_invalid_json_string_rejected() -> None:
    r = _run([sys.executable, SCRIPT, '--json', '{"inputs":[' ])
    assert r.returncode != 0
    assert 'invalid json in --json' in r.stderr.lower()


def test_cli_invalid_json_file_rejected(tmp_path: Path) -> None:
    jf = tmp_path / 'bad.json'
    jf.write_text('{"inputs":[', encoding='utf8')
    r = _run([sys.executable, SCRIPT, '--json-file', str(jf)])
    assert r.returncode != 0
    assert 'invalid json in --json-file' in r.stderr.lower()


def test_cli_missing_json_file_rejected(tmp_path: Path) -> None:
    jf = tmp_path / 'missing.json'
    r = _run([sys.executable, SCRIPT, '--json-file', str(jf)])
    assert r.returncode != 0
    assert 'json file not found' in r.stderr.lower()


def test_cli_json_unknown_key_rejected(tmp_path: Path) -> None:
    p = tmp_path / 'cli_test.bmp'
    _make_scaled_image(p)
    payload = {'inputs': [str(p)], 'no_save': True, 'bogus': 123}
    cmd = [sys.executable, SCRIPT, '--json', json.dumps(payload)]
    r = _run(cmd)
    assert r.returncode != 0
    assert 'unknown keys in json payload' in r.stderr.lower()


def test_cli_json_type_mismatch_rejected(tmp_path: Path) -> None:
    p = tmp_path / 'cli_test.bmp'
    _make_scaled_image(p)
    payload = {'inputs': str(p), 'no_save': 'yes'}
    cmd = [sys.executable, SCRIPT, '--json', json.dumps(payload)]
    r = _run(cmd)
    assert r.returncode != 0
    assert "json key 'inputs' must be a list of strings" in r.stderr.lower()


def test_cli_json_out_format_bmp_and_jpg_rejected(tmp_path: Path) -> None:
    p = tmp_path / 'cli_test.bmp'
    _make_scaled_image(p)

    out_dir = tmp_path / 'out_bmp'
    ok_payload = {'inputs': [str(p)], 'out_dir': str(out_dir), 'out_format': 'bmp'}
    ok_cmd = [sys.executable, SCRIPT, '--json', json.dumps(ok_payload)]
    ok = _run(ok_cmd)
    assert ok.returncode == 0
    assert any(x.suffix.lower() == '.bmp' for x in out_dir.iterdir())

    bad_payload = {'inputs': [str(p)], 'out_format': 'jpg'}
    bad_cmd = [sys.executable, SCRIPT, '--json', json.dumps(bad_payload)]
    bad = _run(bad_cmd)
    assert bad.returncode != 0
    assert 'supported formats: png,bmp' in bad.stderr.lower()
