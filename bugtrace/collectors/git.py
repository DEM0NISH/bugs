import subprocess
from pathlib import Path

from bugtrace.models import EvidenceItem
from bugtrace.redaction import redact


ALLOWED = {"quote_service/main.py", "quote_service/pricing.py", "quote_service/db.py"}


def collect(repository: Path, reference: str, endpoint: str) -> list[EvidenceItem]:
    if endpoint not in {"/quotes", "/quotes/{id}/confirm", "/quotes/{id}/cancel"}:
        return []
    result = subprocess.run(["git", "-C", str(repository), "log", "--format=%H%x09%aI%x09%s", "--name-only", reference], check=True, capture_output=True, text=True, timeout=10)
    items = []
    current = None
    files = []
    for line in result.stdout.splitlines() + [""]:
        if "\t" in line:
            if current is not None and set(files) & ALLOWED:
                commit, timestamp, subject = current
                items.append(EvidenceItem(id=f"E{len(items) + 1}", source="git", timestamp=timestamp, confidence="low", content=redact({"commit": commit[:12], "subject": subject, "files": sorted(set(files) & ALLOWED)})))
            current = tuple(line.split("\t", 2))
            files = []
        elif line.strip():
            files.append(line.strip().replace("\\", "/"))
        elif current is not None:
            if set(files) & ALLOWED:
                commit, timestamp, subject = current
                items.append(EvidenceItem(id=f"E{len(items) + 1}", source="git", timestamp=timestamp, confidence="low", content=redact({"commit": commit[:12], "subject": subject, "files": sorted(set(files) & ALLOWED)})))
            current = None
            files = []
    return items
