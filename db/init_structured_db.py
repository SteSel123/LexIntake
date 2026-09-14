"""CLI: initialize LexIntake PostgreSQL schema and seed from kb/.

Run after setting ``DATABASE_URL`` to apply Alembic migrations and optionally
load structured reference data from the ``kb/`` JSON fixtures.
"""

from __future__ import annotations

import argparse

from db.structured_db import init_db


def main() -> None:
    """Parse flags and invoke ``init_db`` with optional seeding."""
    parser = argparse.ArgumentParser(
        description="Initialize LexIntake PostgreSQL DB (requires DATABASE_URL)"
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Create tables only; do not seed from kb/",
    )
    args = parser.parse_args()
    result = init_db(seed=not args.no_seed)
    print("PostgreSQL ready")
    print(f"url={result['database_url']}")
    print(f"seeded={result['seeded']}")
    print(f"counts={result['counts']}")


if __name__ == "__main__":
    main()
