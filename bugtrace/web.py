import json
import re
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse


ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
BUG_REPORTS = ROOT / "bug_reports"
app = FastAPI(title="BugTrace Results API", version="1.0.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "BugTrace Results API"}


@app.get("/api/evaluation")
def evaluation() -> dict:
    path = REPORTS / "evaluation.json"
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Evaluation results are not available.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/reports")
def reports() -> dict:
    evaluation_path = REPORTS / "evaluation.json"
    if not evaluation_path.is_file():
        raise HTTPException(status_code=503, detail="Evaluation results are not available.")
    results = json.loads(evaluation_path.read_text(encoding="utf-8"))["results"]
    cases = []
    for result in results:
        case_id = result["case_id"]
        report_path = BUG_REPORTS / f"{case_id}.yaml"
        source = yaml.safe_load(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        cases.append({
            **result,
            "title": source.get("title", case_id),
            "description": source.get("description", ""),
        })
    return {"sample_size": len(cases), "passed": sum(case["pass"] for case in cases), "cases": cases}


@app.get("/api/reports/{case_id}", response_class=HTMLResponse)
def report(case_id: str) -> str:
    if not re.fullmatch(r"[A-Z]{2}-\d{2}", case_id) or not (REPORTS / f"{case_id}.html").is_file():
        raise HTTPException(status_code=404, detail="Report not found.")
    return (REPORTS / f"{case_id}.html").read_text(encoding="utf-8")
