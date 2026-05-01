# Agent Worktree Doctor Prompt

Use this prompt in AI coding tools that do not support Codex skills directly.

## English

Before editing this repository, run:

```bash
python skills/agent-worktree-doctor/scripts/agent_worktree_doctor.py snapshot .
```

After editing, run:

```bash
python skills/agent-worktree-doctor/scripts/agent_worktree_doctor.py report . --lang both
```

Read `agent-worktree-doctor-report.md` before summarizing the work. Pay special attention to pre-existing dirty files, high-risk file categories, deleted files, and context bloat.

## 中文

在修改这个仓库之前，先运行：

```bash
python skills/agent-worktree-doctor/scripts/agent_worktree_doctor.py snapshot .
```

修改完成后运行：

```bash
python skills/agent-worktree-doctor/scripts/agent_worktree_doctor.py report . --lang both
```

总结工作前先阅读 `agent-worktree-doctor-report.md`。重点检查用户原有脏文件、高风险文件类型、被删除文件和上下文污染源。
