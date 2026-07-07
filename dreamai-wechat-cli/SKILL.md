---
name: dreamai-wechat-cli
description: >-
  DreamAI fork of Wenyan CLI (@tornadoami/dreamai-wechat-cli, command `dreamai-wechat-cli`): WeChat Official Account Markdown layout, publish to draft box, **贴图草稿 `newspic publish`** (official `article_type=newspic`), advanced mass-send (`mass sendall`), draft-box REST-style APIs via `draft` (including `merge-add`), self-update (`update`), and optional `serve` HTTP mode. Use when the user names DreamAI wechat CLI, @tornadoami/dreamai-wechat-cli, draft/mass/newspic/update subcommands, or wants WeChat OA publishing outside upstream `wenyan`.
  Triggers: dreamai-wechat-cli、微信公众号草稿、贴图、newspic、mass 群发、draft merge-add、update 升级、serve 远程发布、--debug 排查。
  Requires: Node/npm; env WECHAT_APP_ID and WECHAT_APP_SECRET for publish; IP whitelist or compatible Server unless using --server.
  Do not use: upstream-only `wenyan` / `@wenyan-md/cli` workflows unless the user explicitly wants that package; then prefer the `dreamai-wenyan-cli` skill.
compatibility: Requires Node.js 18+ and npm; binary `dreamai-wechat-cli` on PATH (install via `npm install -g @tornadoami/dreamai-wechat-cli`, upgrade via `dreamai-wechat-cli update --yes`); outbound HTTPS. For WeChat draft publish, set WECHAT_APP_ID and WECHAT_APP_SECRET in the same environment as the CLI; public IP usually must be on the OA IP allowlist unless using Server mode (--server, --api-key). **图文** draft title ≤32 字；**贴图 newspic** 标题建议 ≤20 字（`--max-title-chars`，见官方 draft_add）。
allowed-tools: Bash(npm:*) Bash(node:*) Bash(dreamai-wechat-cli:*)
metadata:
  upstream-fork-of: "https://github.com/caol64/wenyan-cli"
  repo: "https://github.com/iamtornado/dreamai-wechat-cli"
  npm-package: "@tornadoami/dreamai-wechat-cli"
---

# DreamAI 微信公众号 CLI（dreamai-wechat-cli）

