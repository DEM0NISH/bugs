import ast
import io
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".workspace", ".venv", ".deps", ".pytest_tmp", "__pycache__", ".pytest_cache"}
MARKERS = {
    ".yml": ("#",),
    ".yaml": ("#",),
    ".toml": ("#",),
    ".ini": ("#", ";"),
    ".cfg": ("#", ";"),
    ".txt": ("#",),
    ".sql": ("--",),
    ".sh": ("#",),
    ".ps1": ("#",),
    ".js": ("//", "/*", "*"),
    ".jsx": ("//", "/*", "*"),
    ".ts": ("//", "/*", "*"),
    ".tsx": ("//", "/*", "*"),
    ".css": ("/*", "*"),
    ".html": ("<!--",),
}


def python_issues(path: Path, source: str) -> list[str]:
    issues = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                issues.append(f"{path}:{token.start[0]} comment token")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(node, clean=False):
                issues.append(f"{path}:{node.lineno if hasattr(node, 'lineno') else 1} docstring")
    except (SyntaxError, tokenize.TokenError) as error:
        issues.append(f"{path}: parse error: {error}")
    return issues


def text_issues(path: Path, source: str) -> list[str]:
    if path.suffix.lower() == ".md":
        return []
    issues = []
    markers = MARKERS.get(path.suffix.lower(), ())
    for number, line in enumerate(source.splitlines(), 1):
        stripped = line.lstrip()
        if any(stripped.startswith(marker) for marker in markers):
            issues.append(f"{path}:{number} comment marker")
        if "<!--" in line or "-->" in line:
            issues.append(f"{path}:{number} HTML comment marker")
        if path.suffix.lower() == ".css" and "/*" in line:
            issues.append(f"{path}:{number} CSS comment marker")
    return issues


def check(root: Path = ROOT) -> list[str]:
    issues = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(root)
        if path.suffix.lower() == ".py":
            issues.extend(python_issues(relative, source))
        else:
            issues.extend(text_issues(relative, source))
    return issues


def main() -> int:
    issues = check()
    if issues:
        print("\n".join(issues))
        return 1
    print("No comments or docstrings found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
