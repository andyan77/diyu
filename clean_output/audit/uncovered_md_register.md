# uncovered_md_register · 5-class 闭环登记

> 重渲染于 W1 治理收口
> 数据源：scan_unprocessed_md 实测 + grep candidates yaml + register.csv 反查
> 全集 N = 8 份未抽 MD · 全部已签字闭环（_pending_review_ 已清零）

## 5 类闭环分类（reviewer-approved）

| classification | 含义 |
|---|---|
| `covered_by_pack` | 已直接落 CandidatePack |
| `unprocessable` | 已登记 unprocessable_register（含 external_reference_material 等具体子类）|
| `cross_source_reference` | 文件名/段落被其他 pack 直引覆盖 |
| `meta_non_business` | 工作区导航 / 红线说明 / 元层文件，非业务素材 |
| `gap_decision` | 由 skeleton_gap_register 决议覆盖 |

## 全 8 份签字清单

| source_md | classification | resolved_by | rationale |
|---|---|---|---|
| Q2-内容类型种子/CLAUDE.md | meta_non_business | system_meta_non_business_v1 | 工作区红线说明，非业务素材 |
| Q2-内容类型种子/_index.md | meta_non_business | system_meta_non_business_v1 | 工作区导航文件 |
| Q4-人设种子/_index.md | meta_non_business | system_meta_non_business_v1 | 工作区导航文件 |
| Q2-内容类型种子/compass_artifact_wf-6a00fe44-74d6-4f0c-b6c9-c3e309071f66_text_markdown.md | unprocessable | UP-tcb17-003 | external_reference_material（综述）已登记 |
| Q2-内容类型种子/企业叙事类compass_artifact.md | unprocessable | UP-tcb16-001;UP-tcb16-002 | external_reference_material（综述）已登记 |
| Q2-内容类型种子/企业叙事类deep-research-report.md | unprocessable | UP-tcb16-003 | external_reference_material（综述）已登记 |
| Q2-内容类型种子/深度研究.md | unprocessable | UP-tcb17-001;UP-tcb14-b3-002 | external_reference_material（综述）已登记 |
| Q2-内容类型种子/GPT5.4.md | cross_source_reference | KP-training_unit-enterprise-narrative-object-witness-over-talking-head; KP-training_unit-enterprise-narrative-anti-ai-tone; KP-training_unit-enterprise-narrative-north-star-first; KP-product_attribute-enterprise-narrative-six-section-shell | yaml 中文件名直引（grep 命中 4 个 pack）|

## 验收门

- 8 份 resolved_by 全部非空且非 `_pending_review_` ✅
- 5 类分类映射完整 ✅
- meta_non_business 由 `system_meta_non_business_v1` 系统签发：规则为 CLAUDE.md / _index.md / `_*.md` 模式视为元层
- unprocessable 类签的是具体 unprocessable_id（在 register.csv 可查）
- cross_source_reference 签的是具体 pack_id 列表
- 无 gap_decision 类（reviewer 修正：不强行 GAP 化兜底）
