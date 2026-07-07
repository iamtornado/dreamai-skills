# dreamai-wechat-cli：配置与发布前置条件

本文档补充环境、微信侧限制、Server 模式，以及本 fork 特有的 **`draft` / `mass` / `update` / `serve`** 提示。

**相关**：按报错排查见 [`troubleshooting.md`](troubleshooting.md)。

## 环境变量（微信公众号）

发布或调用草稿相关接口前，运行环境通常需设置：

| 变量 | 说明 |
| ---- | ---- |
| `WECHAT_APP_ID` | 公众号 AppID |
| `WECHAT_APP_SECRET` | 公众号 AppSecret |

**安全建议**：仅通过环境变量或受控密钥注入；不要在仓库、Skill 示例或聊天中硬编码真实值。

可选调试：`DREAMAI_WECHAT_DEBUG=1` 或与 CLI `--debug` 组合使用（以 `--help` 为准）。

## 微信公众平台 IP 白名单

在 **本地直连** 公众号 API 时，调用方公网 IP 通常需加入公众号后台 IP 白名单。

- 上游相关说明：<https://yuzhi.tech/docs/wenyan/upload>

若无法固定本机出口 IP，使用 **Server 模式**：在固定 IP 的服务器上部署兼容的 Wenyan / 本 CLI `serve` 端点，由 CLI 带 `--server` 与 `--api-key` 访问。详见仓库 [docs/server.md](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/server.md)。

## Frontmatter 字段

最终以 **本 CLI 实际映射** 为准；草稿接口受微信 **[新增草稿 draft_add](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html)** 等约束。

| 字段 | 必填 | 说明 |
| ---- | ---- | ---- |
| `title` | 是 | **不超过 32 个字**；勿用 `\uXXXX` 形式拼标题。 |
| `cover` | 视情况 | 本地路径或 HTTPS URL。若未指定，部分流程可用正文首张图推导封面（以 CLI 行为为准）；仍可能因缺素材失败。 |
| `author` | 否 | **不超过 16 个字**。 |
| `source_url` | 否 | 阅读原文；**不超过约 1 KB**。 |

### 接口侧其它常见限制（图文草稿）

| 接口字段 | 官方限制（摘要） |
| -------- | ---------------- |
| `digest` | 摘要不超过 **128 个字**（单图文有意义）。 |
| `content` | HTML；**少于 2 万字符**、小于 **1M**；正文图片 URL 须来自微信素材上传结果，**外部 URL 常被过滤**。 |

若本地 `render` 正常但 `publish` 失败，应对照微信返回错误与官方文档。

## `newspic` 子命令（贴图草稿）

**v2.1.0+** 提供 **`dreamai-wechat-cli newspic publish`**：按官方 **[draft/add](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html)** 创建 **`article_type=newspic`** 草稿（图片/文字贴图），并经由 **[material/add_material](https://developers.weixin.qq.com/doc/subscription/api/material/permanent/api_addmaterial.html)** 上传永久图片素材。

| 要点 | 说明 |
| ---- | ---- |
| 与 `publish` 区别 | `publish` → 图文 `news`（Markdown→HTML）；`newspic publish` → 多图贴图，**不用 Markdown** |
| 仅进草稿箱 | 本命令**不群发**；后台「草稿箱」查看 |
| 标题 | 官方 draft 字段上限 32 字；**贴图 UI 建议 ≤20 字**（默认 `--max-title-chars 20`） |
| 描述 | 对应 JSON 字段 `content`（纯文本，非 HTML） |
| 图片 | `image_info.image_list[].image_media_id`，须为**永久素材** ID；最多 **20** 张 |
| 目录模式 | `--from-dir <dir>`：读 `wechat_post.json`（`title`、`description`）+ 有序 `panel_*.png`（或其它约定文件名） |
| 手动模式 | `--title`、`--content`、`--image`（可重复）或 `--images-dir` |
| 凭证 | `--app-id` / `--app-secret` 或 `WECHAT_APP_ID` / `WECHAT_APP_SECRET` |

示例：

```bash
dreamai-wechat-cli newspic publish --from-dir /path/to/post_bundle
dreamai-wechat-cli newspic publish --title "标题" --content "描述" --image a.png --image b.png
```

详情见仓库 [docs/newspic.md](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/newspic.md)。

**下游集成**：调用方应执行 **npm 全局安装的** `dreamai-wechat-cli`，勿 `node …/dist/cli.js` 指向源码；升级：`dreamai-wechat-cli update --yes`。

## 正文与图片路径

- **本地绝对路径**与 **HTTPS 图片 URL** 一般由 CLI 按微信要求上传素材。
- **仅当 `-f` 为本地文件路径时**，文中 **相对路径** 图片（如 `./assets/x.png`）解析最可靠。

## `draft` 子命令

本 fork 提供与草稿箱字段对齐的 **`dreamai-wechat-cli draft`** 子命令（如 count、list、get、update、delete、add、merge-add 等，以 `dreamai-wechat-cli draft --help` 为准）。Agent 在不确定参数名时**必须先 `--help`**，避免臆造 media_id 或 JSON 字段。

`merge-add` 用于把多篇草稿按顺序拼成一篇新的多图文草稿；可选 `--sendall`（合并后立即群发）和 `--delete-sources`（成功后删除源草稿）。详情见仓库 [docs/draft-merge.md](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/draft-merge.md)。

## `mass` 子命令（高级群发）

`dreamai-wechat-cli mass sendall --media-id <id>` 封装微信 `message/mass/sendall` 的 `mpnews` 场景，支持全员或 `--tag-id` 按标签群发。

常见前提：

- 公众号具备官方文档要求的群发接口权限（通常需认证号，依微信后台为准）。
- 调用机器出口 IP 在公众号白名单内（本地直连时）。
- 群发为异步任务，成功返回仅代表任务已提交；最终结果需看微信回执机制。

详情见仓库 [docs/mass.md](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/mass.md)。

## `update` 子命令（CLI 自更新）

`update` 用于升级全局安装的 CLI：

```bash
dreamai-wechat-cli update --check
dreamai-wechat-cli update
dreamai-wechat-cli update --yes
dreamai-wechat-cli update --to <version-or-dist-tag>
```

说明：

- 内部会执行 `npm install -g @tornadoami/dreamai-wechat-cli@<target>`。
- 在 CI/非交互环境建议用 `--yes`。
- 升级后建议新开终端并验证 `dreamai-wechat-cli --version`。

## `serve` 模式

`dreamai-wechat-cli serve` 暴露 HTTP 接口（含草稿与发布相关路由，见仓库文档）。部署、鉴权与路径以 [docs/server.md](https://github.com/iamtornado/dreamai-wechat-cli/blob/main/docs/server.md) 为准。

## Server 模式（CLI 作为客户端）

典型调用：

```bash
dreamai-wechat-cli publish -f article.md --server <server-url> --api-key <key>
```

适用于无固定出口 IP、团队共享发布出口、CI/CD、与 Agent 集成等场景。
