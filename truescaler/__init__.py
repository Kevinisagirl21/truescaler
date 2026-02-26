"""Package shim to expose the top-level truescaler.py as an importable module.

This file dynamically loads ../truescaler.py so tests and other code can
`import truescaler`.
"""
from importlib import util
from pathlib import Path
_impl_path = Path(__file__).resolve().parent.parent / 'truescaler.py'
spec = util.spec_from_file_location('truescaler._impl', str(_impl_path))
if spec is None or spec.loader is None:
    raise ImportError(f'Could not load truescaler implementation from {_impl_path}')
_mod = util.module_from_spec(spec)
spec.loader.exec_module(_mod)

# re-export public names
for name, val in vars(_mod).items():
    if not name.startswith('_'):
        globals()[name] = val
