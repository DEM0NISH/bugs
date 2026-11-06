from bugtrace.models import EvidenceItem


def timeline(items: list[EvidenceItem]) -> list[EvidenceItem]:
    return sorted(items, key=lambda item: (not bool(item.timestamp), item.timestamp or "", item.id))


def gaps(items: list[EvidenceItem], returned_status: int | None) -> list[str]:
    events = {item.content.get("event") for item in items if item.source == "log"}
    missing = []
    if returned_status == 200 and not {"pricing.subtotal", "pricing.discount", "pricing.tax", "pricing.total"} <= events:
        missing.append("A successful quote request has an incomplete pricing event sequence.")
    if not items:
        missing.append("No evidence was found for the reported request ID.")
    return missing
