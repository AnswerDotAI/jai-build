from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
import runpy

PACKAGE_NAME = "jai-sandbox"


def _source_version() -> str:
    root = Path(__file__).resolve().parents[2]
    helper = root / "tools" / "version.py"
    if helper.exists():
        return runpy.run_path(str(helper))["package_version"]()
    raise RuntimeError(f"Unable to determine source version without {helper}")


try:
    __version__ = package_version(PACKAGE_NAME)
except PackageNotFoundError:
    __version__ = _source_version()
