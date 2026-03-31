---
name: dreamai-wenyan-cli
description: >-
  Wenyan CLI (@wenyan-md/cli, command `wenyan`): render Markdown for WeChat Official Account layout and publish to the draft box. Use when the user wants WeChat OA publishing, styled HTML preview, theme management, or Server-mode / CI publishing.
  Triggers: 微信公众号草稿、排版预览、wenyan 安装与报错排查、--server 远程发布。
  Requires: Node/npm; env WECHAT_APP_ID and WECHAT_APP_SECRET for publish; IP whitelist or Wenyan Server unless using Server mode.
  Do not use: generic Markdown/HTML conversion with no WeChat/Wenyan context unless the user explicitly names Wenyan or WeChat OA publishing.
compatibility: Requires Node.js and npm; binary `wenyan` on PATH; outbound HTTPS. For WeChat draft publish, set WECHAT_APP_ID and WECHAT_APP_SECRET in the same environment as the CLI; public IP usually must be on the OA IP allowlist unless using Wenyan Server (--server, --api-key).
allowed-tools: Bash(npm:*) Bash(node:*) Bash(wenyan:*)
metadata:
  upstream-repo: "https://github.com/caol64/wenyan-cli"
  npm-package: "@wenyan-md/cli"
---

# 文颜 CLI（wenyan-cli）

