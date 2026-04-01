# 文颜 CLI：按症状排查（Agent）

处理顺序建议：**读 CLI 标准错误/日志 → 对照本章 → 查 `wenyan <cmd> --help` → 查上游 [docs](https://github.com/caol64/wenyan-cli/tree/main/docs)**。

## 发布 / 上传相关

| 症状（用户描述或日志关键词） | 可能原因 | Agent 建议动作 |
| ---------------------------- | -------- | -------------- |
| 提示未配置或鉴权失败、invalid credential、access_token | `WECHAT_APP_ID` / `WECHAT_APP_SECRET` 未设置、错误或过期 | 确认在**运行 `wenyan` 的同一 shell/CI job** 中已 export；不要让用户把 Secret 发到聊天 |
| 接口失败、IP 不在白名单、request from illegal IP | 本地直连时出口 IP 未加入公众号白名单 | 让用户在公众平台加白名单，或改用 `--server` + Wenyan Server（固定出口） |
| 仅本地相对路径图片丢失；URL 模式下图裂 | `-f` 非本地文件，相对路径无法解析 | 改为本地路径发布，或把图片改为绝对路径/HTTPS |
| Server 模式 401/403 | `--api-key` 错误或 Server 配置不匹配 | 核对用户提供的 key；不要猜测 key |
| 超时、连接失败 | 网络、代理、Server 宕机 | 检查 `ping`/浏览器能否访问 Server；本地直连时检查出网 |

## 文稿与 frontmatter

| 症状 | 可能原因 | Agent 建议动作 |
| ---- | -------- | -------------- |
| 提示缺少标题或解析失败 | 无 frontmatter 或缺 `title` | 在文首补充合法 YAML，`title` 必填 |
| 标题相关校验失败、发布被拒或标题被截断 | `title` 超过微信 **[新增草稿](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html)** 限制（**不超过 32 个字**） | 将 `title` 缩短到 32 字以内；勿用 `\uXXXX` 形式拼标题 |
| 作者或摘要报错 | `author` 超过 **16 个字**，或 `digest` 超过 **128 个字**（单图文） | 按官方字段说明缩短 |
| 正文图片在公众号里不显示 | 接口要求正文内图片 URL 须来自微信素材上传接口；**外部 URL 会被过滤** | 依赖文颜将图片上传为素材；避免指望未走微信上传的外部图 URL 原样生效 |
| `content_source_url` 相关错误 | 原文链接超过 **1 KB** | 缩短 `source_url` 或使用短链（注意合规） |
| 封面不符合预期 | `cover` 缺省、路径错误或微信拒收 | 对照 `configuration.md` 检查路径与格式 |

## 安装与环境

| 症状 | 可能原因 | Agent 建议动作 |
| ---- | -------- | -------------- |
| `wenyan: command not found` | 未安装或未在 PATH | `npm install -g @wenyan-md/cli`；新开终端后再试 |
| Node 版本过旧 | 上游要求未满足 | 查看上游 `package.json` engines 或 README；建议当前 LTS |

## 何时转交人工 / 上游

- 微信侧**账号类型**、权限（例如某些接口需认证号）导致的能力差异：需用户在微信公众平台核实。
- 文颜 **Server** 自建部署、反向代理、Docker：查阅上游 `README.docker.md`、`docs/server.md` 等。

更多配置项与字段说明：**`configuration.md`**。
