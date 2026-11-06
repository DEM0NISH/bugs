import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def connect(path: str | Path | None = None, initialize_schema: bool = True) -> sqlite3.Connection:
    target = Path(path or os.environ.get("QUOTE_DB_PATH", ".workspace/quote_service.db"))
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if initialize_schema:
        initialize(connection)
    return connection


@contextmanager
def immediate(path: str | Path):
    connection = connect(path, initialize_schema=False)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        "CREATE TABLE IF NOT EXISTS buyers (id TEXT PRIMARY KEY, name TEXT NOT NULL, credit_limit TEXT NOT NULL, credit_reserved TEXT NOT NULL DEFAULT '0.00');"
        "CREATE TABLE IF NOT EXISTS quotes (id TEXT PRIMARY KEY, buyer_id TEXT NOT NULL REFERENCES buyers(id), status TEXT NOT NULL, subtotal TEXT NOT NULL, discount_percent TEXT NOT NULL, discount_amount TEXT NOT NULL, taxable_amount TEXT NOT NULL, gst_amount TEXT NOT NULL, total TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);"
        "CREATE TABLE IF NOT EXISTS quote_lines (id INTEGER PRIMARY KEY, quote_id TEXT NOT NULL REFERENCES quotes(id), quantity INTEGER NOT NULL, unit_price TEXT NOT NULL, description TEXT NOT NULL);"
        "CREATE TABLE IF NOT EXISTS credit_ledger (id INTEGER PRIMARY KEY, buyer_id TEXT NOT NULL REFERENCES buyers(id), quote_id TEXT NOT NULL REFERENCES quotes(id), entry_type TEXT NOT NULL CHECK(entry_type IN ('reserve','release')), amount TEXT NOT NULL, created_at TEXT NOT NULL);"
        "CREATE TABLE IF NOT EXISTS idempotency_keys (key TEXT PRIMARY KEY, quote_id TEXT NOT NULL REFERENCES quotes(id), created_at TEXT NOT NULL);"
    )
    connection.commit()


def seed(connection: sqlite3.Connection) -> None:
    connection.execute("INSERT OR IGNORE INTO buyers(id,name,credit_limit,credit_reserved) VALUES(?,?,?,?)", ("buyer-1", "Sample Buyer", "100000.00", "0.00"))
    connection.commit()
