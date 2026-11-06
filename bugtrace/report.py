from html import escape
from pathlib import Path

from bugtrace.models import Investigation


def markdown(investigation: Investigation) -> str:
    lines = [f"# Investigation {investigation.case_id}", "", f"**Verdict:** {investigation.verdict}", "", investigation.summary, "", "## Evidence timeline", "", "| ID | Source | Time | Confidence | Evidence |", "| --- | --- | --- | --- | --- |"]
    for item in investigation.evidence:
        lines.append(f"| {item.id} | {item.source} | {item.timestamp} | {item.confidence} | `{item.content}` |")
    lines.extend(["", "## Invariant checks", "", "| Invariant | Result | Summary |", "| --- | --- | --- |"])
    for result in investigation.invariants:
        lines.append(f"| {result.invariant_id} | {'PASS' if result.passed else 'FAIL'} | {result.summary} |")
    lines.extend(["", "## Hypotheses", ""])
    for item in investigation.hypotheses:
        lines.append(f"- **{item.title} ({item.status})**: {item.explanation} Evidence: {', '.join(item.supporting_evidence_ids)}")
    lines.extend(["", "## Reproduction", "", f"{investigation.reproduction.reason}", "", "## Regression", "", f"Status: {investigation.regression.status}. {investigation.regression.reason}", "", "## Limitations", ""])
    lines.extend(f"- {item}" for item in investigation.limitations)
    return "\n".join(lines) + "\n"


def html_report(investigation: Investigation) -> str:
    rows = "".join(f'<tr id="{escape(item.id)}"><th scope="row"><a href="#{escape(item.id)}">{escape(item.id)}</a></th><td>{escape(item.source)}</td><td>{escape(item.timestamp)}</td><td>{escape(item.confidence)}</td><td><code>{escape(str(item.content))}</code></td></tr>' for item in investigation.evidence)
    checks = "".join(f'<tr><th scope="row">{escape(item.invariant_id)}</th><td class="{"pass" if item.passed else "fail"}">{"PASS" if item.passed else "FAIL"}</td><td>{escape(item.summary)}</td></tr>' for item in investigation.invariants)
    hypotheses = "".join(hypothesis_html(item) for item in investigation.hypotheses)
    limitations = "".join(f"<li>{escape(item)}</li>" for item in investigation.limitations)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Investigation {escape(investigation.case_id)}</title><style>
:root{{font-family:system-ui,sans-serif;color:#183334;background:#f7f5ef;line-height:1.55}}body{{max-width:1050px;margin:auto;padding:1rem}}a{{color:#006e68}}table{{border-collapse:collapse;width:100%;display:block;overflow:auto}}caption{{text-align:left;font-weight:700;padding:.5rem}}th,td{{border:1px solid #aab7b3;padding:.55rem;text-align:left;vertical-align:top}}code{{font-family:ui-monospace,monospace;overflow-wrap:anywhere}}.pass{{color:#176b3a}}.fail{{color:#a22d20}}:focus-visible{{outline:3px solid #006e68;outline-offset:2px}}.badge{{border:1px solid #aab7b3;border-radius:6px;padding:.15rem .45rem}}@media(prefers-color-scheme:dark){{:root{{color:#e6eeee;background:#172122}}a{{color:#72d6ca}}th,td{{border-color:#637372}}.pass{{color:#81dba0}}.fail{{color:#ff9a88}}}}@media print{{a{{color:inherit}}body{{max-width:none}}}}</style></head><body><a href="#main">Skip to content</a><main id="main"><h1>Investigation {escape(investigation.case_id)}</h1><p class="badge">Verdict: {escape(investigation.verdict)}</p><p>{escape(investigation.summary)}</p><h2>Evidence timeline</h2><table><caption>Evidence collected for this request</caption><thead><tr><th scope="col">ID</th><th scope="col">Source</th><th scope="col">Time</th><th scope="col">Confidence</th><th scope="col">Content</th></tr></thead><tbody>{rows or '<tr><td colspan="5">No events found for this request ID.</td></tr>'}</tbody></table><h2>Invariant check results</h2><table><caption>Business rule validation</caption><thead><tr><th scope="col">Invariant</th><th scope="col">Status</th><th scope="col">Result</th></tr></thead><tbody>{checks or '<tr><td colspan="3">No checks could be run.</td></tr>'}</tbody></table><h2>Hypotheses</h2><ol>{hypotheses or '<li>No supported hypothesis from current evidence.</li>'}</ol><h2>Reproduction</h2><p>{escape(investigation.reproduction.reason)}</p><h2>Regression</h2><p>{escape(investigation.regression.status)}: {escape(investigation.regression.reason)}</p><h2>Limitations</h2><ul>{limitations or '<li>None recorded.</li>'}</ul></main></body></html>'''


def write(investigation: Investigation, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{investigation.case_id}.md").write_text(markdown(investigation), encoding="utf-8")
    (output_dir / f"{investigation.case_id}.html").write_text(html_report(investigation), encoding="utf-8")


def hypothesis_html(item) -> str:
    citations = ", ".join(f'<a href="#{escape(evidence_id)}">{escape(evidence_id)}</a>' for evidence_id in item.supporting_evidence_ids)
    return f'<li><strong>{escape(item.title)} · {escape(item.status)}</strong><p>{escape(item.explanation)} Evidence: {citations}</p></li>'
