# Openclaw / 扩展元数据（非 Agent Skills 核心字段）

[Agent Skills 规范](https://agentskills.io/specification) 中 `metadata` 推荐为「字符串键 → 字符串值」。若客户端仍需要结构化 **Openclaw** 安装提示，可使用下方 JSON。

```json
{
  "openclaw": {
    "emoji": "📮",
    "requires": { "bins": ["dreamai-wechat-cli"] },
    "install": [
      {
        "id": "npm",
        "kind": "npm",
        "package": "@tornadoami/dreamai-wechat-cli",
        "bins": ["dreamai-wechat-cli"],
        "label": "Install dreamai-wechat-cli (npm -g)"
      }
    ]
  }
}
```

合并到客户端配置时，包名与 bin 须与 npm 发布一致：<https://www.npmjs.com/package/@tornadoami/dreamai-wechat-cli>（若与本地不符以用户环境为准）。
