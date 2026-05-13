---
task_id: KS-RETRIEVAL-006
phase: Retrieval
wave: W7
depends_on: [KS-VECTOR-001, KS-POLICY-005]
files_touched:
  - knowledge_serving/serving/vector_retrieval.py
  - knowledge_serving/tests/test_vector_filter.py
artifacts:
  - knowledge_serving/serving/vector_retrieval.py
s_gates: [S10]
plan_sections:
  - "§6.8"
  - "§8"
writes_clean_output: false
ci_commands:
  - python3 -m pytest knowledge_serving/tests/test_vector_filter.py -v
status: done
---

# KS-RETRIEVAL-006 · vector_retrieval + payload filter

## 1. 任务目标
- **业务**：从 Qdrant 做语义召回，必须带 payload hard filter。
- **工程**：基于 model_policy.yaml 的 embedding 生成 query embedding；filter 至少含 brand_layer ∈ allowed_layers、gate_status="active"、granularity_layer ∈ [L1,L2,L3]。
- **S gate**：S10。
- **非目标**：不灌库（属 KS-DIFY-ECS-004）。

## 2. 前置依赖
- KS-VECTOR-001、KS-POLICY-005

## 3. 输入契约
- 读：model_policy.yaml、qdrant_payload_schema.json
- 入参：query / allowed_layers / content_type
- env：QDRANT_URL_STAGING, QDRANT_API_KEY

## 4. 执行步骤
1. 用 policy.embedding.model 生成 query embedding
2. 构造 payload filter
3. Qdrant search → top_k 候选
4. rerank（按 KS-POLICY-005 设置）但**不**扩大召回范围
5. Qdrant 不可用 → 走 fallback（structured-only）

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `vector_retrieval.py` | py | 是 | 是 |
| `test_vector_filter.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| brand_a 召回到 brand_b chunk | 永不发生 |
| gate_status=deprecated chunk | 不命中 |
| Qdrant down | structured-only fallback |
| embedding 维度不匹配 | raise（KS-POLICY-005 联动） |
| rerank 引入新候选 | 拒绝（rerank 不得扩范围） |

## 7. 治理语义一致性
- S10 payload filter 全字段
- brand hard filter
- 不调 LLM 做最终判断
- 不写 clean_output

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_vector_filter.py -v
pass: 跨租户 0 串味 + Qdrant down fallback + 维度校验
artifact: pytest report
note: 用 `python3 -m pytest` 而非裸 `pytest`，避免环境 PATH 中无 `pytest` 入口时 127 假绿
```

## 9. CD / 环境验证
- staging：用 staging Qdrant + ks_chunks__<ver>
- prod：alias ks_chunks_current
- 健康检查：每分钟探活
- 监控：召回延迟 / fallback 率
- secrets：env 注入

## 10. 独立审查员 Prompt
> 请：1) 构造 brand_a 请求，对照 brand_b chunk 0 命中；2) 关掉 Qdrant，必须走 structured-only；3) rerank 不扩范围；4) 输出 pass / fail。
> 阻断项：跨租户串味；Qdrant down 时 5xx。

## 11. DoD
- [x] 模块入 git
- [x] pytest 全绿（19/19，本地实测 / runtime_verified 2026-05-13）
- [x] staging smoke pass（真 dashscope text-embedding-v3 + 真 Qdrant alias ks_chunks_current；30 候选 / 0 跨租户串味 / gate=active 全合规 / granularity=L1 全合规；audit: `knowledge_serving/audit/smoke_vector_retrieval_KS-RETRIEVAL-006.json`）
- [x] 审查员 pass（独立审查员 2026-05-13 FAIL → 修复 dag.csv/frontmatter 一致性 + CI 命令 `python3 -m pytest` + 本项闭环后采纳；阻断项已逐条落地）
