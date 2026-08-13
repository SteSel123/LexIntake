"""CLI entrypoint: initialize LexIntake structured SQLite database."""

from __future__ import annotations

import argparse

from sqlite_db import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize LexIntake structured SQLite DB")
    parser.add_argument(
        "--db-path",
        default=None,
        help="Optional path to sqlite file (default: db/lexintake.db)",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Create tables only; do not seed from kb/",
    )
    args = parser.parse_args()
    result = init_db(db_path=args.db_path, seed=not args.no_seed)
    print(f"SQLite ready at {result['db_path']}")
    print(f"seeded={result['seeded']}")
    print(f"counts={result['counts']}")


if __name__ == "__main__":
    main()
