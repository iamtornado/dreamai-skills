# Openclaw / 扩展元数据（非 Agent Skills 核心字段）

[Agent Skills 规范](https://agentskills.io/specification) 中 `metadata` 推荐为「字符串键 → 字符串值」。若你的客户端仍需要结构化 **Openclaw** 安装提示，可使用下方 JSON（与旧版 `SKILL.md` frontmatter 中的块等价）。

```json
{
  "openclaw": {
    "emoji": "📰",
    "requires": { "bins": ["wenyan"] },
    "install": [
      {
        "id": "npm",
        "kind": "npm",
        "package": "@wenyan-md/cli",
        "bins": ["wenyan"],
        "label": "Install Wenyan CLI (npm -g)"
      }
    ]
  }
}
```

将以上内容合并到客户端配置时，请勿修改上游 npm 包名 unless 你知道自己在做什么。
