from pathlib import Path

from bugtrace.collectors.logs import collect as collect_logs
from bugtrace.collectors.git import collect as collect_git
from bugtrace.collectors.sql import collect as collect_sql
from bugtrace.correlate import gaps, timeline
from bugtrace.hypotheses import rule_mode
from bugtrace.intake import load_report
from bugtrace.invariants import check
from bugtrace.models import Investigation
from bugtrace.report import write


def investigate(case_id: str, root: Path = Path.cwd(), output_dir: Path | None = None) -> Investigation:
    case_dir = root / ".workspace" / case_id
    runtime = case_dir / "runtime"
    report = load_report(root / "bug_reports" / f"{case_id}.yaml")
    evidence, skipped = collect_logs(runtime / "service.jsonl", report.request_id)
    repository = case_dir / "repository"
    if repository.exists():
        git_evidence = collect_git(repository, f"{case_id}-buggy", report.endpoint)
        for item in git_evidence:
            item.id = f"E{len(evidence) + 1}"
            evidence.append(item)
    if (runtime / "service.db").exists():
        sql_evidence = collect_sql(runtime / "service.db", root / "sql", {"quotes.sql": report.headers.get("Idempotency-Key", ""), "quote_lines.sql": report.headers.get("Idempotency-Key", ""), "credit.sql": report.headers.get("Idempotency-Key", ""), "buyers.sql": report.body.get("buyer_id", "")})
        for item in sql_evidence:
            item.id = f"E{len(evidence) + 1}"
            evidence.append(item)
    evidence = timeline(evidence)
    results = check(evidence)
    returned = next((item.content.get("data", {}).get("status_code") for item in evidence if item.content.get("event") == "request.completed"), None)
    gaps_found = gaps([item for item in evidence if item.source == "log"], returned)
    log_evidence = [item for item in evidence if item.source == "log"]
    if skipped:
        gaps_found.append(f"Skipped {skipped} malformed log lines.")
    if not log_evidence:
        verdict, hypotheses = "insufficient_evidence", []
    else:
        verdict, hypotheses = rule_mode(results, evidence)
    summary = "The request evidence violates one or more business invariants." if verdict == "defect_indicated" else "Available request evidence is consistent with the stated invariants." if verdict == "no_defect_found" else "The request could not be tied to available evidence."
    investigation = Investigation(case_id=case_id, verdict=verdict, summary=summary, needs_info=report.needs_info, evidence=evidence, invariants=results, hypotheses=hypotheses, limitations=[*gaps_found, "Offline rule mode was used. Optional LLM mode was not run.", "Reproduction and generated regression execution require the approval gate."])
    if output_dir:
        write(investigation, output_dir)
    return investigation
