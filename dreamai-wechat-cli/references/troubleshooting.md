# dreamai-wechat-cli：按症状排查（Agent）

处理顺序建议：**读 stderr → 对照本章 → `dreamai-wechat-cli <cmd> --help` → 仓库 [docs](https://github.com/iamtornado/dreamai-wechat-cli/tree/main/docs)**。

## 发布 / 上传相关

| 症状（用户描述或日志关键词） | 可能原因 | Agent 建议动作 |
| ---------------------------- | -------- | -------------- |
| 鉴权失败、invalid credential、access_token | `WECHAT_APP_ID` / `WECHAT_APP_SECRET` 未设置、错误或过期 | 确认在**运行 CLI 的同一 shell/CI job** 中已 export；不要让用户把 Secret 发到聊天 |
| IP 不在白名单、illegal IP | 本地直连时出口 IP 未加白 | 在公众平台加白名单，或改用 `--server` + 固定出口服务 |
| 相对路径图片丢失 | `-f` 非本地文件 | 改为本地路径发布，或改为绝对路径/HTTPS |
| Server 模式 401/403 | `--api-key` 错误或 Server 配置不匹配 | 核对用户提供的 key；不要猜测 |
| 超时、连接失败 | 网络、代理、Server 不可用 | 检查 Server URL；本地直连时检查出网 |

## 文稿与 frontmatter

| 症状 | 可能原因 | Agent 建议动作 |
| ---- | -------- | -------------- |
| 缺少标题或解析失败 | 无 frontmatter 或缺 `title` | 文首补充合法 YAML，`title` 必填 |
| 标题校验失败 | `title` 超过微信 **[新增草稿](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html)** **32 个字** | 缩短标题 |
| 作者相关错误 | `author` 超过 **16 个字** | 缩短 |
| 正文图不显示 | 正文图须走微信素材 URL | 依赖 CLI 上传；勿指望未上传的外部图 URL 原样生效 |
| `source_url` 错误 | 超过 **约 1 KB** | 缩短或使用短链（注意合规） |
| 封面问题 | `cover` 缺失、路径错误或拒收 | 对照 `configuration.md` |

## `draft` / `serve`

| 症状 | 可能原因 | Agent 建议动作 |
| ---- | -------- | -------------- |
| 子命令不存在或参数错误 | 版本过旧或记错参数 | `dreamai-wechat-cli draft --help`；必要时让用户升级包 |
| HTTP 404/路由错误 | `serve` 路径或反代配置 | 读仓库 `docs/server.md` |
| 与 `publish` 行为不一致 | 直连 vs 经 Server | 确认是否同一组 `--server`/`--api-key` 与环境变量 |
| `draft merge-add` 报图文条数或字段错误 | 合并后超过微信限制，或源草稿缺必要字段 | 缩减待合并 `media_id` 数量并先逐篇 `draft get` 检查字段，再重试 |

## `mass` 群发

| 症状 | 可能原因 | Agent 建议动作 |
| ---- | -------- | -------------- |
| `mass sendall` 权限/认证相关错误 | 公众号不满足群发接口条件 | 让用户在微信官方文档与公众号后台核实接口权限 |
| 群发返回成功但用户没收到 | 群发是异步任务 | 说明返回仅代表任务提交成功，需等待微信任务回执/事件 |
| `media_id` 无效或已失效 | 来源草稿被删除/失效，或 ID 不匹配 | 重新通过 `publish` 或 `draft add/merge-add` 获取新 `media_id` |
| 指定标签群发失败 | `--tag-id` 无效或不在账号可用范围 | 核对标签 ID 与账号配置，必要时先全员路径验证 |

## 安装与环境

| 症状 | 可能原因 | Agent 建议动作 |
| ---- | -------- | -------------- |
| `dreamai-wechat-cli: command not found` | 未安装或未在 PATH | `npm install -g @tornadoami/dreamai-wechat-cli`；新开终端 |
| 与用户文档中的 `wenyan` 不一致 | 混用上游与 fork | 本仓库命令为 **`dreamai-wechat-cli`**；上游为 `wenyan` |
| Node 版本过旧 | 仓库要求 Node 18+ | 升级 Node；见 fork `package.json` engines（如有） |
| 升级失败（权限/交互） | npm 全局权限不足，或在 CI 中等待确认 | 使用可写 Node 环境（如 nvm）并改用 `dreamai-wechat-cli update --yes` |

## 诊断日志

若用户怀疑重复草稿或需追踪请求：

```bash
dreamai-wechat-cli publish -f article.md --debug
# 或
DREAMAI_WECHAT_DEBUG=1 dreamai-wechat-cli publish -f article.md
```

`draft` 子命令同样可尝试 `--debug`（以 `--help` 为准）。**勿**在汇报中粘贴完整 token 或 Secret。

## 何时转交人工 / 仓库维护者

- 微信账号类型、接口权限（认证号等）导致的能力差异：需用户在公众平台核实。
- 自建 Server、Docker、反向代理：见仓库 `README.docker.md`、`docs/server.md`。

更多字段说明：**`configuration.md`**。
