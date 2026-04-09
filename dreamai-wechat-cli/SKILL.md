---
name: dreamai-wechat-cli
description: >-
  DreamAI fork of Wenyan CLI (@tornadoami/dreamai-wechat-cli, command `dreamai-wechat-cli`): WeChat Official Account Markdown layout, publish to draft box, draft-box REST-style APIs via `draft`, and optional `serve` HTTP mode. Use when the user names DreamAI wechat CLI, @tornadoami/dreamai-wechat-cli, draft subcommands, or wants WeChat OA publishing outside upstream `wenyan`.
  Triggers: dreamai-wechat-cli、微信公众号草稿、draft count/list/get、serve 远程发布、--debug 排查。
  Requires: Node/npm; env WECHAT_APP_ID and WECHAT_APP_SECRET for publish; IP whitelist or compatible Server unless using --server.
  Do not use: upstream-only `wenyan` / `@wenyan-md/cli` workflows unless the user explicitly wants that package; then prefer the `dreamai-wenyan-cli` skill.
compatibility: Requires Node.js 18+ and npm; binary `dreamai-wechat-cli` on PATH; outbound HTTPS. For WeChat draft publish, set WECHAT_APP_ID and WECHAT_APP_SECRET in the same environment as the CLI; public IP usually must be on the OA IP allowlist unless using Server mode (--server, --api-key). WeChat draft_add API limits include title max 32 字 and author max 16 字 (see official draft_add docs).
allowed-tools: Bash(npm:*) Bash(node:*) Bash(dreamai-wechat-cli:*)
metadata:
  upstream-fork-of: "https://github.com/caol64/wenyan-cli"
  repo: "https://github.com/iamtornado/dreamai-wechat-cli"
  npm-package: "@tornadoami/dreamai-wechat-cli"
---

# DreamAI 微信公众号 CLI（dreamai-wechat-cli）

