# 文颜 CLI：配置与发布前置条件

本文档补充 `SKILL.md` 中与环境、微信侧限制和 Server 模式相关的细节，便于 Agent 排查问题。

**相关**：按报错排查见同目录下的 [`troubleshooting.md`](troubleshooting.md)。

## 环境变量（微信公众号）

发布到微信公众号接口前，运行环境需设置（缺一通常会导致上传失败）：

| 变量 | 说明 |
| ---- | ---- |
| `WECHAT_APP_ID` | 公众号 AppID |
| `WECHAT_APP_SECRET` | 公众号 AppSecret |

**安全建议**：仅通过环境变量或受控密钥注入；不要在仓库、Skill 示例或聊天中硬编码真实值。

## 微信公众平台 IP 白名单

在 **本地直连** 公众号 API 的模式下，调用上传接口的机器公网 IP 通常需加入公众号后台的 IP 白名单；未配置会表现为接口调用失败。

- 配置说明（上游文档引用）：<https://yuzhi.tech/docs/wenyan/upload>

若无法固定本机 IP，可考虑 **Server 模式**：在固定 IP 的服务器上部署 Wenyan Server，CLI 仅作为客户端发请求。

## Frontmatter 字段

与微信公众平台服务端接口的对应关系以 **文颜实际映射** 为准；发布到草稿箱时最终会受 **[新增草稿 draft_add](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html)** 等接口约束。

| 字段 | 必填 | 说明 |
| ---- | ---- | ---- |
| `title` | 是 | 文章标题。官方接口 `articles[].title`：**总长度不超过 32 个字**（不要用 `\uXXXX` 形式转义，直接写正常字符串）。 |
| `cover` | 视情况 | 封面：本地绝对路径或网络 URL。图文 `news` 类型下接口要求 `thumb_media_id`（永久素材）；通常由文颜上传封面后填入，若缺封面可能导致接口失败。 |
| `author` | 否 | 对应接口 `author`：**总长度不超过 16 个字**；勿使用 Unicode 转义写法。 |
| `source_url` | 否 | 对应接口 `content_source_url`（阅读原文）；**大小不超过 1 KB**。 |

### 接口侧其它常见限制（draft_add / 图文）

以下字段若由文颜从正文/HTML 生成，Agent 仍应知晓上限，便于排错：

| 接口字段 | 官方限制（摘要） |
| -------- | ---------------- |
| `digest` | 摘要不超过 **128 个字**；仅**单图文**有意义，多图文可为空（不填则默认抓正文前约 54 字）。 |
| `content` | 支持 HTML；须 **少于 2 万字符**、小于 **1M**；正文中图片 URL 须来自微信「上传图文消息内的图片」等接口返回的地址，**外部图片 URL 会被过滤**。 |
| `article_type` | 不填默认为图文 `news`；另有图片消息 `newspic` 等结构，与纯 Markdown 图文流程不同。 |

若本地预览正常但 `publish` 失败，应对照官方文档与返回错误码，而非仅看 Markdown 是否渲染成功。

## 正文与图片路径

- **本地绝对路径**与 **HTTPS 图片 URL** 一般均可由文颜按微信要求处理并上传素材。
- **仅当内容输入为本地文件路径时**，文中的 **相对路径** 图片（如 `./assets/x.png`）才能可靠解析。

## Server 模式要点

- CLI → 自建 Wenyan Server → 微信公众号 API。
- 典型调用：`wenyan publish -f article.md --server <server-url> --api-key <key>`。
- 适用于：无固定出口 IP、团队共享发布出口、CI/CD、与 AI Agent 集成等场景。

详细部署与参数请优先查阅上游仓库 `docs/`：<https://github.com/caol64/wenyan-cli>
