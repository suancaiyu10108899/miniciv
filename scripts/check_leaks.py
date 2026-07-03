#!/usr/bin/env python
# scripts/check_leaks.py — 扫描 git 追踪文件中的敏感信息
# 作为 pre-commit hook 运行，也支持手动运行: python scripts/check_leaks.py
#
# 检测: API keys (sk-*, Bearer tokens), 硬编码密码, .env 文件是否在 gitignore 中

import os, sys, subprocess, re
from pathlib import Path

# ─── Patterns to detect ──────────────────────────────
# Each: (regex, name, severity)
PATTERNS = [
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), "OpenAI/DeepSeek API key (sk-...)", "CRITICAL"),
    (re.compile(r'Bearer\s+[a-zA-Z0-9\-_\.]{20,}'), "Bearer token", "CRITICAL"),
    (re.compile(r'api_key\s*=\s*["\'][a-zA-Z0-9\-_]{10,}["\']'), "Hardcoded api_key assignment", "CRITICAL"),
    (re.compile(r'ANTHROPIC_AUTH_TOKEN\s*=\s*[a-zA-Z0-9\-_]{10,}'), "ANTHROPIC_AUTH_TOKEN with value", "CRITICAL"),
    (re.compile(r'DEEPSEEK_API_KEY\s*=\s*[a-zA-Z0-9\-_]{10,}'), "DEEPSEEK_API_KEY with value", "CRITICAL"),
    (re.compile(r'password\s*=\s*["\'][^"\']{3,}["\']'), 'Hardcoded password', "WARNING"),
    (re.compile(r'secret\s*=\s*["\'][^"\']{3,}["\']'), 'Hardcoded secret', "WARNING"),
]

# Files to skip
SKIP_PATTERNS = [
    "check_leaks.py",          # this file (may contain regex examples)
    ".env.example",             # template file
    "package-lock.json",        # auto-generated
    ".pyc", ".pyo",             # compiled
    ".git/",                    # git internals
    "__pycache__/",
]

# ─── Helpers ──────────────────────────────────────────

def get_tracked_files():
    """返回所有 git 追踪的文件列表"""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        return result.stdout.strip().split("\n")
    except Exception:
        # Fallback: list all non-git files
        root = Path(__file__).parent.parent
        tracked = []
        for f in root.rglob("*"):
            if f.is_file() and ".git" not in str(f):
                tracked.append(str(f.relative_to(root)))
        return tracked


def should_skip(filepath: str) -> bool:
    for pat in SKIP_PATTERNS:
        if pat in filepath:
            return True
    return False


def check_file(filepath: str) -> list[dict]:
    """扫描单个文件。返回发现的问题列表。"""
    root = Path(__file__).parent.parent
    full_path = root / filepath
    findings = []

    try:
        # Skip binary files
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return findings

    for lineno, line in enumerate(lines, 1):
        for regex, name, severity in PATTERNS:
            matches = regex.findall(line)
            for match in matches:
                # Don't flag commented lines
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("--"):
                    continue
                # Don't flag .env.example
                if ".env.example" in filepath:
                    continue
                findings.append({
                    "file": filepath,
                    "line": lineno,
                    "type": name,
                    "severity": severity,
                    "preview": line.strip()[:100],
                })
    return findings


def check_gitignore():
    """检查 .env 是否在 gitignore 中"""
    root = Path(__file__).parent.parent
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return [{"file": ".gitignore", "line": 0, "type": "Missing .gitignore file",
                 "severity": "WARNING", "preview": ""}]

    content = gitignore.read_text()
    checks = [".env"]
    findings = []
    for check in checks:
        if check not in content:
            findings.append({
                "file": ".gitignore",
                "line": 0,
                "type": f"'{check}' not in gitignore — risk of committing API keys",
                "severity": "WARNING",
                "preview": f"Add '{check}' to .gitignore",
            })
    return findings


def main():
    root = Path(__file__).parent.parent
    os.chdir(root)

    print("check_leaks.py — scanning for sensitive information...")
    findings = []

    # Check tracked files
    tracked = get_tracked_files()
    for filepath in tracked:
        if not filepath or should_skip(filepath):
            continue
        findings.extend(check_file(filepath))

    # Check gitignore
    findings.extend(check_gitignore())

    # Report
    if not findings:
        print("OK: no leaks detected")
        return 0

    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    warnings = [f for f in findings if f["severity"] == "WARNING"]

    if critical:
        print(f"\n*** {len(critical)} CRITICAL finding(s) ***")
        for f in critical:
            print(f"  {f['file']}:{f['line']} — {f['type']}")
            print(f"    {f['preview']}")

    if warnings:
        print(f"\n{len(warnings)} WARNING(s):")
        for f in warnings:
            print(f"  {f['file']}:{f['line']} — {f['type']}")

    print(f"\nTotal: {len(critical)} critical, {len(warnings)} warnings")

    # Exit with error if critical findings (for pre-commit hook)
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
