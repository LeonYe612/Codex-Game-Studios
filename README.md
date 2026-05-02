# Codex Game Studios

Codex Game Studios is a Codex-native, automation-first game development studio
workflow adapted from [Donchitos/Claude-Code-Game-Studios](https://github.com/Donchitos/Claude-Code-Game-Studios).

It keeps the original Claude Code template while adding a Codex plugin layer:
natural-language routing, project stage detection, quality gates, expert role
references, and practical scripts for validating game projects.

## What Is Included

- **Codex plugin manifest** in `.codex-plugin/plugin.json`
- **77 Codex skills** in `skills/`: 72 adapted studio workflows plus 5
  Codex-native orchestration and automation skills
- **49 expert references** in `agents/`: creative, technical, production,
  engine, QA, release, and discipline specialists
- **Automation scripts** in `scripts/` for project health checks, stage
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

```powershell
git clone https://github.com/swl521/Codex-Game-Studios.git
cd Codex-Game-Studios
```

Install it into your local Codex plugin directory:

```powershell
.\scripts\cgs-install-local.ps1
```

Then restart Codex or enable the local plugin if your Codex build requires
manual plugin activation.

## Automation

Run the self-check:

```powershell
.\scripts\cgs-doctor.ps1
```

Detect a game project's current stage:

```powershell
.\scripts\cgs-detect-stage.ps1 -Root "path\to\your-game"
```

Run project validation:

```powershell
.\scripts\cgs-validate-project.ps1 -Root "path\to\your-game"
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

- `.codex-plugin/plugin.json`：Codex 插件入口
- `skills/`：77 个 Codex skills，包括 72 个移植工作流和 5 个 Codex 原生编排技能
- `agents/`：49 个专家画像，供 Codex 在策划、技术、制作、QA、发行等场景引用
- `scripts/`：项目检查、阶段检测、质量门、本地安装脚本
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

```powershell
git clone https://github.com/swl521/Codex-Game-Studios.git
cd Codex-Game-Studios
.\scripts\cgs-install-local.ps1
```

安装后重启 Codex，或按你的 Codex 版本要求启用本地插件。

## 说明

Codex 目前不使用 Claude Code 的 `.claude/agents` 原生注册机制。本项目的
Codex 版采用更适合 Codex 的方式：自然语言路由、自动化脚本、质量门和专家画像
引用。这样不用 Claude 会员，也能在 Codex 里获得类似游戏工作室的结构化协作体验。
