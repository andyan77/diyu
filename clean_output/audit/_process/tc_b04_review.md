---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# TC-B04 复核报告 · 门店接客场景包（补完）

> 日期：2026-05-03
> 范围：TC-B04 单卡流程验证 · 补完 9 类剩余接客场景 + 跨切裁决
> 状态：进行中（每抽 3 条增量追加一节）

---

## 1. 已抽 CandidatePack 路径与核心断言（增量追加）

### 第 1 批（pack 01-03）

| # | pack_id | knowledge_assertion（一句话压缩） |
|---|---|---|
| 01 | KP-service_judgment-urgent-full-look | 应急客先问 5 件事；第一套"能去"、第二套"像她"；主件断码不许气质硬转 |
| 02 | KP-service_judgment-commute-mainstay | 通勤客第二套必须挂"利用率"理由，不能再叠"也能穿"；断码可救但保功能 |
| 03 | KP-service_judgment-weekend-social | 周末客先判状态感（松弛/精致/显气色），先陈列后开口；断码只许同气质转 |

### 第 2 批（pack 04-06）

| # | pack_id | knowledge_assertion（一句话压缩） |
|---|---|---|
| 04 | KP-service_judgment-shape-correction | 显瘦客先定位部位+确认 4 参数；卖的是安全感，关键版型断码不许硬救 |
| 05 | KP-service_judgment-ready-made-full-set | 现成成套客先判动机（省心/速度/不会搭）；断码必须按整体气质成对替换 |
| 06 | KP-service_judgment-functional-gap-fill | 补位客先问衣柜地图；卡的是利用率讲不透；断码最容易救 |

### 第 3 批（pack 07-09）

| # | pack_id | knowledge_assertion（一句话压缩） |
|---|---|---|
| 07 | KP-service_judgment-new-item-cannot-style | 新款不会搭客必须当场给两条路；第二套守使用路径；断码可救 |
| 08 | KP-service_judgment-budget-controlled | 预算客先锁"主力 vs 组合""单价 vs 利用率"；要的是确定性，不许加件凑预算 |
| 09 | KP-service_judgment-repeat-purchase-replenish | 复购客必须识别上次满意的是哪一轴；断码同轴替，禁差不多糊弄 |

**至此 9 类剩余接客场景 + 已抽 comfort_sensitive = 10/10 类 100% 覆盖。**

### 第 4 批（pack 10-12 跨切裁决）

| # | pack_id | knowledge_assertion（一句话压缩） |
|---|---|---|
| 10 | KP-service_judgment-greeting-master-principles | 接客 4 总原则：先判任务/先问顾虑/三套不同逻辑/断码先看场景 |
| 11 | KP-service_judgment-second-third-set-blocker | 5 类卡第二/三套场景必须在第二套切换推荐逻辑 |
| 12 | KP-inventory_rescue-can-rescue-scenarios | 5 类断码可救场景必须按"核心轴"替代而非按嘴推 |

### 第 5 批（pack 13-16 跨切裁决 + 培训承接）

| # | pack_id | knowledge_assertion（一句话压缩） |
|---|---|---|
| 13 | KP-inventory_rescue-no-rescue-scenarios | 3 类不可救：shape/comfort/urgent 主件断；硬救必伤复购信任 |
| 14 | KP-display_rule-display-first-then-speak | 4 类先陈列后开口；过早开口打断顾客视觉判断流 |
| 15 | KP-service_judgment-must-ask-first | 6 类必须先问再推；锁定前置参数后再推第一套 |
| 16 | KP-training_unit-greeting-format-lock | 培训格式锁定 4 种；长视频/统一话术/PPT 录屏禁用 |

**至此 TC-B04 共抽 16 条 CandidatePack（10 类场景细则 + 6 类跨切裁决与培训承接），算上 TC-01 已抽的 comfort_sensitive 共 17 条覆盖本素材包。**
