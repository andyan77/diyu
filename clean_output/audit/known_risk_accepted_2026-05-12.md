# 已知风险接受 / Known Risk Accepted · 2026-05-12

## 风险事件 / Risk Event

**事件**：2 个 LLM（大语言模型）API key 通过 2026-05-12 与 Claude Code 的对话历史传输：
- DASHSCOPE_API_KEY（QWEN / 通义千问，阿里云百炼）
- DEEPSEEK_API_KEY（DEEPSEEK / 深度求索）

**暴露面 / exposure surface**：
- Anthropic API 日志可能保留对话副本
- 本机 Claude Code 缓存包含对话历史
- 任何后续截图 / 导出 / 二次分享均可造成二次泄露

## 用户决策 / User Decision

- **轮换 / rotate**：❌ 不轮换 / declined
- **决策时间 / time**：2026-05-12
- **决策人 / decided by**：项目所有者 / project owner（diyufaye@gmail.com）
- **签字理由 / rationale**：当前 key 仅用于本项目内部开发，接受暴露面风险

## 风险缓解措施 / Mitigation in Place

| 措施 / measure | 状态 |
|---|---|
| `.env` 入 `.gitignore` | ✅ 已配置 |
| `.env` 不入 git 历史 | ✅ 首次提交前已配置 |
| `scripts/load_env.sh` 含 git 跟踪自检 | ✅ 已实现 |
| `.env.example` 仅模板，无明文 | ✅ 已配置 |
| 后续不允许任何 key 贴入对话 | 约定 / convention |

## 未来触发轮换的条件 / Future Rotation Triggers

下列任一发生，必须立即轮换 / immediately rotate：

1. 仓库历史中检测到 `sk-` 明文（pre-commit hook 应阻断 / should block）
2. `.env` 出现在任何 git 提交
3. 设备更换 / 团队人员变动
4. 任一 key 在 LLM 提供方控制台显示异常调用 / abnormal usage detected
5. 项目转交他人 / project handover

## 责任链 / Accountability

本风险接受**不豁免**后续治理责任。一旦发生实际滥用 / actual misuse，处置按 §A3 高风险清单（high-risk register）流程。
