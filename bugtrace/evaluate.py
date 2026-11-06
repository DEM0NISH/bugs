import json
from pathlib import Path

from bugtrace.investigation import investigate
from bugtrace.report import write


def evaluate(root: Path = Path.cwd(), report_dir: Path | None = None) -> dict:
    truth_dir = root / "ground_truth"
    cases = sorted(path.stem for path in truth_dir.glob("*.json"))
    results = []
    for case_id in cases:
        expected = json.loads((truth_dir / f"{case_id}.json").read_text(encoding="utf-8"))["expected_verdict"]
        actual = investigate(case_id, root)
        results.append({"case_id": case_id, "expected": expected, "actual": actual.verdict, "pass": expected == actual.verdict})
    if report_dir:
        report_dir.mkdir(parents=True, exist_ok=True)
        for case_id in cases:
            write(investigate(case_id, root), report_dir)
        table = ["# Offline evaluation", "", f"Sample size: {len(results)} synthetic cases.", "", "| Case | Expected verdict | Actual verdict | Result |", "| --- | --- | --- | --- |"]
        table.extend(f"| {item['case_id']} | {item['expected']} | {item['actual']} | {'PASS' if item['pass'] else 'FAIL'} |" for item in results)
        (report_dir / "evaluation.md").write_text("\n".join(table) + "\n", encoding="utf-8")
        (report_dir / "evaluation.json").write_text(json.dumps({"sample_size": len(results), "results": results}, indent=2) + "\n", encoding="utf-8")
        links = "".join(f'<li><a href="{case_id}.html">{case_id}</a> <a href="{case_id}.md">Markdown</a></li>' for case_id in cases)
        (report_dir / "index.html").write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>BugTrace reports</title><main><h1>Investigation reports</h1><ul>{links}</ul><a href="evaluation.md">Offline evaluation</a></main></html>', encoding="utf-8")
    return {"sample_size": len(results), "results": results}
