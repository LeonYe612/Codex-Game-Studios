# Codex Game Studios

Codex Game Studios is a Codex-native, automation-first game development studio
workflow adapted from [Donchitos/Claude-Code-Game-Studios](https://github.com/Donchitos/Claude-Code-Game-Studios).

It keeps the original Claude Code template while adding a Codex plugin layer:
natural-language routing, project stage detection, quality gates, expert role
references, and practical scripts for validating game projects.

## What Is Included

- **Codex plugin manifest** in `plugins/codex-game-studios/.codex-plugin/plugin.json`
- **77 Codex skills** in `plugins/codex-game-studios/skills/`: 72 adapted studio workflows plus 5
  Codex-native orchestration and automation skills
- **49 expert references** in `plugins/codex-game-studios/agents/`: creative, technical, production,
  engine, QA, release, and discipline specialists
- **Automation scripts** in `plugins/codex-game-studios/scripts/` for project health checks, stage
  detection, validation, and local installation
- **Original Claude template** in `.claude/` for users who still want Claude
  Code compatibility

## Recommended Codex Usage

Use natural language. You do not need to memorize command names:

```text
Use Codex Game Studios to start my game project.
Check my game project and recommend the next step.
Run the Codex Game Studios quality gate.
Ask the creative director to review this concept.
```

The main Codex-native entry points are:

- `studio-router`: chooses the right workflow from natural language
- `studio-doctor`: checks plugin and project health
- `studio-stage-detect`: detects the current game project stage
- `agent-consult`: applies one of the expert role references
- `automation-gate`: runs Codex-native quality gates

## Local Codex Installation

Clone the repository:

```bash
git clone git@github.com:LeonYe612/Codex-Game-Studios.git
cd Codex-Game-Studios
```

Add this repository as a local marketplace, then install the plugin:

```bash
codex plugin marketplace add .
codex plugin add codex-game-studios@codex-game-studios
```

Restart Codex after installation. The plugin is installed into Codex's managed
plugin cache; do not copy the repository directory into `~/.codex/plugins/`.

To install directly from the private Git repository without cloning it first:

```bash
codex plugin marketplace add git@github.com:LeonYe612/Codex-Game-Studios.git
codex plugin add codex-game-studios@codex-game-studios
```

## Enable Or Disable

To remove the plugin and its discovery metadata from new Codex sessions:

```bash
codex plugin remove codex-game-studios@codex-game-studios
```

To reinstall it later:

```bash
codex plugin add codex-game-studios@codex-game-studios
```

For a reversible switch that keeps the installed files, edit
`~/.codex/config.toml`:

```toml
[plugins."codex-game-studios@codex-game-studios"]
enabled = false
```

Set it back to `true` and restart Codex to re-enable all Skills. The CLI does not
currently expose a dedicated `plugin enable`/`plugin disable` subcommand; direct
configuration is the supported fallback.

## Automation

The automation scripts require PowerShell 7 (`pwsh`). Install it on macOS with
`brew install --cask powershell`. The natural-language studio skills do not
require PowerShell.

Run the self-check:

```powershell
.\plugins\codex-game-studios\scripts\cgs-doctor.ps1
```

Detect a game project's current stage:

```powershell
.\plugins\codex-game-studios\scripts\cgs-detect-stage.ps1 -Root "path\to\your-game"
```

Run project validation:

```powershell
.\plugins\codex-game-studios\scripts\cgs-validate-project.ps1 -Root "path\to\your-game"
```

Check skill discovery metadata without PowerShell:

```bash
python3 plugins/codex-game-studios/scripts/skill-metadata-check.py --json
```

## Claude Code Compatibility

The original `.claude/` directory is preserved for Claude Code users. Codex
Game Studios does not require a Claude subscription or Claude CLI. The Codex
plugin layer is the recommended path for Codex users.

Claude Code hooks and Codex automation are different systems. In this port,
Codex quality gates are implemented through skills and scripts instead of
Claude session lifecycle hooks.

## Attribution

This project is based on
[Donchitos/Claude-Code-Game-Studios](https://github.com/Donchitos/Claude-Code-Game-Studios),
released under the MIT License. See `ATTRIBUTION.md` and `LICENSE`.

---

# Codex Game Studios 中文说明

Codex Game Studios 是一个面向 Codex 的游戏开发工作流插件，重点是
“自动化优先 + 自然语言触发”。它改编自
[Donchitos/Claude-Code-Game-Studios](https://github.com/Donchitos/Claude-Code-Game-Studios)，
同时保留原 `.claude/` 模板，方便需要 Claude Code 的用户继续使用。

## 包含内容

- `plugins/codex-game-studios/.codex-plugin/plugin.json`：Codex 插件入口
- `plugins/codex-game-studios/skills/`：77 个 Codex skills，包括 72 个移植工作流和 5 个 Codex 原生编排技能
- `plugins/codex-game-studios/agents/`：49 个专家画像，供 Codex 在策划、技术、制作、QA、发行等场景引用
- `plugins/codex-game-studios/scripts/`：项目检查、阶段检测、质量门、本地安装脚本
- `.claude/`：原 Claude Code 模板兼容层

## 推荐用法

直接用自然语言告诉 Codex：

```text
用 Codex Game Studios 帮我开始一个游戏项目。
检查我的游戏项目，然后告诉我下一步做什么。
运行 Codex Game Studios 的质量门。
让 creative-director 看一下这个游戏概念。
```

Codex 版的主要入口：

- `studio-router`：根据自然语言选择工作流
- `studio-doctor`：检查插件和项目健康状态
- `studio-stage-detect`：判断项目阶段
- `agent-consult`：按专家画像进行咨询或评审
- `automation-gate`：运行质量门

## 安装

```bash
git clone https://github.com/LeonYe612/Codex-Game-Studios.git
cd Codex-Game-Studios
codex plugin marketplace add .
codex plugin add codex-game-studios@codex-game-studios
```

不要手动把仓库复制到 `~/.codex/plugins/`；Codex 会将插件安装到自己的缓存目录。
安装后重启 Codex。

也可以不预先克隆，直接从私人 Git 仓库安装：

```bash
codex plugin marketplace add git@github.com:LeonYe612/Codex-Game-Studios.git
codex plugin add codex-game-studios@codex-game-studios
```

## 启停

彻底移除插件及其 Skill 元数据：

```bash
codex plugin remove codex-game-studios@codex-game-studios
```

重新安装：

```bash
codex plugin add codex-game-studios@codex-game-studios
```

如需保留已安装文件、只临时关闭，可在 `~/.codex/config.toml` 中设置：

```toml
[plugins."codex-game-studios@codex-game-studios"]
enabled = false
```

改回 `true` 并重启 Codex 即可恢复。当前 Codex CLI 没有独立的
`plugin enable` / `plugin disable` 子命令，直接配置是受支持的替代方式。

## 说明

Codex 目前不使用 Claude Code 的 `.claude/agents` 原生注册机制。本项目的
Codex 版采用更适合 Codex 的方式：自然语言路由、自动化脚本、质量门和专家画像
引用。这样不用 Claude 会员，也能在 Codex 里获得类似游戏工作室的结构化协作体验。