[文颜（Wenyan）](https://github.com/caol64/wenyan-cli) 将 Markdown 排版并发布到**微信公众号草稿箱**等能力（其它平台以上游文档为准）。

本 Skill 面向 **AI Agent**：优先使用 **速查清单** 与 **黄金路径**；细则按需打开 `references/`（[渐进式 disclosure](https://agentskills.io/specification#progressive-disclosure)）。

## References

| 文档 | 用途 |
| ---- | ---- |
| [references/configuration.md](references/configuration.md) | 环境变量、frontmatter、IP 白名单、图片路径、Server 模式 |
| [references/troubleshooting.md](references/troubleshooting.md) | 按症状排查（凭证、白名单、图片、Server） |
| [references/openclaw.md](references/openclaw.md) | 旧版结构化 `metadata` 的 Openclaw 片段（可选） |

## Agent 速查（执行前读一遍）

1. **目标**：用户要「只预览 HTML」还是「发布草稿」？是否已声明使用 `--server`？
2. **凭证**：若发布，`WECHAT_APP_ID` 与 `WECHAT_APP_SECRET` 必须在**运行命令的环境**中可用；不要在聊天中索取或回显 Secret。
3. **网络/白名单**：本地直连时，运行环境公网 IP 通常需在公众号后台白名单；否则走 Server 模式（见 [configuration.md](references/configuration.md)）。
4. **文稿**：`article.md` 顶部必须有合法 YAML frontmatter，且 **`title` 必填且不超过 64 个字符**（微信公众号标题限制）。
5. **图片**：文内相对路径图片仅在「`-f` 指向本地文件」时最可靠；详见 [configuration.md](references/configuration.md)。
6. **失败后**：先读 CLI 报错，再查 [troubleshooting.md](references/troubleshooting.md)；需要上游参数时运行 `wenyan <command> --help`。

## 何时使用 / 不使用

| 使用本 Skill | 不使用（除非用户改口） |
| ------------ | ---------------------- |
| 微信公众号排版、发**草稿**、文颜 CLI | 与公众号/文颜无关的通用「转 HTML」 |
| 安装/验证 `wenyan`、主题、`publish`/`render` | 用户未授权操作其微信账号/未配置环境却要求直接发布 |
| 排查发布失败（凭证、白名单、Server） | 要求破解、绕过平台规则或伪造请求 |

## Prerequisites

- **Node.js** + npm：`npm install -g @wenyan-md/cli`
- 验证：`wenyan --help`
- 发布前完整前置条件见 [configuration.md](references/configuration.md)

## 黄金路径（默认工作流）

按顺序执行；任一步失败则停止并说明原因。

1. **确认意图**：渲染预览 → 第 4 步用 `render`；发布草稿 → `publish`。
2. **读文件**：打开用户给出的 Markdown，检查 frontmatter 是否存在且含 `title`（并确认标题长度 <= 64）。
3. **必要时补全 frontmatter**：仅当用户明确要求且字段缺失时，与用户确认 `author`、`source_url`、封面等；若 `title` 超过 64 字符先提示并建议缩短；不要编造 AppID/Secret。
4. **选择命令**（本地文件优先）：

   ```bash
   wenyan publish -f /absolute/or/relative/path/to/article.md
   ```

   若仅预览：

   ```bash
   wenyan render -f /absolute/or/relative/path/to/article.md
   ```

5. **Server 模式**（用户已提供 server URL 与 api-key 时）：

   ```bash
   wenyan publish -f article.md --server "https://api.example.com" --api-key "<user-supplied-key>"
   ```

6. **汇报**：按下方 **Agent 输出规范** 向用户说明结果；勿粘贴 Secret。

## 命令与输入方式（简表）

| 目的 | 命令骨架 |
| ---- | -------- |
| 发布草稿 | `wenyan publish -f <path-or-url-or-inline>` |
| 仅渲染 | `wenyan render -f <…>` |
| 主题 | `wenyan theme`（子命令以 `--help` 为准） |
| 本地 Server | `wenyan serve`（用于自托管/联调，见上游 `docs/`） |

| 输入方式 | 示例 | Agent 注意 |
| -------- | ---- | ---------- |
| 本地路径 | `wenyan publish -f ./posts/a.md` | 相对路径图片以此方式最稳 |
| URL | `wenyan publish -f https://…/a.md` | 确认可访问 |
| 管道 | `cat a.md \| wenyan publish` | 适合 CI；相对图片需能解析 |
| 内联 | `wenyan publish "# t\n…"` | 仅短篇快发 |

## 文章格式（Frontmatter）

发布前 Markdown **须** 以 YAML frontmatter 开头（`title` 必填，且不超过 64 个字符）；字段表与封面规则见 [configuration.md](references/configuration.md)。

```yaml
---
title: 文章标题
cover: /path/to/cover.jpg
author: 作者
source_url: https://example.com/original
---
```

## 示例（便于对齐期望）

### 输入（节选）

用户提供的 `post.md`：

```markdown
---
title: 示例标题
author: demo
---
## 小节
正文与 ![](https://example.com/x.png) 图片。
```

### 输出（Agent 行为）

- 若用户要预览：运行 `wenyan render -f post.md`，向用户说明 HTML 产出位置或控制台/文件行为（以 CLI 实际输出为准）。
- 若用户要发草稿：在环境变量与白名单就绪后运行 `wenyan publish -f post.md`，并提示用户在 **微信公众平台 → 草稿箱** 查看。

## Agent 输出规范（完成后必读）

向用户汇报时尽量包含：

- **做了什么**：例如「已执行 `wenyan publish -f …`」或「已 render」。
- **结果**：成功 / 失败；若成功，说明草稿应在**微信公众平台草稿箱**中查看（或团队约定位置）。
- **失败时**：一句概括错误；指向可能原因（环境变量、白名单、图片路径、Server URL/key）；建议下一步（见 [troubleshooting.md](references/troubleshooting.md)）。
- **不要输出**：`WECHAT_APP_SECRET`、原始 API 密钥、用户 `--api-key` 的完整值。

## 校验与规范

- Skill 格式：<https://agentskills.io/specification>
- 本地校验（需 Node）：`npx skills-ref validate ./dreamai-wenyan-cli`
- 完整文档索引：<https://agentskills.io/llms.txt>

## 维护记录

- 2026-03-30：初始化 skill。
- 2026-03-30：增强 Agent 导向结构（速查、黄金路径、输出规范、`troubleshooting` 参考）。
- 2026-03-30：按 Agent Skills 规范收紧 frontmatter（`compatibility`、`allowed-tools`、字符串 `metadata`）；移除非规范 `homepage`；`references` 改为规范链接；Openclaw 迁入 `references/openclaw.md`。
