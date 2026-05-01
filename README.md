# Agent Worktree Auditor / AI 编程工作区审计器

Agent Worktree Auditor is a portable skill and CLI helper for AI coding workflows. It helps Codex, Claude Code, Cursor, Copilot-style agents, and human developers inspect what changed, what looks risky, and what may be wasting context window space.

Agent Worktree Auditor 是一个可直接拷贝使用的 AI 编程辅助 Skill 和命令行工具。它帮助 Codex、Claude Code、Cursor、Copilot 类工作流检查工作区改动、风险文件和上下文污染源。

## What it does

- Creates a baseline before an AI agent starts editing.
- Reports changed files, risky edits, deleted files, lockfiles, environment files, CI configs, migrations, and generated assets.
- Separates pre-existing dirty files from new agent changes when a baseline exists.
- Scans large files, logs, generated folders, vendored dependencies, and data files that can waste context.
- Generates bilingual Markdown and JSON reports.

## 它能做什么

- 在 AI 开始改代码前创建 baseline 快照。
- 检查改动文件、高风险文件、删除文件、锁文件、环境文件、CI 配置、迁移文件和构建产物。
- 如果存在 baseline，可以区分“用户原有改动”和“AI 后续新增改动”。
- 扫描大文件、日志、生成目录、依赖目录和数据文件，找出可能浪费上下文窗口的内容。
- 生成中英文 Markdown 报告和 JSON 报告。

## Install as a Codex skill

Copy the skill folder into your Codex skills directory:

```powershell
Copy-Item -Recurse .\skills\agent-worktree-auditor "$env:USERPROFILE\.codex\skills\agent-worktree-auditor"
```

macOS/Linux:

```bash
mkdir -p ~/.codex/skills
cp -R ./skills/agent-worktree-auditor ~/.codex/skills/agent-worktree-auditor
```

Then invoke it in Codex:

```text
Use $agent-worktree-auditor to snapshot this repo before edits and generate a report afterward.
```

## 安装为 Codex Skill

把 Skill 文件夹复制到 Codex skills 目录：

```powershell
Copy-Item -Recurse .\skills\agent-worktree-auditor "$env:USERPROFILE\.codex\skills\agent-worktree-auditor"
```

之后可以在 Codex 里直接调用：

```text
使用 $agent-worktree-auditor，在改代码前创建快照，改完后生成风险报告。
```

## CLI usage

The script only needs Python 3.9+ and Git. It works on Windows, macOS, and Linux.

```bash
python skills/agent-worktree-auditor/scripts/agent_worktree_auditor.py snapshot /path/to/repo
python skills/agent-worktree-auditor/scripts/agent_worktree_auditor.py report /path/to/repo --lang both
```

Use it from any AI coding tool by asking the agent to run those commands before and after an editing task. Codex can invoke it as a skill; Claude Code, Cursor, terminal agents, and CI jobs can invoke the same Python script directly.

Outputs:

- `agent-worktree-auditor-report.md`
- `agent-worktree-auditor-report.json`
- `.agent-worktree-auditor/baseline.json`

## 命令行用法

脚本只依赖 Python 3.9+ 和 Git，支持 Windows、macOS、Linux。

```bash
python skills/agent-worktree-auditor/scripts/agent_worktree_auditor.py snapshot /path/to/repo
python skills/agent-worktree-auditor/scripts/agent_worktree_auditor.py report /path/to/repo --lang both
```

在不支持 Skill 的平台上，也可以直接让 AI 编程工具运行这两条命令。Codex 可以用 Skill 方式调用；Claude Code、Cursor、终端 Agent、CI 任务可以直接调用同一个 Python 脚本。

输出文件：

- `agent-worktree-auditor-report.md`
- `agent-worktree-auditor-report.json`
- `.agent-worktree-auditor/baseline.json`

## Why this exists

AI coding agents are useful, but they can accidentally touch unrelated files, overwrite pre-existing user changes, or flood their context with build output and logs. This project is a small guardrail: it does not replace code review, but it makes the worktree easier to inspect before the next agent step.

## 为什么要做这个

AI 编程工具很好用，但它们也可能顺手改到不该改的文件、覆盖用户原本的改动，或者把构建产物和日志塞进上下文。这个项目不是替代代码审查，而是给 AI 编程流程加一个轻量护栏，让下一步改动更清楚、更可控。
