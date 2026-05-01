#!/usr/bin/env python3
"""Agent Worktree Doctor: local safety and context diagnostics for AI coding."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_DIR = ".agent-worktree-doctor"
BASELINE_NAME = "baseline.json"
REPORT_MD = "agent-worktree-doctor-report.md"
REPORT_JSON = "agent-worktree-doctor-report.json"

EXCLUDED_DIRS = {
    TOOL_DIR,
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "out",
    ".next",
    ".nuxt",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    ".turbo",
    ".cache",
}

TEXT_EXTS = {
    ".bat",
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".kt",
    ".log",
    ".lua",
    ".md",
    ".mjs",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

RISK_PATTERNS = [
    ("lockfile", re.compile(r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|Cargo\.lock|Pipfile\.lock|poetry\.lock|composer\.lock|Gemfile\.lock)$")),
    ("environment or secret", re.compile(r"(^|/)(\.env|\.env\..+|.*secret.*|.*credential.*|.*key.*\.pem)$", re.I)),
    ("ci config", re.compile(r"(^|/)(\.github/workflows/|\.gitlab-ci\.yml|azure-pipelines\.yml|Jenkinsfile)$", re.I)),
    ("migration", re.compile(r"(^|/)(migrations?|db/migrate|prisma/migrations)/", re.I)),
    ("generated/build output", re.compile(r"(^|/)(dist|build|out|coverage|\.next|target)/", re.I)),
    ("binary asset", re.compile(r"\.(png|jpg|jpeg|gif|webp|ico|pdf|docx|xlsx|pptx|zip|7z|rar|exe|dll|so|dylib)$", re.I)),
    ("package manifest", re.compile(r"(^|/)(package\.json|pyproject\.toml|requirements.*\.txt|Cargo\.toml|go\.mod|pom\.xml|build\.gradle)$", re.I)),
]


@dataclasses.dataclass
class GitFile:
    path: str
    status: str
    category: str


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_cmd(args: list[str], cwd: Path) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except FileNotFoundError as exc:
        return 127, "", str(exc)


def find_git_root(path: Path) -> Path | None:
    code, out, _ = run_cmd(["git", "rev-parse", "--show-toplevel"], path)
    if code != 0:
        return None
    return Path(out.strip()).resolve()


def parse_status_line(line: str) -> GitFile | None:
    if not line.strip() or len(line) < 4:
        return None
    status = line[:2]
    raw_path = line[3:].strip()
    if " -> " in raw_path:
        raw_path = raw_path.split(" -> ", 1)[1]
    category = "untracked" if status == "??" else "deleted" if "D" in status else "modified"
    if "A" in status and status != "??":
        category = "added"
    if "R" in status:
        category = "renamed"
    return GitFile(path=raw_path.replace("\\", "/"), status=status, category=category)


def git_status(repo: Path) -> list[GitFile]:
    code, out, _ = run_cmd(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo)
    if code != 0:
        return []
    files: list[GitFile] = []
    for line in out.splitlines():
        item = parse_status_line(line)
        if item:
            files.append(item)
    return files


def git_numstat(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cmd in (["git", "diff", "--numstat"], ["git", "diff", "--cached", "--numstat"]):
        code, out, _ = run_cmd(cmd, repo)
        if code != 0:
            continue
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                add_raw, del_raw, path = parts[0], parts[1], parts[2]
                rows.append(
                    {
                        "path": path.replace("\\", "/"),
                        "additions": None if add_raw == "-" else int(add_raw),
                        "deletions": None if del_raw == "-" else int(del_raw),
                    }
                )
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = dedup.setdefault(row["path"], {"path": row["path"], "additions": 0, "deletions": 0})
        if row["additions"] is None or row["deletions"] is None:
            current["binary"] = True
        else:
            current["additions"] += row["additions"]
            current["deletions"] += row["deletions"]
    return list(dedup.values())


def sha256_file(path: Path, max_bytes: int = 20_000_000) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def snapshot(repo: Path, output: Path | None = None) -> Path:
    root = find_git_root(repo) or repo.resolve()
    status = git_status(root) if find_git_root(repo) else []
    files: dict[str, dict[str, Any]] = {}
    for item in status:
        abs_path = root / item.path
        files[item.path] = {
            "status": item.status,
            "category": item.category,
            "sha256": sha256_file(abs_path) if abs_path.exists() and abs_path.is_file() else None,
        }
    payload = {
        "tool": "agent-worktree-doctor",
        "version": 1,
        "created_at": now_iso(),
        "platform": platform.platform(),
        "repo": str(root),
        "git_available": find_git_root(repo) is not None,
        "files": files,
    }
    out_path = output or root / TOOL_DIR / BASELINE_NAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def classify_risks(files: list[GitFile]) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    for item in files:
        for label, pattern in RISK_PATTERNS:
            if pattern.search(item.path):
                risks.append({"path": item.path, "status": item.status, "risk": label})
        if item.category == "deleted":
            risks.append({"path": item.path, "status": item.status, "risk": "deleted file"})
    return risks


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTS:
        return True
    try:
        data = path.read_bytes()[:4096]
        return b"\0" not in data and bool(data.strip())
    except OSError:
        return False


def context_scan(root: Path, max_file_kb: int) -> dict[str, Any]:
    large_files: list[dict[str, Any]] = []
    noisy_files: list[dict[str, Any]] = []
    scanned_files = 0
    scanned_bytes = 0
    omitted_dirs: dict[str, int] = {}

    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        kept_dirs = []
        for dirname in dirs:
            if dirname in EXCLUDED_DIRS:
                omitted_dirs[dirname] = omitted_dirs.get(dirname, 0) + 1
            else:
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in files:
            if filename in {REPORT_MD, REPORT_JSON}:
                continue
            path = current_path / filename
            try:
                rel = path.relative_to(root).as_posix()
                size = path.stat().st_size
            except OSError:
                continue
            scanned_files += 1
            scanned_bytes += size
            suffix = path.suffix.lower()
            if size >= max_file_kb * 1024:
                large_files.append({"path": rel, "kb": round(size / 1024, 1)})
            if suffix in {".log", ".tmp", ".bak", ".cache"} or re.search(r"(^|/)(debug|trace|output|report)s?/", rel, re.I):
                noisy_files.append({"path": rel, "reason": "log/output-like file"})
            if suffix in {".csv", ".jsonl", ".ipynb"} and size > 100 * 1024:
                noisy_files.append({"path": rel, "reason": "large data/notebook file"})
            if suffix == ".min.js" or ".bundle." in filename:
                noisy_files.append({"path": rel, "reason": "minified or bundled asset"})
            if is_probably_text(path):
                pass

    large_files.sort(key=lambda row: row["kb"], reverse=True)
    return {
        "scanned_files": scanned_files,
        "scanned_kb": round(scanned_bytes / 1024, 1),
        "omitted_dirs": omitted_dirs,
        "large_files": large_files[:30],
        "noisy_files": noisy_files[:30],
        "estimated_tokens": int(scanned_bytes / 4),
    }


def load_baseline(root: Path, explicit: Path | None) -> dict[str, Any] | None:
    path = explicit or root / TOOL_DIR / BASELINE_NAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def compare_baseline(root: Path, files: list[GitFile], baseline: dict[str, Any] | None) -> dict[str, Any]:
    if not baseline:
        return {"available": False, "pre_existing": [], "new_or_changed_after_baseline": [], "overlap": []}
    baseline_files = baseline.get("files", {})
    pre_existing = []
    new_or_changed = []
    overlap = []
    for item in files:
        current_hash = sha256_file(root / item.path) if (root / item.path).exists() and (root / item.path).is_file() else None
        base = baseline_files.get(item.path)
        if base:
            pre_existing.append(item.path)
            if current_hash and base.get("sha256") and current_hash != base.get("sha256"):
                overlap.append(item.path)
        else:
            new_or_changed.append(item.path)
    return {
        "available": True,
        "created_at": baseline.get("created_at"),
        "pre_existing": sorted(pre_existing),
        "new_or_changed_after_baseline": sorted(new_or_changed),
        "overlap": sorted(overlap),
    }


def build_report(repo: Path, baseline_path: Path | None, max_file_kb: int) -> dict[str, Any]:
    root = find_git_root(repo)
    git_available = root is not None
    root = root or repo.resolve()
    files = git_status(root) if git_available else []
    baseline = load_baseline(root, baseline_path)
    return {
        "tool": "agent-worktree-doctor",
        "created_at": now_iso(),
        "platform": platform.platform(),
        "root": str(root),
        "git_available": git_available,
        "changed_files": [dataclasses.asdict(item) for item in files],
        "numstat": git_numstat(root) if git_available else [],
        "risks": classify_risks(files),
        "baseline": compare_baseline(root, files, baseline),
        "context": context_scan(root, max_file_kb=max_file_kb),
    }


def line(text: str = "") -> str:
    return text + "\n"


def render_md(data: dict[str, Any], lang: str) -> str:
    sections: list[str] = []
    if lang in {"zh", "both"}:
        sections.append(render_zh(data))
    if lang == "both":
        sections.append("\n---\n")
    if lang in {"en", "both"}:
        sections.append(render_en(data))
    return "".join(sections)


def risk_level(data: dict[str, Any]) -> str:
    changed = len(data["changed_files"])
    risks = len(data["risks"])
    overlap = len(data["baseline"].get("overlap", []))
    if risks >= 8 or changed >= 25 or overlap >= 3:
        return "high"
    if risks >= 3 or changed >= 8 or overlap:
        return "medium"
    return "low"


def render_zh(data: dict[str, Any]) -> str:
    level_map = {"low": "低", "medium": "中", "high": "高"}
    level = level_map[risk_level(data)]
    out = []
    out.append(line("# Agent Worktree Doctor 报告"))
    out.append(line())
    out.append(line(f"- 生成时间：`{data['created_at']}`"))
    out.append(line(f"- 根目录：`{data['root']}`"))
    out.append(line(f"- Git 可用：`{data['git_available']}`"))
    out.append(line(f"- 风险等级：**{level}**"))
    out.append(line())
    out.append(line("## 工作区变化"))
    files = data["changed_files"]
    if files:
        for item in files[:80]:
            out.append(line(f"- `{item['status']}` `{item['path']}` ({item['category']})"))
        if len(files) > 80:
            out.append(line(f"- 其余 {len(files) - 80} 个文件已省略。"))
    else:
        out.append(line("- 未发现 Git 工作区改动，或当前目录不是 Git 仓库。"))
    out.append(line())
    out.append(line("## Baseline 对比"))
    base = data["baseline"]
    if base.get("available"):
        out.append(line(f"- baseline 时间：`{base.get('created_at')}`"))
        out.append(line(f"- baseline 前已有改动：{len(base['pre_existing'])} 个"))
        out.append(line(f"- baseline 后新增/变更：{len(base['new_or_changed_after_baseline'])} 个"))
        out.append(line(f"- 可能被 AI 继续改动的原有脏文件：{len(base['overlap'])} 个"))
        for path in base["overlap"][:20]:
            out.append(line(f"- overlap: `{path}`"))
    else:
        out.append(line("- 没有 baseline，无法可靠区分用户原有改动和 AI 新改动。下次运行前先执行 `snapshot`。"))
    out.append(line())
    out.append(line("## 风险信号"))
    if data["risks"]:
        for risk in data["risks"][:80]:
            out.append(line(f"- `{risk['path']}`：{risk['risk']}，状态 `{risk['status']}`"))
    else:
        out.append(line("- 未发现明显高风险文件类型。"))
    out.append(line())
    out.append(line("## 上下文卫生"))
    ctx = data["context"]
    out.append(line(f"- 扫描文件数：{ctx['scanned_files']}"))
    out.append(line(f"- 扫描体积：{ctx['scanned_kb']} KB"))
    out.append(line(f"- 粗略 token 估计：{ctx['estimated_tokens']}"))
    if ctx["omitted_dirs"]:
        omitted = ", ".join(f"{k} x{v}" for k, v in sorted(ctx["omitted_dirs"].items()))
        out.append(line(f"- 已跳过噪声目录：{omitted}"))
    if ctx["large_files"]:
        out.append(line("### 大文件"))
        for row in ctx["large_files"][:15]:
            out.append(line(f"- `{row['path']}`：{row['kb']} KB"))
    if ctx["noisy_files"]:
        out.append(line("### 可能污染上下文的文件"))
        for row in ctx["noisy_files"][:15]:
            out.append(line(f"- `{row['path']}`：{row['reason']}"))
    out.append(line())
    out.append(line("## 建议"))
    out.append(line("- 如果要让 AI 继续改代码，先检查风险信号里的 lockfile、环境文件、CI 配置和迁移文件。"))
    out.append(line("- 如果存在 overlap 文件，优先人工确认，避免覆盖用户原有改动。"))
    out.append(line("- 把构建产物、日志、大型数据文件加入 agent ignore 或提示 AI 不要读取。"))
    out.append(line("- 对高风险改动先运行测试，再让 AI 继续扩大修改范围。"))
    return "".join(out)


def render_en(data: dict[str, Any]) -> str:
    level = risk_level(data)
    out = []
    out.append(line("# Agent Worktree Doctor Report"))
    out.append(line())
    out.append(line(f"- Generated at: `{data['created_at']}`"))
    out.append(line(f"- Root: `{data['root']}`"))
    out.append(line(f"- Git available: `{data['git_available']}`"))
    out.append(line(f"- Risk level: **{level}**"))
    out.append(line())
    out.append(line("## Worktree Changes"))
    files = data["changed_files"]
    if files:
        for item in files[:80]:
            out.append(line(f"- `{item['status']}` `{item['path']}` ({item['category']})"))
        if len(files) > 80:
            out.append(line(f"- {len(files) - 80} additional files omitted."))
    else:
        out.append(line("- No Git worktree changes found, or this path is not a Git repository."))
    out.append(line())
    out.append(line("## Baseline Comparison"))
    base = data["baseline"]
    if base.get("available"):
        out.append(line(f"- Baseline created at: `{base.get('created_at')}`"))
        out.append(line(f"- Pre-existing dirty files: {len(base['pre_existing'])}"))
        out.append(line(f"- New/changed after baseline: {len(base['new_or_changed_after_baseline'])}"))
        out.append(line(f"- Pre-existing files touched again: {len(base['overlap'])}"))
        for path in base["overlap"][:20]:
            out.append(line(f"- overlap: `{path}`"))
    else:
        out.append(line("- No baseline found. Run `snapshot` before the next agent session to separate user changes from agent changes."))
    out.append(line())
    out.append(line("## Risk Flags"))
    if data["risks"]:
        for risk in data["risks"][:80]:
            out.append(line(f"- `{risk['path']}`: {risk['risk']}, status `{risk['status']}`"))
    else:
        out.append(line("- No obvious high-risk file categories detected."))
    out.append(line())
    out.append(line("## Context Hygiene"))
    ctx = data["context"]
    out.append(line(f"- Scanned files: {ctx['scanned_files']}"))
    out.append(line(f"- Scanned size: {ctx['scanned_kb']} KB"))
    out.append(line(f"- Rough token estimate: {ctx['estimated_tokens']}"))
    if ctx["omitted_dirs"]:
        omitted = ", ".join(f"{k} x{v}" for k, v in sorted(ctx["omitted_dirs"].items()))
        out.append(line(f"- Omitted noisy directories: {omitted}"))
    if ctx["large_files"]:
        out.append(line("### Large Files"))
        for row in ctx["large_files"][:15]:
            out.append(line(f"- `{row['path']}`: {row['kb']} KB"))
    if ctx["noisy_files"]:
        out.append(line("### Likely Context Noise"))
        for row in ctx["noisy_files"][:15]:
            out.append(line(f"- `{row['path']}`: {row['reason']}"))
    out.append(line())
    out.append(line("## Recommendations"))
    out.append(line("- Review lockfiles, environment files, CI config, and migrations before continuing agent edits."))
    out.append(line("- If overlap files exist, inspect them manually to avoid overwriting pre-existing user work."))
    out.append(line("- Exclude build output, logs, and large data files from agent context."))
    out.append(line("- Run tests before broadening the agent's edit scope when risk flags are present."))
    return "".join(out)


def command_snapshot(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve() if args.output else None
    out = snapshot(Path(args.path).resolve(), output)
    print(f"snapshot written: {out}")
    return 0


def command_report(args: argparse.Namespace) -> int:
    path = Path(args.path).resolve()
    baseline = Path(args.baseline).resolve() if args.baseline else None
    data = build_report(path, baseline, args.max_file_kb)
    root = Path(data["root"])
    md_path = Path(args.output).resolve() if args.output else root / REPORT_MD
    json_path = Path(args.json_output).resolve() if args.json_output else root / REPORT_JSON
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_md(data, args.lang), encoding="utf-8")
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"markdown report: {md_path}")
    print(f"json report: {json_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent_worktree_doctor",
        description="Audit AI coding worktree changes and context bloat.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Create a pre-agent baseline snapshot.")
    snap.add_argument("path", nargs="?", default=".", help="Repository or project path.")
    snap.add_argument("--output", help="Custom baseline JSON path.")
    snap.set_defaults(func=command_snapshot)

    report = sub.add_parser("report", help="Generate Markdown and JSON diagnostics.")
    report.add_argument("path", nargs="?", default=".", help="Repository or project path.")
    report.add_argument("--baseline", help="Baseline JSON path. Defaults to .agent-worktree-doctor/baseline.json.")
    report.add_argument("--output", help="Markdown report path.")
    report.add_argument("--json-output", help="JSON report path.")
    report.add_argument("--lang", choices=["zh", "en", "both"], default="both", help="Report language.")
    report.add_argument("--max-file-kb", type=int, default=200, help="Large-file threshold for context scan.")
    report.set_defaults(func=command_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
