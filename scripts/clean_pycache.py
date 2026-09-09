"""Remove __pycache__ directories and *.pyc / *.pyo files."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    removed = 0
    for path in ROOT.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)
        removed += 1
    for path in ROOT.rglob("*.py[co]"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    print(f"Cleaned {removed} cache path(s).")


if __name__ == "__main__":
    main()
