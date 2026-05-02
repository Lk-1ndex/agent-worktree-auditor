"""CI smoke tests for Agent Worktree Auditor.

The project is a portable Codex skill, not a Python package. These checks keep
the release installable by validating the skill layout and exercising the script
against a temporary Git repository.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "agent-worktree-auditor"
SCRIPT = SKILL_DIR / "scripts" / "agent_worktree_auditor.py"


def run(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        raise AssertionError(f"command failed: {' '.join(args)}")
    return result


def assert_exists(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"missing required path: {path.relative_to(ROOT).as_posix()}")


def test_skill_layout() -> None:
    assert_exists(SKILL_DIR / "SKILL.md")
    assert_exists(SKILL_DIR / "agents" / "openai.yaml")
    assert_exists(SCRIPT)
    assert_exists(ROOT / "README.md")
    assert_exists(ROOT / "README.zh-CN.md")

    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").lstrip("\ufeff")
    if not skill_md.startswith("---"):
        raise AssertionError("SKILL.md must start with YAML frontmatter")
    if "name: agent-worktree-auditor" not in skill_md:
        raise AssertionError("SKILL.md frontmatter must declare the skill name")
    if "description:" not in skill_md:
        raise AssertionError("SKILL.md frontmatter must include a description")

    openai_yaml = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
    if "default_prompt:" not in openai_yaml:
        raise AssertionError("agents/openai.yaml must include default_prompt")
    if "$agent-worktree-auditor" not in openai_yaml:
        raise AssertionError("default_prompt should mention $agent-worktree-auditor")


def test_script_compiles_and_has_help() -> None:
    run([sys.executable, "-m", "compileall", "-q", str(SCRIPT)])
    help_output = run([sys.executable, str(SCRIPT), "--help"]).stdout
    if "snapshot" not in help_output or "report" not in help_output:
        raise AssertionError("CLI help should document snapshot and report commands")


def test_snapshot_and_report_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="agent-worktree-auditor-ci-") as tmp:
        repo = Path(tmp)
        run(["git", "init"], repo)
        run(["git", "config", "user.email", "ci@example.com"], repo)
        run(["git", "config", "user.name", "CI"], repo)

        (repo / "README.md").write_text("# Fixture\n", encoding="utf-8")
        run(["git", "add", "README.md"], repo)
        run(["git", "commit", "-m", "initial fixture"], repo)

        run([sys.executable, str(SCRIPT), "snapshot", str(repo)])
        (repo / ".env").write_text("TOKEN=placeholder\n", encoding="utf-8")
        (repo / "notes.md").write_text("agent change\n", encoding="utf-8")
        run([sys.executable, str(SCRIPT), "report", str(repo), "--lang", "both"])

        report_md = repo / "agent-worktree-auditor-report.md"
        report_json = repo / "agent-worktree-auditor-report.json"
        assert_exists(report_md)
        assert_exists(report_json)

        data = json.loads(report_json.read_text(encoding="utf-8"))
        paths = {item["path"] for item in data["changed_files"]}
        if ".env" not in paths or "notes.md" not in paths:
            raise AssertionError("report should include untracked fixture changes")
        risks = {item["risk"] for item in data["risks"]}
        if "environment or secret" not in risks:
            raise AssertionError("report should flag .env as environment or secret risk")


def main() -> int:
    test_skill_layout()
    test_script_compiles_and_has_help()
    test_snapshot_and_report_smoke()
    print("CI smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
