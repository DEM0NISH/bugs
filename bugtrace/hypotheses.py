from bugtrace.models import EvidenceItem, Hypothesis, InvariantResult


def rule_mode(results: list[InvariantResult], evidence: list[EvidenceItem]) -> tuple[str, list[Hypothesis]]:
    evidence_ids = {item.id for item in evidence}
    if not evidence_ids:
        return "insufficient_evidence", []
    failed = [result for result in results if not result.passed]
    if not failed:
        return "no_defect_found", []
    hypotheses = []
    for result in failed:
        citations = [item for item in result.evidence_ids if item in evidence_ids]
        relevant = {"pricing_math": {"quote_service/pricing.py"}, "stored_pricing_math": {"quote_service/pricing.py", "quote_service/db.py"}, "idempotency_uniqueness": {"quote_service/main.py", "quote_service/db.py"}, "credit_ledger_balance": {"quote_service/main.py", "quote_service/db.py"}}.get(result.invariant_id, set())
        candidates = [item.id for item in evidence if item.source == "git" and relevant.intersection(item.content.get("files", []))]
        explanation = result.summary
        if candidates:
            explanation += " Related Git commits are low-confidence candidates and are not proof."
        hypotheses.append(Hypothesis(title=result.invariant_id.replace("_", " ").title(), explanation=explanation, status="supported" if citations else "inconclusive", supporting_evidence_ids=citations + candidates))
    return "defect_indicated", hypotheses
