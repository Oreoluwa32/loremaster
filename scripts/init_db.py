"""
Apply the Loremaster schema to the configured Postgres database.

Run:  python scripts/init_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loremaster.config import load_settings  # noqa: E402
from loremaster.db import read_schema_sql, session  # noqa: E402


def main() -> None:
    settings = load_settings()
    print(f"Applying schema to {settings.pg_host}:{settings.pg_port}/{settings.pg_db}")

    with session(settings) as conn, conn.cursor() as cur:
        cur.execute(read_schema_sql())

    print("Schema applied.")


if __name__ == "__main__":
    main()