[dreamai-wechat-cli](https://github.com/iamtornado/dreamai-wechat-cli) 是上游 [wenyan-cli](https://github.com/caol64/wenyan-cli) 的 **DreamAI 维护分支**：npm 包 **`@tornadoami/dreamai-wechat-cli`**，全局命令 **`dreamai-wechat-cli`**（与上游全局命令 `wenyan` 不同）。侧重公众号排版、草稿发布，并扩展 **`draft` 子命令**与 **`serve` HTTP 服务**。

本 Skill 面向 **AI Agent**：优先 **速查清单** 与 **黄金路径**；细则见 `references/`。

## References

| 文档 | 用途 |
| ---- | ---- |
| [references/configuration.md](references/configuration.md) | 环境变量、frontmatter、IP 白名单、图片路径、Server 模式、`draft` / `serve` 提示 |
| [references/troubleshooting.md](references/troubleshooting.md) | 按症状排查（凭证、白名单、图片、Server、调试开关） |
| [references/openclaw.md](references/openclaw.md) | 可选 Openclaw 安装片段 |

## Agent 速查（执行前读一遍）

1. **目标**：仅预览 HTML → `render`；发草稿 → `publish`；管理草稿 API → `draft …`；自建 HTTP 入口 → `serve`（见仓库 [docs/server.md](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/server.md)）。
2. **凭证**：发布或调草稿 API 时，`WECHAT_APP_ID` 与 `WECHAT_APP_SECRET` 须在**运行命令的环境**中可用；不要在聊天中索取或回显 Secret。
3. **网络/白名单**：本地直连时，出口 IP 通常需在公众号后台白名单；否则走 `--server` + API Key（见 [configuration.md](references/configuration.md)）。
4. **文稿**：Markdown 顶部需合法 YAML frontmatter，**`title` 必填**；**`title` ≤ 32 个字**、**`author`（若有）≤ 16 个字**；`source_url` 等限制同微信草稿接口。详见 [configuration.md](references/configuration.md)。
5. **图片**：文内相对路径图片在 **`-f` 指向本地文件** 时最可靠。
6. **调试**：可加 `--debug` 或设置 `DREAMAI_WECHAT_DEBUG=1`（`publish` 与 `draft` 均支持，以 CLI `--help` 为准）。
7. **失败后**：先读 stderr；再查 [troubleshooting.md](references/troubleshooting.md)；参数不确定时运行 `dreamai-wechat-cli <command> --help`。

## 何时使用 / 不使用

| 使用本 Skill | 不使用（除非用户改口） |
| ------------ | ---------------------- |
| 用户提到 DreamAI fork、`dreamai-wechat-cli`、`@tornadoami/dreamai-wechat-cli` | 明确只要上游 `wenyan` / `@wenyan-md/cli` → 用 **dreamai-wenyan-cli** skill |
| 公众号排版、发草稿、`draft` 子命令、`serve` | 与公众号/本 CLI 无关的通用 Markdown→HTML |
| 安装/排查、Server 模式、CI 管道发布 | 未授权操作微信账号或未配置环境却要求直接发布 |

## Prerequisites

- **Node.js 18+** + npm：`npm install -g @tornadoami/dreamai-wechat-cli`
- 或从 GitHub：`npm install -g github:iamtornado/dreamai-wechat-cli`
- 验证：`dreamai-wechat-cli --help` / `dreamai-wechat-cli --version`
- 发布与 API 前置条件见 [configuration.md](references/configuration.md)

## 黄金路径（默认工作流）

1. **确认意图**：预览 → `render`；发草稿 → `publish`；草稿 CRUD/查询 → `draft`；HTTP 服务 → `serve`。
2. **读文件**：检查 frontmatter、`title` 长度、`author` 长度、`source_url` 体量。
3. **必要时补全 frontmatter**：仅当用户明确要求且字段缺失时确认；不要编造 AppID/Secret；超长字段先提示按微信接口缩短。
4. **常用命令**（本地文件优先）：

   ```bash
   dreamai-wechat-cli publish -f /absolute/or/relative/path/to/article.md
   ```

   仅预览：

   ```bash
   dreamai-wechat-cli render -f /absolute/or/relative/path/to/article.md
   ```

5. **Server 模式**（用户已提供 server URL 与 api-key）：

   ```bash
   dreamai-wechat-cli publish -f article.md --server "https://api.example.com" --api-key "<user-supplied-key>"
   ```

6. **草稿 API**：子命令与字段以微信公众平台草稿管理为准；先运行：

   ```bash
   dreamai-wechat-cli draft --help
   ```

7. **汇报**：按 **Agent 输出规范**；勿粘贴 Secret。

## 命令与输入方式（简表）

| 目的 | 命令骨架 |
| ---- | -------- |
| 发布草稿 | `dreamai-wechat-cli publish -f <path-or-url-or-inline>` |
| 仅渲染 | `dreamai-wechat-cli render -f <…>` |
| 主题 | `dreamai-wechat-cli theme`（`--help` 为准） |
| 草稿箱 API | `dreamai-wechat-cli draft <subcommand> …` |
| HTTP Server | `dreamai-wechat-cli serve`（见仓库 docs） |

仓库文档索引：[publish](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/publish.md)、[theme](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/theme.md)、[server](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/server.md)。

| 输入方式 | 示例 | Agent 注意 |
| -------- | ---- | ---------- |
| 本地路径 | `dreamai-wechat-cli publish -f ./posts/a.md` | 相对路径图片以此方式最稳 |
| URL | `dreamai-wechat-cli publish -f https://…/a.md` | 确认可访问 |
| 管道 | `cat a.md \| dreamai-wechat-cli publish` | 适合 CI |
| 内联 | `dreamai-wechat-cli publish "# t\n…"` | 仅短篇 |

## 文章格式（Frontmatter）

发布前 Markdown **须** 以 YAML frontmatter 开头（`title` 必填，且符合微信草稿字段上限）；字段表与封面说明见 [configuration.md](references/configuration.md)。

```yaml
---
title: 文章标题
cover: /path/to/cover.jpg
author: 作者
source_url: https://example.com/original
---
```

## Agent 输出规范（完成后必读）

- **做了什么**：例如已执行 `dreamai-wechat-cli publish -f …` 或 `draft …`。
- **结果**：成功/失败；成功时提示在 **微信公众平台 → 草稿箱** 或团队约定位置查看。
- **失败时**：概括错误；指向环境变量、白名单、图片、`--server`/`--api-key`；建议 [troubleshooting.md](references/troubleshooting.md)。
- **不要输出**：`WECHAT_APP_SECRET`、完整 `--api-key`。

## 校验与规范

- Skill 格式：<https://agentskills.io/specification>
- 本地校验（需 Node）：`npx skills-ref validate ./dreamai-wechat-cli`

## 维护记录

- 2026-04-09：初始化 skill（对齐 dreamai-wechat-cli 仓库与 npm 包名）。
