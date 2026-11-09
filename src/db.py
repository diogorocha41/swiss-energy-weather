"""DuckDB connection helpers and ingestion bookkeeping."""
import hashlib
from pathlib import Path

import duckdb

from src.config import DB_PATH


def connect(path: Path = DB_PATH, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), read_only=read_only)
    # Store and compute everything in UTC; local time is derived explicitly.
    con.execute("SET TimeZone = 'UTC'")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_log (
            source      VARCHAR,
            file_name   VARCHAR,
            sha256      VARCHAR,
            n_rows      BIGINT,
            loaded_at   TIMESTAMP DEFAULT current_timestamp
        )
        """
    )
    return con


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def already_loaded(con, source: str, path: Path, sha: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM ingest_log WHERE source = ? AND file_name = ? AND sha256 = ? LIMIT 1",
        [source, path.name, sha],
    ).fetchone()
    return row is not None


def log_load(con, source: str, path: Path, sha: str, n_rows: int) -> None:
    con.execute(
        "INSERT INTO ingest_log (source, file_name, sha256, n_rows) VALUES (?, ?, ?, ?)",
        [source, path.name, sha, n_rows],
    )