[dreamai-wechat-cli](https://github.com/iamtornado/dreamai-wechat-cli) 是上游 [wenyan-cli](https://github.com/caol64/wenyan-cli) 的 **DreamAI 维护分支**：npm 包 **`@tornadoami/dreamai-wechat-cli`**，全局命令 **`dreamai-wechat-cli`**（与上游全局命令 `wenyan` 不同）。侧重公众号排版与草稿发布，并扩展 **`newspic publish`（贴图草稿）**、**`draft` 子命令（含 `merge-add`）**、**`mass sendall`**、**`update`** 与 **`serve` HTTP 服务**。

**集成约定**：下游项目（如 ComicAutoPub）应通过 **已安装的 npm 全局 CLI** 调用，**不要**直接引用仓库源码或 `dist/cli.js`；升级用 `npm install -g @tornadoami/dreamai-wechat-cli@latest` 或 `dreamai-wechat-cli update --yes`。

本 Skill 面向 **AI Agent**：优先 **速查清单** 与 **黄金路径**；细则见 `references/`。

## References

| 文档 | 用途 |
| ---- | ---- |
| [references/configuration.md](references/configuration.md) | 环境变量、frontmatter、IP 白名单、图片路径、Server 模式、`draft` / `serve` 提示 |
| [references/troubleshooting.md](references/troubleshooting.md) | 按症状排查（凭证、白名单、图片、Server、调试开关） |
| [references/openclaw.md](references/openclaw.md) | 可选 Openclaw 安装片段 |

## Agent 速查（执行前读一遍）

1. **目标**：仅预览 HTML → `render`；发**图文**草稿 → `publish`；发**贴图**草稿 → `newspic publish`；草稿查询/维护 → `draft …`；多草稿合并 → `draft merge-add …`；群发 → `mass sendall …`；升级 CLI → `update`；自建 HTTP 入口 → `serve`。
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
| 公众号排版、发草稿（图文或贴图）、`newspic`、`draft` 子命令、`serve` | 与公众号/本 CLI 无关的通用 Markdown→HTML |
| 安装/排查、Server 模式、CI 管道发布 | 未授权操作微信账号或未配置环境却要求直接发布 |

## Prerequisites

- **Node.js 18+** + npm：`npm install -g @tornadoami/dreamai-wechat-cli`
- 或从 GitHub：`npm install -g github:iamtornado/dreamai-wechat-cli`
- 验证：`dreamai-wechat-cli --help` / `dreamai-wechat-cli --version`
- 发布与 API 前置条件见 [configuration.md](references/configuration.md)

## 黄金路径（默认工作流）

1. **确认意图**：预览 → `render`；**图文**草稿 → `publish`；**贴图**草稿 → `newspic publish`；草稿 CRUD/查询 → `draft`；HTTP 服务 → `serve`。
2. **读文件**：检查 frontmatter、`title` 长度、`author` 长度、`source_url` 体量。
3. **必要时补全 frontmatter**：仅当用户明确要求且字段缺失时确认；不要编造 AppID/Secret；超长字段先提示按微信接口缩短。
4. **常用命令**（本地文件优先）：

   ```bash
   dreamai-wechat-cli publish -f /absolute/or/relative/path/to/article.md
   ```

   **贴图**草稿（官方 `article_type=newspic`，仅进草稿箱）：

   ```bash
   dreamai-wechat-cli newspic publish --from-dir /path/to/post_bundle
   # 或手动：--title … --content … --image a.png --image b.png
   ```

   目录约定（`--from-dir`）：可选 `wechat_post.json`（`title` + `description`）+ 有序图片（如 `panel_01.png`…）；ComicAutoPub 输出目录符合此约定。

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

7. **群发**：认证号与接口权限、IP 白名单、`media_id` 来源都要先确认；优先参考仓库 [docs/mass.md](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/mass.md) 与 [docs/draft-merge.md](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/draft-merge.md)。
8. **升级**：版本相关问题先 `dreamai-wechat-cli update --check`，需要非交互升级时用 `--yes`。
9. **汇报**：按 **Agent 输出规范**；勿粘贴 Secret。

## 命令与输入方式（简表）

| 目的 | 命令骨架 |
| ---- | -------- |
| 发布图文草稿 | `dreamai-wechat-cli publish -f <path-or-url-or-inline>` |
| 发布贴图草稿 | `dreamai-wechat-cli newspic publish --from-dir <dir>` 或 `--title` + `--content` + `--image` |
| 仅渲染 | `dreamai-wechat-cli render -f <…>` |
| 主题 | `dreamai-wechat-cli theme`（`--help` 为准） |
| 草稿箱 API | `dreamai-wechat-cli draft <subcommand> …`（含 `merge-add`） |
| 群发 | `dreamai-wechat-cli mass sendall --media-id <id> [--tag-id <n>]` |
| CLI 升级 | `dreamai-wechat-cli update [--check\|--yes\|--to <version>]` |
| HTTP Server | `dreamai-wechat-cli serve`（见仓库 docs） |

仓库文档索引：[publish](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/publish.md)、[**newspic**](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/newspic.md)、[theme](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/theme.md)、[mass](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/mass.md)、[draft-merge](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/draft-merge.md)、[update](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/update.md)、[server](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/server.md)。

| 输入方式 | 示例 | Agent 注意 |
| -------- | ---- | ---------- |
| 本地路径 | `dreamai-wechat-cli publish -f ./posts/a.md` | 相对路径图片以此方式最稳 |
| URL | `dreamai-wechat-cli publish -f https://…/a.md` | 确认可访问 |
| 管道 | `cat a.md \| dreamai-wechat-cli publish` | 适合 CI |
| 内联 | `dreamai-wechat-cli publish "# t\n…"` | 仅短篇 |

## 文章格式（Frontmatter）

**仅 `publish`（图文 `news`）** 需要 Markdown + YAML frontmatter（`title` 必填，且符合微信草稿字段上限）；字段表与封面说明见 [configuration.md](references/configuration.md)。

**`newspic publish`（贴图）** 不用 Markdown；用 `--title`、`--content`（描述正文），或 `--from-dir` 读取目录内 `wechat_post.json` + 图片。贴图标题建议 **≤20 字**（`--max-title-chars 20`）。

```yaml
---
title: 文章标题
cover: /path/to/cover.jpg
author: 作者
source_url: https://example.com/original
---
```

## Agent 输出规范（完成后必读）

- **做了什么**：例如已执行 `dreamai-wechat-cli publish -f …`、`newspic publish --from-dir …` 或 `draft …`。
- **结果**：成功/失败；成功时提示在 **微信公众平台 → 草稿箱** 或团队约定位置查看。
- **失败时**：概括错误；指向环境变量、白名单、图片、`--server`/`--api-key`；建议 [troubleshooting.md](references/troubleshooting.md)。
- **不要输出**：`WECHAT_APP_SECRET`、完整 `--api-key`。

## 校验与规范

- Skill 格式：<https://agentskills.io/specification>
- 本地校验（需 Node）：`npx skills-ref validate ./dreamai-wechat-cli`

## 维护记录

- 2026-04-09：初始化 skill（对齐 dreamai-wechat-cli 仓库与 npm 包名）。
- 2026-04-21：同步 CLI 新增能力（`mass sendall`、`draft merge-add`、`update`）并更新命令速查。
- 2026-07-07：新增 `newspic publish`（贴图草稿、`--from-dir`）；强调通过 npm 全局 CLI 集成、勿引用源码路径；贴图标题 ≤20 字。
