---
snapshot_type: live
last_validated: 2026-05-04
rationale: W13.A 跨工作区源料引入决策诚实记录 · 后续 reviewer 审查时可对账
---

# W13.A · 跨工作区源料引入决策书

> 状态：用户授权越线 + 已落档诚实记录
> 触发：Finding 2/3 之上的下一层缺口——brand_faye=0 致命缺失（W11/W12 都未能解决）

---

## 一、CLAUDE.md 红线条款（被本次决策越界的部分）

仓库 CLAUDE.md 项目级红线明文：
> **不读、不引用、不继承**任何旧工作区的历史产物、旧状态、旧候选。
> 当前工作区没有的信息 → 标 `unknown_in_current_workspace`，不许凭记忆补。
> 输入范围只处理 `Q2-内容类型种子/`、`Q4-人设种子/`、`Q7Q12-搭配陈列业务包/`。

本决策**显式越界**：从 `/home/faye/dev/diyu-infra-05/data/mvp/seeds/` 引入笛语品牌专属内容到当前仓库。

---

## 二、决策依据

1. **业务必要性**：W12.A 收口后判定库内 brand_faye=0 是阻碍 AI 内容生成质量的最大短板（详见 `audit/w12_acceptance_report.md` + 内容质量评估）。
2. **平台事实**：2026 年小红书打击 AI 托管账号、抖音趋势是"心智壁垒品牌"，缺品牌人格的 AI 生成内容是被禁/被算法降权的形态。
3. **用户显式授权**：用户在多轮对话中明确指示"将适配品牌笛语的专属的内容全部迁移至当前路径，并按照当前仓库的要求，提取入库"。
4. **范围最小化**：本次仅引入 7 份 visibility=brand 的笛语专属 JSON，不动 49 份 visibility=global 的通用内容（避免与既有库重叠/冲突）。

---

## 三、引入清单（7 份笛语专属 JSON）

| # | 源文件 | 实质内容 | 预估派生 pack |
|---|---|---|---:|
| 1 | `brand_tone/brandtone_diyu_001.json` | 品牌调性：5 personality_tags / 3 tone_axis / 6+5 情绪边界 / 5+5 锚点 / 15+8 词汇 / 5 signature_phrases / 4 平台调性 / 盲听测试 | 5-8 |
| 2 | `persona/persona_founder_demo.json` | 笛语创始人 Persona（认真做衣服的人） | 4-6 |
| 3 | `persona/persona_franchise_owner_demo.json` | 笛语加盟店主 Persona | 3-4 |
| 4 | `persona/persona_sample_maker_demo.json` | 笛语样衣师 Persona | 3-4 |
| 5 | `content_type/ctype_founder_ip.json` | 创始人 IP 内容类型（含输出结构 + 钩子 + CTA + 示例） | 3-5 |
| 6 | `content_type/ctype_process_trace.json` | 流程溯源内容类型 | 3-5 |
| 7 | `content_type/ctype_store_daily.json` | 门店日常内容类型 | 3-5 |

预估总计 24-37 个 brand_faye CandidatePack。

---

## 四、安全护栏

为避免越线带来污染，本次引入加 4 道护栏：

| 护栏 | 实现 |
|---|---|
| **来源标识** | 每个新增 md 文件加 frontmatter `source_workspace: diyu-infra-05/data/mvp/seeds`（区别于原 3 目录素材）|
| **目录隔离** | 新建独立目录 `Q-brand-seeds/`，**不混入** Q2/Q4/Q7Q12 |
| **裁决隔离** | 抽出的 pack 全部先进 `candidates/needs_review/`，等 reviewer 审完再迁 brand_faye |
| **brand_layer 标识** | brand_id 源文件标 `diyu_001`，仓库 schema 以 `brand_faye` 承载（保持向后兼容；映射记录见 §五）|

---

## 五、brand_id ↔ brand_layer 映射记录

源料 JSON 的 `brand_id: diyu_001` 与 `brand_name: 笛语（DIYU）`，在当前仓库 multi-tenant schema 下统一标记为 `brand_layer: brand_faye`（CLAUDE.md §3.5 已立法笛语应用查询为 `WHERE brand_layer IN ('domain_general','brand_faye')`）。

未来如有其他 diyu_xxx 子品牌，可在 brand_layer 上再分（`brand_diyu_xxx`），但本轮不引入歧义。

---

## 六、引入流程（按 27 道硬门兼容口径）

1. **W13.A.1**（本文档）· 决策落档
2. **W13.A.2** · 建 `/home/faye/20-血肉-2F种子/Q-brand-seeds/` 目录
3. **W13.A.3** · 7 份 JSON 转 MD（保留全部 12 个顶层字段为 H2 章节，子字段为 H3）
4. **W13.A.4** · 更新 `parse_md_source_units.py` / `scan_unprocessed_md.py` / `compute_coverage_status.py` 输入扫描范围 +1 (`Q-brand-seeds/`)
5. **W13.A.5** · 按 `extract-9tables` skill 抽取 → `candidates/needs_review/`
6. **W13.A.6** · 27 道硬门回归 + W11 三层重裁 + W12 G20/G21 重跑（不应回退）

---

## 七、回滚预案

如本轮引入造成 27 道硬门回退、或与现有库不可调和冲突：

```bash
# 1. 删除 Q-brand-seeds/
rm -rf /home/faye/20-血肉-2F种子/Q-brand-seeds/

# 2. 删除 needs_review/ 下本轮新增 yaml（按 source_workspace 标记可识别）
grep -lR "source_workspace: diyu-infra-05" clean_output/candidates/ | xargs rm

# 3. 还原 parse_md_source_units.py 扫描列表
# 4. 重跑 27 道硬门
```

---

## 八、责任与审计

- 决策人：用户（多轮对话明确授权）
- 执行人：Claude Code agent
- 责任承担：W13.A 完成后由 reviewer 在下次 review 中复核本决策的合理性
- 时间戳：2026-05-04
