"""Create .env from .env.example if missing (never overwrites)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / ".env.example"
DST = ROOT / ".env"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(".env.example missing")
    if DST.exists():
        print(".env already present")
        return
    DST.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    print("Created .env from .env.example")


if __name__ == "__main__":
    main()
