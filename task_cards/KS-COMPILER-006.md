---
task_id: KS-COMPILER-006
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-005]
files_touched:
  - knowledge_serving/scripts/compile_brand_overlay_view.py
  - knowledge_serving/views/brand_overlay_view.csv
artifacts:
  - knowledge_serving/views/brand_overlay_view.csv
s_gates: [S3]
plan_sections:
  - "§3.6"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_brand_overlay_view.py --check
status: not_started
---

# KS-COMPILER-006 · brand_overlay_view 编译

## 1. 任务目标
- **业务**：固化"这个品牌怎么变形"读模型，仅承载品牌调性 + 创始人画像两类（CLAUDE.md 多租户红线）。
- **工程**：覆盖 §3.6；brand_overlay_kind ∈ 4 枚举。
- **S gate**：S3 brand_layer_scope。
- **非目标**：不在 overlay 中放门店纪律 / 商品事实（CLAUDE.md 红线）。

## 2. 前置依赖
- KS-SCHEMA-005

## 3. 输入契约
- 读：`clean_output/candidates/brand_*/`、9 表
- 不读：domain_general candidates

- **W3+ 输入白名单硬约束（见 README §7.1）**：本卡禁止读取 ECS PG `knowledge.*`、ECS 备份目录 `/data/clean_output.bak_*`、历史临时目录 `/tmp/itr*`、Qdrant 中缺 `compile_run_id` + `source_manifest_hash` 的旧 collection；只能从 README §7.1 白名单输入派生（含本卡 §3 上方列出的具体路径，例如 `clean_output/candidates/`、`clean_output/nine_tables/`、`clean_output/audit/`、`knowledge_serving/schema/`、`knowledge_serving/control/content_type_canonical.csv` 等）。

## 4. 执行步骤
1. 加载 brand_<name> candidates
2. overlay_kind 分类：brand_voice / founder_persona / team_persona_overlay / content_type_overlay
3. 校验 precedence、fallback_behavior 字段
4. 输出 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `compile_brand_overlay_view.py` | py | 是 | 是 |
| `brand_overlay_view.csv` | csv | 派生 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| domain_general 误入 overlay | fail（S3） |
| overlay_kind 非 4 枚举 | fail |
| 门店纪律内容混入 overlay | fail（按 CLAUDE.md 红线，关键词扫描） |
| 缺 precedence | fail |
| 幂等 | 一致 |

## 7. 治理语义一致性
- 严格遵守 CLAUDE.md 多租户红线：overlay 只放品牌调性 + 创始人画像
- clean_output 0 写
- 不调 LLM
- brand_layer 不得为 domain_general

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_brand_overlay_view.py --check
pass: exit 0 + S3 全绿 + 关键词扫描无误入
artifact: brand_overlay_view.csv
```

## 9. CD / 环境验证
离线。

## 10. 独立审查员 Prompt
> 请：1) 任一行 brand_layer == "domain_general" 必须 fail；2) 抽样检查 overlay 内容确实是品牌调性 / 创始人画像，而非门店纪律；3) 输出 pass / fail。
> 阻断项：domain_general 行混入；门店纪律 / 商品事实出现在 overlay。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 多租户红线扫描通过
- [ ] 审查员 pass
