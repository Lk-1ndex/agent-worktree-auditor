---
name: agent-worktree-doctor
description: Use this skill before, during, or after AI coding sessions to inspect Git worktree risk, distinguish pre-existing changes from new agent changes when a baseline snapshot exists, find context bloat, and generate bilingual Markdown/JSON reports for Codex, Claude Code, Cursor, or other AI coding workflows.
metadata:
  short-description: Diagnose AI coding worktree and context risk
---

# Agent Worktree Doctor

Use this skill when the user wants to make AI coding safer, review what an AI agent changed, create a pre-agent baseline, inspect context-window bloat, or produce an audit report for Codex/Claude Code/Cursor/Copilot-style workflows.

## Quick Workflow

1. Before an AI coding run, create a baseline snapshot:

```bash
python scripts/agent_worktree_doctor.py snapshot /path/to/repo
```

2. After the AI coding run, generate a report:

```bash
python scripts/agent_worktree_doctor.py report /path/to/repo --lang both
```

3. If the user did not take a snapshot, still run `report`; it will analyze the current Git state and context hygiene, but it cannot reliably label changes as pre-existing vs agent-made.

## What To Look For

- **Pre-existing changes**: dirty files already present in the baseline.
- **New agent changes**: files changed after the baseline snapshot.
- **Risk flags**: lockfiles, environment files, CI configs, migrations, generated files, deleted files, binary assets, broad churn.
- **Context bloat**: large files, logs, generated folders, vendored dependencies, notebooks/data files, build artifacts.

## Output

The script writes:

- `agent-worktree-doctor-report.md`
- `agent-worktree-doctor-report.json`
- `.agent-worktree-doctor/baseline.json` when `snapshot` is used

Reports are bilingual by default when `--lang both` is used, and can be Chinese-only or English-only with `--lang zh` or `--lang en`.

## Platform Notes

The script uses only Python standard library plus Git commands. It works on Windows, macOS, and Linux when Python 3.9+ and Git are available.

If Git is not available or the target is not a Git repository, the script still performs a filesystem context scan and explains what it could not inspect.

