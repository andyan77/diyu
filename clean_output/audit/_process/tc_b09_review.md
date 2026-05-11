---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# TC-B09 复核报告 · 首批 Persona-RoleProfile 清单

> 日期：2026-05-03
> 范围：Q4 第四波首卡 · TC-B09 单卡流程验证
> 状态：**抽取进行中（按每 3 条 pack 滚动追加）**
> 特殊事项：**brand_faye 路径首次正式落档**

---

## 1. 滚动抽取记录（每 3 条追加）

### 1.1 第一组（pack #1-3，全部 domain_general）

| # | pack_id | brand_layer | knowledge_assertion（一句话压缩） |
|---|---|---|---|
| 1 | KP-training_unit-founder-profile-brand-unique-layer | domain_general | FounderProfile 是品牌唯一层（每品牌 0/1），仅服务 founder_ip，不入通用 Persona 编号体系；混编破坏品牌真实性 |
| 2 | KP-training_unit-persona-vs-roleprofile-layering | domain_general | 冷启动通用 Persona ≤3 套高频壳，不"一岗位一人设"；岗位真实感由 RoleProfile 补 |
| 3 | KP-training_unit-roleprofile-not-speaking-shell | domain_general | RoleProfile 是岗位知识底座，不是说话身份壳；Persona 调用 RoleProfile 才能既有人设又有真实感 |

**4 闸自检：3/3 全 pass。**
