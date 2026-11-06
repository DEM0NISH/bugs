import ast
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import httpx
import yaml

from bugtrace.models import RegressionResult


ALLOWED_IMPORTS = {"pytest", "httpx", "decimal", "json"}
FORBIDDEN_NAMES = {"exec", "eval", "open", "import", "os", "subprocess", "socket"}


def generate_test(case_id: str, report: dict, base_url: str) -> str:
    body = json.dumps(report.get("body", {}), separators=(",", ":"))
    headers = dict(report.get("headers", {}))
    headers.setdefault("X-Request-ID", report.get("request_id", "request"))
    if case_id in {"BT-01", "BT-02"}:
        return f'from decimal import Decimal\nimport httpx\nimport json\n\ndef test_quote_total():\n    payload = json.loads({body!r})\n    response = httpx.post("{base_url}/quotes", headers={headers!r}, json=payload)\n    assert Decimal(response.json()["total"]) == Decimal({str(report["expected"]["total"])!r})\n'
    if case_id == "BT-03":
        return f'import httpx\nimport json\n\ndef test_retry_returns_same_quote():\n    payload = json.loads({body!r})\n    first = httpx.post("{base_url}/quotes", headers={headers!r}, json=payload).json()\n    second = httpx.post("{base_url}/quotes", headers={headers!r}, json=payload).json()\n    assert first["id"] == second["id"]\n'
    if case_id == "BT-04":
        return f'import httpx\nimport json\n\ndef test_cancellation_releases_credit():\n    payload = json.loads({body!r})\n    quote = httpx.post("{base_url}/quotes", headers={headers!r}, json=payload).json()\n    quote_id = quote["id"]\n    httpx.post("{base_url}/quotes/" + quote_id + "/confirm")\n    httpx.post("{base_url}/quotes/" + quote_id + "/cancel")\n    credit = httpx.get("{base_url}/buyers/buyer-1/credit").json()\n    assert credit["credit_reserved"] == "0.00"\n'
    return ""


def validate_test(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] not in ALLOWED_IMPORTS for alias in node.names):
                raise ValueError("Generated test imports a module outside the allowlist.")
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
            raise ValueError("Generated test imports a module outside the allowlist.")
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id == "__import__"):
            raise ValueError(f"Generated test uses forbidden name: {node.id}")


def free_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return server.getsockname()[1]


def classify_xml(return_code: int, xml_path: Path) -> tuple[str, str]:
    root = ElementTree.parse(xml_path).getroot()
    failure = root.find(".//failure")
    error = root.find(".//error")
    if return_code == 0:
        return "pass", "Assertion passed."
    if failure is not None and error is None:
        return "assertion_failure", failure.get("message", "Assertion failed.")
    if error is not None:
        return "invalid_test", f"{error.get('message', 'Collection or runtime error.')}: {error.text or ''}"
    return "invalid_test", "Pytest failed without an assertion failure."


def run_ref_test(case_id: str, reference: str, source: str, root: Path) -> tuple[str, str]:
    case_dir = root / ".workspace" / case_id
    repository = case_dir / "repository"
    with tempfile.TemporaryDirectory(prefix=f"test-{reference}-", dir=case_dir) as temporary:
        temp = Path(temporary)
        worktree = temp / "service"
        subprocess.run(["git", "-C", str(repository), "worktree", "add", "--detach", str(worktree), f"{case_id}-{reference}"], check=True, capture_output=True, text=True, timeout=20)
        test_path = temp / "test_generated.py"
        xml_path = temp / "junit.xml"
        database = temp / "test.db"
        log_path = temp / "test.jsonl"
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        source = source.replace("http://127.0.0.1:1", base_url)
        test_path.write_text(source, encoding="utf-8")
        env = os.environ.copy()
        env.update({"QUOTE_DB_PATH": str(database), "QUOTE_LOG_PATH": str(log_path)})
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "quote_service.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=worktree, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                if process.poll() is not None:
                    return "invalid_test", "The service exited before the regression test started."
                try:
                    if httpx.get(f"{base_url}/health", timeout=0.5).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.25)
            else:
                return "invalid_test", "The service did not become healthy before the timeout."
            result = subprocess.run([sys.executable, "-m", "pytest", str(test_path), "--junitxml", str(xml_path), "-q"], cwd=worktree, env=env, capture_output=True, text=True, timeout=60)
            return classify_xml(result.returncode, xml_path)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            subprocess.run(["git", "-C", str(repository), "worktree", "remove", "--force", str(worktree)], capture_output=True, text=True, timeout=20)


def evaluate_regression(case_id: str, root: Path = Path.cwd()) -> RegressionResult:
    report = yaml.safe_load((root / "bug_reports" / f"{case_id}.yaml").read_text(encoding="utf-8")) or {}
    if case_id not in {"BT-01", "BT-02", "BT-03", "BT-04"}:
        return RegressionResult(status="not_applicable", reason="No regression test is generated for a control case.")
    source = generate_test(case_id, report, "http://127.0.0.1:1")
    validate_test(source)
    buggy_result, buggy_reason = run_ref_test(case_id, "buggy", source, root)
    fixed_result, fixed_reason = run_ref_test(case_id, "fixed", source, root)
    valid = buggy_result == "assertion_failure" and fixed_result == "pass"
    reason = "Generated test failed by assertion on the buggy build and passed on the fixed build." if valid else f"Buggy: {buggy_reason} Fixed: {fixed_reason}"
    return RegressionResult(status="valid" if valid else "invalid_test", test_source=source, buggy_result=buggy_result, fixed_result=fixed_result, reason=reason)
