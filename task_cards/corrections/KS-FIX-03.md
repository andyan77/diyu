---
task_id: KS-FIX-03
corrects: KS-DIFY-ECS-001
severity: FAIL
phase: Dify-ECS
wave: W1
depends_on: [KS-FIX-02]
files_touched:
  - scripts/verify_ecs_mirror.py
  - knowledge_serving/audit/ecs_mirror_verify_KS-FIX-03.json
artifacts:
  - knowledge_serving/audit/ecs_mirror_verify_KS-FIX-03.json
status: not_started
---

# KS-FIX-03 · 消除 ECS 镜像 drift

## 1. 任务目标
- **business**：原卡 staging mirror verify exit 1，drift 未消；本卡要求 ECS `/data/clean_output/` 与本地 byte-identical。
- **engineering**：定位每条 drift 来源 → 修复（local 推还是 ECS 清）→ 复跑 verify 直至 exit 0。
- **S-gate**：S0 真源闭环延续。
- **non-goal**：不动 serving views（属 FIX-08）。

## 2. 前置依赖
- KS-FIX-02（dry-run 通道已通）。

## 3. 输入契约
- 真源仍是 local `clean_output/`；任何 drift 默认拉 ECS 向 local 对齐（E8 修数据匹配 spec）。

## 4. 执行步骤
1. 跑 verify → 输出 drift 清单。
2. 对每条 drift 溯源（git log + ECS 远程时间戳）。
3. 默认推 local → ECS；若发现 local 缺文件而 ECS 是历史正确数据，**停下用户裁决**，不许默认拉 ECS 进 local。
4. 复跑 verify exit 0。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/ecs_mirror_verify_KS-FIX-03.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| ECS 多文件 | 必须人工裁决而不是自动同步 |
| Local 多文件 | apply 后 ECS 补齐 |
| sha256 mismatch 单文件 | 必须 stop + 列出，不掩盖 |
| `--fail-on-drift` 缺失就跑 verify | **fail-closed**：脚本默认 drift>0 时 exit 0 是反模式，本卡命令强制带 flag |
| SSH 不通或 tunnel 未起 | **fail-closed**：拒绝写 pass artifact，exit 非 0 |

## 7. 治理语义一致性
- E8 默认修数据匹配 spec；不允许"为了对齐 ECS 改 local"。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 scripts/verify_ecs_mirror.py --env staging --dry-run --fail-on-drift --out knowledge_serving/audit/ecs_mirror_verify_KS-FIX-03.json
pass:    drift_total == 0
fail-closed:
  - drift_total > 0 → exit 1
  - SSH/tunnel 不通 / 缺 env → exit 2
  - --env prod → exit 2
```

> **接口契约 / interface contract**：本卡直接复用已存在的 `scripts/verify_ecs_mirror.py`，
> 不再创建薄 wrapper（早期草稿写 `knowledge_serving/scripts/ecs_mirror_verify.py` 是悬空 wrapper，
> 外审第 3 轮指出"creates 文件不存在 → 卡片不可复跑"，本轮直接消除该悬空声明）。
> 现存脚本的可用 flag：
> - `--env {staging,prod}`：环境（prod 拒绝）
> - `--dry-run`：不触发任何修复，仅生成 drift 报告（FIX-03 是 verify-only 卡）
> - `--fail-on-drift`：drift_total != 0 时 exit 1（默认即此，flag 仅为可读性）
> - `--out PATH`：把 canonical drift 报告复制到指定 audit 路径（KS-FIX-02 本轮新增，硬限定写入路径白名单）

## 9. CD / 环境验证
- staging：ECS。
- 监控：每日 cron 跑一次 verify（FIX-25 CI 总闸纳入）。

## 10. 独立审查员 Prompt
> 验：1) ECS 与 local sha256 全等；2) drift 修复方向必须 local→ECS；3) 任一反向迁移须有 user signoff。

## 11. DoD
- [ ] drift_count=0
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-DIFY-ECS-001 回写
