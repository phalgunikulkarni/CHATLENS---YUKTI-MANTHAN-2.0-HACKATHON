"""Minimal additive column-ensure for account-scoped chat persistence (Phase B).

`models.Base.metadata.create_all(bind=engine)` creates the new
`search_result_refs` table and, for a fresh DB, all new columns. But
`create_all` does NOT ALTER pre-existing tables to add newly declared columns
to an already-existing `chatlens.db`. This module fills only that gap:

- It inspects each affected table with `PRAGMA table_info` and issues
  `ALTER TABLE ... ADD COLUMN` ONLY for columns that are missing.
- It is strictly additive: it never drops or recreates a table, never deletes a
  row, and never fabricates ownership (new columns default to NULL for
  pre-existing rows).
- On any failure it aborts, leaving existing data byte-for-byte intact, and
  re-raises so startup can surface the error (the caller decides whether to
  proceed).

NOTE: This is the SMALL, self-contained additive column-ensure needed for Phase
B to function. The FULL migration module (safe SQLite/Chroma/authorized-locations
migration, task 8.1) is deferred to Phase H and is intentionally NOT implemented
here.
"""

from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Tables that gained additive columns in Phase B, mapped to the columns to
# ensure and their SQLite column type. Only these get ALTERed, only when missing.
_ADDITIVE_COLUMNS: Dict[str, List[tuple]] = {
    "search_sessions": [("account_id", "VARCHAR"), ("title", "VARCHAR")],
    "search_messages": [("account_id", "VARCHAR")],
    "search_contexts": [("account_id", "VARCHAR")],
    "images": [("account_id", "VARCHAR")],
}


def _existing_columns(conn, table: str) -> List[str]:
    """Return column names for `table`, or [] if the table does not exist."""
    rows = conn.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
    # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
    return [r[1] for r in rows]


def ensure_account_columns(engine: Engine) -> None:
    """Add missing account_id/title columns to pre-existing tables (additive).

    Aborts on failure without modifying data, then re-raises.
    """
    try:
        with engine.begin() as conn:
            for table, columns in _ADDITIVE_COLUMNS.items():
                present = _existing_columns(conn, table)
                if not present:
                    # Table does not exist yet; create_all() will build it with
                    # the new columns already present. Nothing to ALTER.
                    continue
                for col_name, col_type in columns:
                    if col_name in present:
                        continue  # already present — do not re-add (idempotent)
                    conn.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN {col_name} {col_type}')
                    )
    except Exception:
        # Leave existing data unchanged (no drop/recreate anywhere above) and
        # surface the error to the caller.
        raise
