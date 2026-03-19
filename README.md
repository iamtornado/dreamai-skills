# dreamai-skills

这是一个用于集中管理各类 AI Agent Skills 的仓库，主要用于沉淀可复用的技能模板、实践经验和配套参考资料。

## 仓库目标

- 统一存放和维护不同场景的 Skills
- 让技能内容可复用、可演进、可协作
- 为后续扩展更多 Skills 提供清晰结构

## 当前结构

```text
dreamai-skills/
├─ dreamai-himalaya/
│  ├─ SKILL.md
│  └─ references/
└─ README.md
```

## Skill 组织建议

每个 Skill 建议使用独立目录，并遵循如下约定：

- `SKILL.md`：技能主文档（目标、触发条件、步骤、注意事项）
- `references/`：可选，存放补充说明、示例、外部资料等

推荐目录模板：

```text
<skill-name>/
├─ SKILL.md
└─ references/
   └─ *.md
```

## 如何新增一个 Skill

1. 在仓库根目录创建新的 skill 文件夹（例如：`dreamai-xxx/`）
2. 在该目录下创建并完善 `SKILL.md`
3. 如有需要，新增 `references/` 用于补充文档
4. 保持命名简洁、语义明确，便于检索

## 命名与维护建议

- 目录名建议使用 `dreamai-<topic>` 风格
- 文档尽量模块化，减少重复内容
- 变更时优先保持向后兼容和可读性

## Skills 官方网站

- **官方规范**
  - Agent Skills 开放标准官网：<https://agentskills.io/>
  - Agent Skills 规范（Specification）：<https://agentskills.io/specification>

- **平台文档**
  - Cursor 官方 Skills 文档：<https://cursor.com/docs/skills>

- **示例仓库**
  - Agent Skills GitHub 仓库：<https://github.com/agentskills/agentskills>
  - Anthropic Skills 示例仓库：<https://github.com/anthropics/skills>

## `SKILL.md` 标准模板

> 建议每个 Skill 都基于以下模板创建，保证可读性与一致性。

```md
---
name: dreamai-<skill-name>
description: 用一句话说明该 Skill 解决的问题与适用场景。
---

# dreamai-<skill-name>

## 目标

- 该 Skill 的核心目标
- 期望输出结果

## 适用场景

- 场景 A：...
- 场景 B：...

## 输入要求

- 必要输入：...
- 可选输入：...

## 执行步骤

1. 第一步：...
2. 第二步：...
3. 第三步：...

## 输出规范

- 输出格式：例如 Markdown / JSON / 代码片段
- 输出质量要求：完整、可执行、可验证

## 边界与限制

- 不处理：...
- 风险点：...
- 回退策略：...

## 示例

### 输入示例

```text
<在这里写输入示例>
```

### 输出示例

```text
<在这里写输出示例>
```

## 维护记录

- 2026-03-19：初始化模板
```

## 文档编写规范

- **清晰命名**：`name` 与目录名保持一致，使用小写短横线命名
- **描述准确**：`description` 必须明确“解决什么问题 + 在什么场景使用”
- **步骤可执行**：执行步骤要具体，避免“按需处理”这类模糊表达
- **输入输出成对**：输入要求和输出规范必须对应，避免信息断层
- **边界可落地**：明确不处理范围、潜在风险和回退方式
- **示例可复现**：至少提供一组可运行/可验证的输入输出示例
- **持续维护**：每次重要变更更新维护记录，便于追溯
