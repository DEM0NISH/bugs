import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

import httpx


CASES = ("BT-01", "BT-02", "BT-03", "BT-04", "NC-01", "NC-02")


def run(command: list[str], cwd: Path, env: dict | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(command, cwd=cwd, env=merged, check=True, capture_output=True, text=True, timeout=timeout)


def remove_readonly(function, path, error) -> None:
    os.chmod(path, stat.S_IWRITE)
    function(path)


def git(repository: Path, *arguments: str, env: dict | None = None) -> None:
    run(["git", *arguments], repository, env)


def commit(repository: Path, subject: str, date: str) -> None:
    git(repository, "add", "-A")
    git(repository, "commit", "-m", subject, env={"GIT_AUTHOR_NAME": "BugTrace Demo", "GIT_AUTHOR_EMAIL": "demo@example.invalid", "GIT_COMMITTER_NAME": "BugTrace Demo", "GIT_COMMITTER_EMAIL": "demo@example.invalid", "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})


def run_baseline_tests(repository: Path, runtime: Path, label: str) -> None:
    if runtime.exists():
        shutil.rmtree(runtime, onerror=remove_readonly)
    runtime.mkdir(parents=True, exist_ok=True)
    env = {"QUOTE_DB_PATH": str(runtime / "baseline.db"), "QUOTE_LOG_PATH": str(runtime / "baseline.jsonl")}
    result = run([sys.executable, "-m", "pytest", "quote_service/tests", "-q"], repository, env=env, timeout=120)
    summary = next((line.strip() for line in (result.stdout + result.stderr).splitlines() if " passed" in line), "pytest completed successfully")
    print(f"Baseline suite passed on {label}: {summary}")


def create_overrides(root: Path) -> None:
    base_pricing = (root / "quote_service" / "pricing.py").read_text(encoding="utf-8")
    base_main = (root / "quote_service" / "main.py").read_text(encoding="utf-8")
    base_db = (root / "quote_service" / "db.py").read_text(encoding="utf-8")
    templates = {
        "BT-01": {"pricing.py": base_pricing.replace('discount_amount = money(subtotal * discount_percent / Decimal("100"))', 'discount_amount = money(subtotal * discount_percent / Decimal("100")) if len(lines) < 2 else Decimal("0.00")')},
        "BT-02": {"pricing.py": base_pricing.replace('gst_amount = money(taxable_amount * GST_RATE)', 'gst_amount = money(sum((money(money(amount * (Decimal("100") - discount_percent) / Decimal("100")) * GST_RATE) for amount in line_amounts), Decimal("0.00")))')},
        "BT-03": {
            "main.py": base_main.replace('''        existing = connection.execute("SELECT quote_id FROM idempotency_keys WHERE key = ?", (idempotency_key,)).fetchone()
        if existing:
            emit(request_id, "idempotency.hit", {"key": idempotency_key, "quote_id": existing["quote_id"]})
            quote = connection.execute("SELECT * FROM quotes WHERE id = ?", (existing["quote_id"],)).fetchone()
            response.status_code = 200
            return dict(quote)
        emit(request_id, "idempotency.miss", {"key": idempotency_key})''', '        emit(request_id, "idempotency.miss", {"key": idempotency_key})').replace('connection.execute("INSERT INTO idempotency_keys VALUES(?,?,?)", (idempotency_key, quote_id, created_at))', 'connection.execute("INSERT INTO idempotency_keys(key,quote_id,created_at) VALUES(?,?,?)", (idempotency_key, quote_id, created_at))'),
            "db.py": base_db.replace('idempotency_key TEXT NOT NULL UNIQUE', 'idempotency_key TEXT NOT NULL').replace('idempotency_keys (key TEXT PRIMARY KEY, quote_id TEXT NOT NULL REFERENCES quotes(id), created_at TEXT NOT NULL)', 'idempotency_keys (id INTEGER PRIMARY KEY, key TEXT NOT NULL, quote_id TEXT NOT NULL REFERENCES quotes(id), created_at TEXT NOT NULL)'),
        },
        "BT-04": {"main.py": base_main.replace('''            if quote["status"] == "confirmed":
                buyer = transaction.execute("SELECT * FROM buyers WHERE id = ?", (quote["buyer_id"],)).fetchone()
                reserved = Decimal(buyer["credit_reserved"])
                total = Decimal(quote["total"])
                buyer_update = transaction.execute("UPDATE buyers SET credit_reserved = ? WHERE id = ? AND credit_reserved = ?", (str(reserved - total), quote["buyer_id"], buyer["credit_reserved"]))
                if buyer_update.rowcount != 1:
                    raise HTTPException(409, "Buyer credit changed")
                transaction.execute("INSERT INTO credit_ledger(buyer_id,quote_id,entry_type,amount,created_at) VALUES(?,?,?,?,?)", (quote["buyer_id"], quote_id, "release", quote["total"], now()))
                released = quote["total"]''', '''            if quote["status"] == "confirmed":
                pass''')},
    }
    for case_id, files in templates.items():
        override_dir = root / "quote_service_defects" / case_id
        override_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            (override_dir / filename).write_text(content, encoding="utf-8")


def free_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return server.getsockname()[1]


def scenario(case_id: str, repository: Path, runtime: Path, report: dict) -> None:
    runtime.mkdir(parents=True, exist_ok=True)
    database = runtime / "service.db"
    log_path = runtime / "service.jsonl"
    port = free_port()
    env = os.environ.copy()
    env.update({"QUOTE_DB_PATH": str(database), "QUOTE_LOG_PATH": str(log_path)})
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "quote_service.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=repository, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    base_url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError("The sample service exited before becoming healthy.")
            try:
                if httpx.get(f"{base_url}/health", timeout=0.5).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            raise TimeoutError("The sample service did not become healthy.")
        for index in range(7):
            payload = {"buyer_id": "buyer-1", "discount_percent": 0, "lines": [{"quantity": 1, "unit_price": "1.00", "description": f"normal-{index}"}]}
            httpx.post(f"{base_url}/quotes", headers={"Idempotency-Key": f"normal-{index}", "X-Request-ID": f"normal-{case_id}-{index}"}, json=payload, timeout=5)
        if case_id == "NC-02":
            return
        headers = dict(report.get("headers", {}))
        headers.setdefault("X-Request-ID", report["request_id"])
        payload = report.get("body", {})
        first = httpx.post(f"{base_url}/quotes", headers=headers, json=payload, timeout=10)
        if not first.is_success:
            raise RuntimeError(f"Scenario request failed with {first.status_code}: {first.text}")
        if case_id == "BT-03":
            second = httpx.post(f"{base_url}/quotes", headers=headers, json=payload, timeout=10)
            if not second.is_success:
                raise RuntimeError(f"Retry request failed with {second.status_code}: {second.text}")
            report["actual"] = {"first_id": first.json().get("id"), "retry_id": second.json().get("id"), "quote_count": 2 if first.json().get("id") != second.json().get("id") else 1}
        if case_id == "BT-04":
            quote_id = first.json()["id"]
            httpx.post(f"{base_url}/quotes/{quote_id}/confirm", headers={"X-Request-ID": report["request_id"]}, timeout=10)
            httpx.post(f"{base_url}/quotes/{quote_id}/cancel", headers={"X-Request-ID": report["request_id"]}, timeout=10)
            report["actual"] = httpx.get(f"{base_url}/buyers/buyer-1/credit", timeout=5).json()
        if case_id == "BT-01":
            report["actual"] = {"total": first.json().get("total")}
        if case_id == "BT-02":
            report["actual"] = {"total": first.json().get("total")}
    finally:
        if process.poll() is None:
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def build_case(root: Path, case_id: str) -> None:
    workspace = root / ".workspace" / case_id
    repository = workspace / "repository"
    for generated in (workspace / "runtime", workspace / "baseline-buggy", workspace / "baseline-fixed"):
        if generated.exists():
            shutil.rmtree(generated, onerror=remove_readonly)
    if repository.exists():
        shutil.rmtree(repository, onerror=remove_readonly)
    repository.mkdir(parents=True)
    shutil.copytree(root / "quote_service", repository / "quote_service")
    shutil.copy2(root / ".gitignore", repository / ".gitignore")
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "BugTrace Demo")
    git(repository, "config", "user.email", "demo@example.invalid")
    base = "2025-01-01T00:00:00+00:00"
    commit(repository, "Add service structure", base)
    for index in range(3):
        (repository / f"scenario-{index}.txt").write_text(f"Local synthetic scenario note {index}\n", encoding="utf-8")
        commit(repository, "Refresh sample data", f"2025-01-0{index + 2}T00:00:00+00:00")
    if case_id in {"BT-01", "BT-02", "BT-03", "BT-04"}:
        for filename in (root / "quote_service_defects" / case_id).glob("*.py"):
            shutil.copy2(filename, repository / "quote_service" / filename.name)
        commit(repository, "Refine request processing", "2025-01-05T00:00:00+00:00")
        pricing_path = repository / "quote_service" / "pricing.py"
        pricing_source = pricing_path.read_text(encoding="utf-8").replace("line_amounts", "line_values")
        pricing_path.write_text(pricing_source, encoding="utf-8")
        commit(repository, "Rename calculation local", "2025-01-06T00:00:00+00:00")
    git(repository, "tag", f"{case_id}-buggy")
    git(repository, "checkout", f"{case_id}-buggy")
    run_baseline_tests(repository, workspace / "baseline-buggy", f"{case_id}-buggy")
    shutil.copytree(root / "quote_service", repository / "quote_service", dirs_exist_ok=True)
    (repository / "scenario_state.txt").write_text("Synthetic scenario state recorded.\n", encoding="utf-8")
    commit(repository, "Adjust request processing", "2025-01-07T00:00:00+00:00")
    git(repository, "tag", f"{case_id}-fixed")
    git(repository, "checkout", f"{case_id}-fixed")
    run_baseline_tests(repository, workspace / "baseline-fixed", f"{case_id}-fixed")
    report_path = root / "bug_reports" / f"{case_id}.yaml"
    import yaml
    report = yaml.safe_load(report_path.read_text(encoding="utf-8")) or {}
    if case_id == "NC-02":
        report["request_id"] = "missing-request-id"
    git(repository, "checkout", f"{case_id}-buggy")
    scenario(case_id, repository, workspace / "runtime", report)
    report_path.write_text(yaml.safe_dump(report, sort_keys=False), encoding="utf-8")
    git(repository, "checkout", f"{case_id}-fixed")


def build_demo(root: Path = Path.cwd()) -> None:
    create_overrides(root)
    for case_id in CASES:
        build_case(root, case_id)
    print(f"Built {len(CASES)} deterministic local scenario repositories in {root / '.workspace'}")
