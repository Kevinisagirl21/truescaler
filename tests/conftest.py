from __future__ import annotations

import pytest


def pytest_sessionstart(session) -> None:
    try:
        import _truescaler_core  # noqa: F401
    except Exception as exc:
        pytest.exit(
            "Required native backend '_truescaler_core' is not importable. "
            "Build/install it before running tests with: python -m pip install -e .",
            returncode=2,
        )
