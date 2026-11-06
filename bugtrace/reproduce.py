import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
import yaml

from bugtrace.models import Reproduction


def free_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return server.getsockname()[1]


def replay(case_id: str, reference: str = "buggy", root: Path = Path.cwd()) -> Reproduction:
    case_dir = root / ".workspace" / case_id
    repository = case_dir / "repository"
    report = yaml.safe_load((root / "bug_reports" / f"{case_id}.yaml").read_text(encoding="utf-8")) or {}
    if case_id == "NC-02":
        return Reproduction(attempted=False, reason="No request identifier exists in the logs or database, so replay is not possible.")
    reference_name = f"{case_id}-{reference}"
    with tempfile.TemporaryDirectory(prefix="replay-", dir=case_dir) as temporary:
        worktree = Path(temporary) / "service"
        subprocess.run(["git", "-C", str(repository), "worktree", "add", "--detach", str(worktree), reference_name], check=True, capture_output=True, text=True, timeout=20)
        database = Path(temporary) / "replay.db"
        log_path = Path(temporary) / "replay.jsonl"
        port = free_port()
        env = os.environ.copy()
        env.update({"QUOTE_DB_PATH": str(database), "QUOTE_LOG_PATH": str(log_path)})
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "quote_service.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=worktree, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base_url = f"http://127.0.0.1:{port}"
        try:
            for _ in range(80):
                if process.poll() is not None:
                    raise RuntimeError("The replay service exited before becoming healthy.")
                try:
                    if httpx.get(f"{base_url}/health", timeout=0.5).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.25)
            else:
                raise TimeoutError("The replay service did not become healthy.")
            headers = dict(report.get("headers", {}))
            headers.setdefault("X-Request-ID", report["request_id"])
            payload = report.get("body", {})
            first = httpx.post(f"{base_url}/quotes", headers=headers, json=payload, timeout=10)
            if not first.is_success:
                return Reproduction(attempted=True, expected=report.get("expected", {}), actual={"status_code": first.status_code}, matched=False, reason="The request could not be replayed as reported.")
            actual = {}
            if case_id == "BT-01" or case_id == "BT-02" or case_id == "NC-01":
                actual = {"total": first.json().get("total")}
            if case_id == "BT-03":
                retry = httpx.post(f"{base_url}/quotes", headers=headers, json=payload, timeout=10)
                connection = sqlite3.connect(database)
                count = connection.execute("SELECT COUNT(*) FROM quotes WHERE idempotency_key = ?", (headers["Idempotency-Key"],)).fetchone()[0]
                connection.close()
                actual = {"first_id": first.json().get("id"), "retry_id": retry.json().get("id"), "quote_count": count}
            if case_id == "BT-04":
                quote_id = first.json()["id"]
                httpx.post(f"{base_url}/quotes/{quote_id}/confirm", headers={"X-Request-ID": report["request_id"]}, timeout=10)
                httpx.post(f"{base_url}/quotes/{quote_id}/cancel", headers={"X-Request-ID": report["request_id"]}, timeout=10)
                actual = httpx.get(f"{base_url}/buyers/buyer-1/credit", timeout=5).json()
            expected = report.get("expected", {})
            def equal(left, right):
                try:
                    return Decimal(str(left)) == Decimal(str(right))
                except (InvalidOperation, ValueError):
                    return left == right

            matched = all(equal(actual.get(key), value) for key, value in expected.items())
            return Reproduction(attempted=True, expected=expected, actual=actual, matched=matched, reason="Replay completed and expected fields were compared." if matched else "Replay completed and one or more expected fields differed.")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            subprocess.run(["git", "-C", str(repository), "worktree", "remove", "--force", str(worktree)], capture_output=True, text=True, timeout=20)
