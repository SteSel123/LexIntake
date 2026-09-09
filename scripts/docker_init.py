"""One-shot container entrypoint: schema seed + ETL into Postgres."""
from __future__ import annotations

import subprocess
import sys


def main() -> None:
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
