"""One-shot Docker init: seed structured DB then run the KB ETL pipeline.

Invoked by the ``init`` Compose service so Postgres is populated before API/UI start.
"""
from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """Run init_structured_db and etl.pipeline sequentially; fail fast on error."""
    steps = [
        [sys.executable, "-m", "db.init_structured_db"],
        [sys.executable, "-m", "etl.pipeline"],
    ]
    for cmd in steps:
        print("+", " ".join(cmd), flush=True)
        subprocess.check_call(cmd)
    print("Init complete.", flush=True)


if __name__ == "__main__":
    main()
