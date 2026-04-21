r"""SecureLifeAI - Backend Contents Viewer

Prints a human-readable snapshot of the SQLite backend (schema + sample rows).

Why this exists:
- Quick local inspection while debugging.
- Avoids exposing any debug/admin endpoint in the Flask app.

Usage:
  .\.venv\Scripts\python.exe view_backend_contents.py
  .\.venv\Scripts\python.exe view_backend_contents.py --table profiles --limit 20

Notes:
- Sensitive columns (e.g., password hashes) are redacted.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from typing import Iterable, List, Sequence, Tuple


DEFAULT_DB_PATH = "insurance.db"
REDACT_KEYS = ("password", "hash", "secret", "token")


def _ensure_utf8_output() -> None:
    """Avoid Windows console encoding errors when printing (e.g., ₹)."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # If reconfigure isn't supported or fails, keep default behavior.
        pass


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _list_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def _table_columns(conn: sqlite3.Connection, table: str) -> List[Tuple[str, str]]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    # Each row: cid, name, type, notnull, dflt_value, pk
    return [(r["name"], r["type"]) for r in rows]


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(1) AS n FROM {table}").fetchone()
    return int(row["n"]) if row else 0


def _should_redact(column_name: str) -> bool:
    col = column_name.lower()
    return any(key in col for key in REDACT_KEYS)


def _redact_row(row: sqlite3.Row, columns: Sequence[str]) -> List[str]:
    out: List[str] = []
    for col in columns:
        val = row[col]
        if _should_redact(col) and val is not None:
            out.append("<redacted>")
        else:
            out.append("" if val is None else str(val))
    return out


def _format_table(columns: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    # Simple fixed-width table.
    rows_list = [list(columns), *[list(r) for r in rows]]
    widths = [max(len(r[i]) for r in rows_list) for i in range(len(columns))]

    def fmt(r: Sequence[str]) -> str:
        return " | ".join((r[i] or "").ljust(widths[i]) for i in range(len(columns)))

    sep = "-+-".join("-" * w for w in widths)
    lines = [fmt(rows_list[0]), sep]
    for r in rows_list[1:]:
        lines.append(fmt(r))
    return "\n".join(lines)


def print_summary(conn: sqlite3.Connection) -> None:
    tables = _list_tables(conn)
    if not tables:
        print("No tables found (is the DB initialized?).")
        return

    print(f"Database: {DEFAULT_DB_PATH}")
    print("Tables:")
    for t in tables:
        n = _row_count(conn, t)
        print(f"- {t}: {n} rows")


def print_schema(conn: sqlite3.Connection, table: str | None) -> None:
    tables = [table] if table else _list_tables(conn)
    for t in tables:
        cols = _table_columns(conn, t)
        print(f"\nSchema: {t}")
        for name, typ in cols:
            print(f"  - {name}: {typ}")


def print_rows(conn: sqlite3.Connection, table: str, limit: int) -> None:
    cols = _table_columns(conn, table)
    col_names = [c[0] for c in cols]

    query = f"SELECT * FROM {table} ORDER BY 1 DESC LIMIT ?"
    fetched = conn.execute(query, (limit,)).fetchall()

    print(f"\nRows: {table} (latest {min(limit, len(fetched))} of {_row_count(conn, table)})")
    if not fetched:
        print("<no rows>")
        return

    safe_rows = [_redact_row(r, col_names) for r in fetched]
    print(_format_table(col_names, safe_rows))


def main() -> int:
    _ensure_utf8_output()
    parser = argparse.ArgumentParser(description="View SecureLifeAI backend SQLite contents")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite DB (default: insurance.db)")
    parser.add_argument("--table", default=None, help="Print only a specific table")
    parser.add_argument("--limit", type=int, default=10, help="Rows to show per table (default: 10)")
    parser.add_argument("--no-schema", action="store_true", help="Skip schema printing")
    parser.add_argument("--no-rows", action="store_true", help="Skip row printing")
    args = parser.parse_args()

    conn = _connect(args.db)
    try:
        print_summary(conn)
        if not args.no_schema:
            print_schema(conn, args.table)

        if not args.no_rows:
            if args.table:
                print_rows(conn, args.table, args.limit)
            else:
                for t in _list_tables(conn):
                    print_rows(conn, t, args.limit)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
