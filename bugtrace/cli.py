import argparse
import json
from pathlib import Path

from bugtrace.evaluate import evaluate
from bugtrace.investigation import investigate


def main() -> int:
    parser = argparse.ArgumentParser(prog="bugtrace")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build-demo")
    investigate_command = commands.add_parser("investigate")
    investigate_command.add_argument("case_id")
    investigate_command.add_argument("--approve", action="store_true")
    investigate_command.add_argument("--llm", action="store_true")
    commands.add_parser("evaluate")
    commands.add_parser("check")
    arguments = parser.parse_args()
    root = Path.cwd()
    if arguments.command == "build-demo":
        from bugtrace.demo import build_demo
        build_demo(root)
        return 0
    if arguments.command == "investigate":
        result = investigate(arguments.case_id, root, root / "reports")
        if arguments.llm:
            print("LLM mode is not installed. Offline rule mode was used.")
        if arguments.approve:
            from bugtrace.reproduce import replay
            from bugtrace.regression import evaluate_regression, generate_test
            from bugtrace.intake import load_report
            report = load_report(root / "bug_reports" / f"{arguments.case_id}.yaml")
            generated = generate_test(arguments.case_id, report.model_dump(), "http://127.0.0.1:1")
            print("Generated regression test:")
            print(generated or "No test is generated for this control case.")
            result.reproduction = replay(arguments.case_id, "buggy", root)
            result.regression = evaluate_regression(arguments.case_id, root)
            result.limitations = [item for item in result.limitations if "approval gate" not in item]
            from bugtrace.report import write
            write(result, root / "reports")
        print(result.model_dump_json(indent=2))
        if not arguments.approve:
            print("Regression execution requires --approve.")
        return 0
    if arguments.command == "evaluate":
        print(json.dumps(evaluate(root, root / "reports"), indent=2))
        return 0
    if arguments.command == "check":
        from scripts.check_no_comments import check
        issues = check(root)
        print("\n".join(issues) if issues else "No comments or docstrings found.")
        return int(bool(issues))
    return 1
