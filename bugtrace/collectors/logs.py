import json
from pathlib import Path

from bugtrace.models import EvidenceItem
from bugtrace.redaction import redact


def collect(path: Path, request_id: str, start_index: int = 1) -> tuple[list[EvidenceItem], int]:
    items = []
    skipped = 0
    if not path.exists():
        return items, skipped
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(event, dict):
            skipped += 1
            continue
        if event.get("request_id") != request_id:
            continue
        items.append(EvidenceItem(id=f"E{start_index + len(items)}", source="log", timestamp=event.get("ts", ""), confidence="high", content=redact(event)))
    return items, skipped
