# Agent Worktree Doctor：AI 编程工作区医生

这是一个面向 AI 编程流程的 Skill + CLI 小工具。它适合配合 Codex、Claude Code、Cursor、Copilot Agent 等使用，用来检查 AI 修改了哪些文件、哪些地方有风险、哪些内容可能浪费上下文窗口。

## 适用场景

- 让 AI 改代码前，先保存当前工作区状态。
- AI 改完代码后，快速生成改动风险报告。
- 区分用户原有改动和 AI 后续改动。
- 找出 lockfile、环境文件、CI 配置、数据库迁移、构建产物等高风险改动。
- 找出日志、大文件、生成文件、数据文件等上下文污染源。

## 安装为 Codex Skill

把 `skills/agent-worktree-doctor` 复制到 Codex skills 目录：

```powershell
Copy-Item -Recurse .\skills\agent-worktree-doctor "$env:USERPROFILE\.codex\skills\agent-worktree-doctor"
```

然后在 Codex 里这样调用：

```text
使用 $agent-worktree-doctor，在改代码前创建快照，改完后生成风险报告。
```

## 命令行使用

创建 baseline：

```bash
python skills/agent-worktree-doctor/scripts/agent_worktree_doctor.py snapshot /path/to/repo
```

生成中英文报告：

```bash
python skills/agent-worktree-doctor/scripts/agent_worktree_doctor.py report /path/to/repo --lang both
```

输出文件：

- `agent-worktree-doctor-report.md`
- `agent-worktree-doctor-report.json`
- `.agent-worktree-doctor/baseline.json`

## 平台支持

脚本只使用 Python 标准库和 Git 命令，支持：

- Windows PowerShell / Windows Terminal
- macOS Terminal
- Linux shell
- Codex、Claude Code、Cursor 等能运行本地命令的 AI 编程环境

## 项目定位

它不是又一个 AI 编程助手，也不是代码审查大模型。它是 AI 编程现场的小工具：帮你在下一步继续让 AI 修改之前，看清楚工作区是不是干净、改动是不是越界、上下文是不是太脏。

