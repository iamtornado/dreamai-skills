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

| 字段 | 必填 | 说明 |
| ---- | ---- | ---- |
| `title` | 是 | 文章标题（微信公众号平台强制要求：不超过 64 个字符） |
| `cover` | 视情况 | 封面：本地绝对路径或网络 URL；若正文已有合适图片可按产品行为省略 |
| `author` | 否 | 作者展示名 |
| `source_url` | 否 | 原文地址 |

## 正文与图片路径

- **本地绝对路径**与 **HTTPS 图片 URL** 一般均可由文颜按微信要求处理并上传素材。
- **仅当内容输入为本地文件路径时**，文中的 **相对路径** 图片（如 `./assets/x.png`）才能可靠解析。

## Server 模式要点

- CLI → 自建 Wenyan Server → 微信公众号 API。
- 典型调用：`wenyan publish -f article.md --server <server-url> --api-key <key>`。
- 适用于：无固定出口 IP、团队共享发布出口、CI/CD、与 AI Agent 集成等场景。

详细部署与参数请优先查阅上游仓库 `docs/`：<https://github.com/caol64/wenyan-cli>
