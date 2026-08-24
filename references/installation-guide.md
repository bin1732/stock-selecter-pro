# references/installation-guide.md — 安装指南

> 本 skill 遵循 Agent Skills 规范组织（目录含 SKILL.md + references/ + scripts/），可装入任何支持 Agent Skills 规范的宿主（Claude Code / Codex / Cursor 等）。

## 安装要点

skill 的 `name` 为 `stock-selecter-pro`（frontmatter name 字段）。安装时请将解压内容放入**以该名称命名的目录**，宿主才能正确发现与加载。

### Claude Code（用户级）

```bash
mkdir -p ~/.claude/skills/stock-selecter-pro
# 将 SKILL.md、references/、scripts/ 解压到该目录
```

### Codex / OpenAI（用户级）

```bash
mkdir -p ~/.agents/skills/stock-selecter-pro
# 将 SKILL.md、references/、scripts/ 解压到该目录
```

### 项目级（仅当前项目生效）

```bash
mkdir -p .claude/skills/stock-selecter-pro
# 将 SKILL.md、references/、scripts/ 解压到该目录
```

## 升级与数据

- 升级前备份本地数据：`scripts/archive/stock_selecter.db`（策略表现档案库，本地 SQLite）与引导标记文件（`~/.stock_selecter_pro_guide_done`）。
- 升级时覆盖 `SKILL.md` / `references/` / `scripts/` 即可；删除档案库文件即可重置追踪数据，不影响核心功能。

## 环境要求

- Python ≥3.10（仅标准库，零外部依赖）。
- 联网数据获取：东方财富/腾讯/新浪公开行情接口（无需认证）；离线时数据接口明确失败并如实标注，不伪造数据。
