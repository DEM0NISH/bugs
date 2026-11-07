from pathlib import Path
from datetime import date, datetime

import yaml

from bugtrace.models import BugReport


FIELDS = ("title", "environment", "endpoint", "method", "headers", "body", "request_id", "expected", "actual", "reported_at")


def load_report(path: Path) -> BugReport:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(data.get("reported_at"), (date, datetime)):
        data["reported_at"] = data["reported_at"].isoformat()
    missing = [field for field in FIELDS if field not in data]
    data["needs_info"] = missing
    return BugReport.model_validate(data)
