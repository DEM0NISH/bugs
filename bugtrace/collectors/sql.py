import sqlite3
from pathlib import Path

from bugtrace.models import EvidenceItem
from bugtrace.redaction import redact


def collect(database: Path, query_dir: Path, identifiers: dict[str, str] | None = None) -> list[EvidenceItem]:
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    results = []
    try:
        for query_path in sorted(query_dir.glob("*.sql")):
            query = query_path.read_text(encoding="utf-8").strip()
            if not query.lower().startswith("select") or ";" in query.rstrip(";"):
                raise ValueError(f"Only a single SELECT is allowed: {query_path.name}")
            key = query_path.name
            parameter = identifiers.get(key, "") if identifiers else ""
            parameters = (parameter,) if "?" in query else ()
            rows = [dict(row) for row in connection.execute(query, parameters).fetchall()]
            results.append(EvidenceItem(id=f"E{len(results) + 1}", source="sql", confidence="low", content=redact({"query": query_path.name, "rows": rows})))
    finally:
        connection.close()
    return results
