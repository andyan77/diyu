---
task_id: KS-GEN-002
phase: Production-Readiness
wave: W15
depends_on: [KS-GEN-001]
files_touched:
  - knowledge_serving/golden_briefs/
  - knowledge_serving/audit/golden_briefs_KS-GEN-002.json
artifacts:
  - knowledge_serving/audit/golden_briefs_KS-GEN-002.json
s_gates: [S7]
plan_sections:
  - "§A4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/validate_golden_briefs.py --strict --min-count 10 --out knowledge_serving/audit/golden_briefs_KS-GEN-002.json
status: not_started
---

# KS-GEN-002 · golden_brief 集（30 条真实业务 brief 入库）

## 1. 任务目标
- **业务**：MVP 评测要用真业务 brief，不能用 AI 编的假场景。本卡：从笛语真实运营场景里抽 ≥ 30 条 brief（每种 MVP 矩阵组合至少 10 条），覆盖正常路径 + 边界 + 故意残缺（验 fallback）。
- **工程**：每条 brief 是结构化 YAML，含 tenant_id / brand_layer / content_type / channel / business_brief 字段 + expected_fallback_status；落 audit JSON 锁定集合 sha256。
- **S-gate**：S7（fallback 集应覆盖本卡 expected_fallback_status 取值集）。
- **非目标**：不写生成结果（那是 KS-GEN-003 干的）；不评价（KS-GEN-004 干）。

## 2. 前置依赖
- KS-GEN-001（MVP 范围已锁）。

## 3. 输入契约
- 读：`knowledge_serving/audit/mvp_scope_KS-GEN-001.json`（取 content_types + channels）
- 不读：`clean_output/` 业务知识（brief 是输入侧的"任务订单"，与领域知识库正交）

## 4. 执行步骤
**分两阶段执行（避免一上来被人工评分工作量拖住）**：

**Stage-1（≥ 10 条 / 链路 PoC）**：
1. 与用户对话，按 MVP 矩阵每组合先收集 ≥ 10 条真实业务 brief（用户给原始素材，AI 结构化）。
2. 至少含 normal / fallback / blocked 三类 expected_fallback_status，每类 ≥ 1 条。
3. 写 YAML 到 `knowledge_serving/golden_briefs/<content_type>__<channel>/brief_<NNN>.yaml`。
4. 跑 validate_golden_briefs.py（--min-count 10），同步走完 KS-GEN-003/004 一遍，确认 e2e + 评分模板可用。

**Stage-2（扩到 ≥ 30 条 / full eval）**：
5. Stage-1 通过 + 用户认可后，扩展到每组合 ≥ 10 条 → 全集 ≥ 30 条。
6. 重跑 validate_golden_briefs.py（--min-count 30），覆盖 fallback ≥ 3 类。
7. 最终 audit 字段含 `stage_1_passed_at` + `stage_2_passed_at` 双时间戳。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `golden_briefs/**/*.yaml` × ≥ 30 | yaml | 是（真业务素材） | 是 | static_verified |
| `audit/golden_briefs_KS-GEN-002.json` | json | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| Stage-1: count < 10 | **fail-closed** |
| Stage-2: count < 30 | **fail-closed**（最终态） |
| Stage-2 任一组合 < 10 条 | fail-closed |
| expected_fallback_status 仅 normal（没残缺样本） | fail-closed（防"只测顺路"假绿） |
| brief 含 AI 生成填充词（"举例来说" / "通常情况下"等） | 人工 review 标识 + 拒绝 |

## 7. 治理语义一致性
- 不写 `clean_output/`（golden_briefs 是 Phase 2 输入资产，不是 Phase 1 真源）。
- 不调 LLM 编造 brief（R2 + 反幻觉）。
- brand_layer 字段严格按 `domain_general` / `brand_faye` 多租户纪律标注。

## 8. CI 门禁
```
command (Stage-1): python3 knowledge_serving/scripts/validate_golden_briefs.py --strict --min-count 10 --out knowledge_serving/audit/golden_briefs_KS-GEN-002.json
command (Stage-2): python3 knowledge_serving/scripts/validate_golden_briefs.py --strict --min-count 30 --out knowledge_serving/audit/golden_briefs_KS-GEN-002.json
pass (Stage-1):    count ≥ 10 + fallback ≥ 3 类 + stage_1_passed_at 时间戳
pass (Stage-2):    count ≥ 30 + 每组合 ≥ 10 + stage_2_passed_at 时间戳
卡 done 必须两 stage 都通过
```

## 9. CD / 环境验证
- staging / prod：本卡仅入 git，不涉及环境部署。

## 10. 独立审查员 Prompt
> 验：1) 抽 3 条 brief 看是否真业务（不是 AI 编的）；2) audit count ≥ 30；3) fallback 覆盖矩阵齐。

## 11. DoD
- [ ] Stage-1: 10+ brief 入 git + audit `stage_1_passed_at`
- [ ] Stage-1 链路 PoC 走通（KS-GEN-003/004 跑过一遍）
- [ ] Stage-2: 30+ brief 入 git + audit `stage_2_passed_at`
- [ ] fallback 覆盖矩阵齐
- [ ] 用户确认 brief 真实性（每组合抽样签字）
