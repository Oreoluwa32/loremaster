"""Postgres + pgvector connectivity."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector

from .config import Settings, load_settings


def connect(settings: Settings | None = None) -> psycopg.Connection:
    """Open a Postgres connection with pgvector codecs registered."""
    settings = settings or load_settings()
    conn = psycopg.connect(settings.pg_dsn)
    try:
        register_vector(conn)
    except Exception:
        # Vector extension isn't installed yet (e.g. first-time init); the
        # caller will create the extension and re-register afterwards.
        pass
    return conn


@contextmanager
def session(settings: Settings | None = None) -> Iterator[psycopg.Connection]:
    """Connection context manager that commits on success, rolls back on error."""
    conn = connect(settings)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def read_schema_sql() -> str:
    """Return the bundled schema.sql as a string."""
    return resources.files("loremaster").joinpath("schema.sql").read_text(encoding="utf-8")
