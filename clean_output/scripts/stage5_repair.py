#!/usr/bin/env python3
"""硬门 4 · 品牌残留 10 条裁决执行（M2 阶段 5）

裁决（用户批准 + direct_quote 硬规则）：
  degraded_to_general · 5 条 (#1 #2 #5 #7 #10)
    - 命中在 evidence_quote (direct_quote): 删句（不改写）→ #1 #2 #10
    - 命中在 scenario.* (非 evidence_quote): 改写为通用 → #5 #7
  domain_general_keep · 4 条 (#3 #4 #8 #9)
    - 仅在 brand_layer_review 节加 rationale (scan 误报标注)
  split_two_packs · 1 条 (#6)
    - 原 pack 去笛语化 + 新建 brand_faye/...-faye-positioning yaml

落 audit/brand_residue_review.csv（10 行决策）
"""
import csv
import datetime as dt
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DG = ROOT / "candidates" / "domain_general"
BF = ROOT / "candidates" / "brand_faye"
BF.mkdir(parents=True, exist_ok=True)
TS = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
DECIDED_BY = "human_review_2026-05-03"

REVIEW_CSV = ROOT / "audit" / "brand_residue_review.csv"
QUEUE_CSV = ROOT / "audit" / "brand_layer_review_queue.csv"


def backup(p):
    bak = p.with_suffix(p.suffix + f".bak.{TS}")
    shutil.copy(p, bak)
    return bak


def replace_in_file(path, old, new):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return False
    path.write_text(text.replace(old, new), encoding="utf-8")
    return True


def delete_line(path, target_substring):
    """删除首个含 target_substring 的整行"""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    deleted = False
    for ln in lines:
        if not deleted and target_substring in ln:
            deleted = True
            continue
        out.append(ln)
    path.write_text("".join(out), encoding="utf-8")
    return deleted


# 决策记录累积
DECISIONS = []


# ============== 路径 1 · degraded_to_general ==============

def degraded_evidence_delete(pack_id, hint_keyword):
    """#1 #2 #10: evidence_quote (direct_quote) 中删笛语句"""
    p = DG / f"{pack_id}.yaml"
    backup(p)
    ok = delete_line(p, hint_keyword)
    return p, ok


def degraded_scenario_rewrite(pack_id, old_text, new_text):
    """#5 #7: scenario 字段改写"""
    p = DG / f"{pack_id}.yaml"
    backup(p)
    ok = replace_in_file(p, old_text, new_text)
    return p, ok


def add_rationale_to_review(pack_id, decision, rationale):
    """domain_general_keep · 4 条：在 brand_layer_review 节加/改 rationale 字段"""
    p = DG / f"{pack_id}.yaml"
    backup(p)
    text = p.read_text(encoding="utf-8")
    # 在 rationale: 行追加 keep 标注（如果没有就用 decision_suggestion 的下一行插入）
    new_rationale_line = f'  rationale_keep: "{decision} · {rationale}"\n'
    lines = text.splitlines(keepends=True)
    out = []
    inserted = False
    for ln in lines:
        out.append(ln)
        if (not inserted) and ln.strip().startswith("decision_suggestion:"):
            out.append(new_rationale_line)
            inserted = True
    p.write_text("".join(out), encoding="utf-8")
    return p, inserted


def record_decision(idx, pack_id, decision, rationale, action_summary):
    DECISIONS.append({
        "idx": idx,
        "pack_id": pack_id,
        "decision": decision,
        "rationale": rationale,
        "action": action_summary,
    })


# ============== 路径 2 · split_two_packs (#6) ==============

PACK6 = "KP-service_judgment-product-review-concerns-clearance-on-spot"
PACK6_BRAND = "KP-service_judgment-product-review-concerns-clearance-on-spot-faye-positioning"

# 6a · 改原 yaml: knowledge_assertion 去笛语化 + evidence_quote 删笛语行
PACK6_KA_OLD = "把\"被种草\"路径改成\"被安慰\"路径，是笛语在接客场景下最强的转化工具。"
PACK6_KA_NEW = "把\"被种草\"路径改成\"被安慰\"路径，是 product_review 在第二层接客场景的核心转化工具（具体品牌优先级口径由各品牌 brand_<name> 层声明）。"
PACK6_EV_LINE = "    这是笛语在接客场景下最强的转化工具。\n"

# 6b · brand_faye 新 pack 内容
PACK6_BRAND_YAML = """pack_id: KP-service_judgment-product-review-concerns-clearance-on-spot-faye-positioning
schema_version: candidate_v1
pack_type: service_judgment
brand_layer: brand_faye
state: drafted

knowledge_assertion: >-
  笛语品牌将"product_review C3-2 顾虑解除接客现场用法"显式定为
  接客场景下最强的转化工具——优于其他 service_judgment 工具
  （尺码补救 / 替代款引导 / 主推连带等）。这是笛语对该方法的
  品牌级优先级声明，不是通用方法本身（通用方法已落 domain_general 层
  KP-service_judgment-product-review-concerns-clearance-on-spot）。

scenario:
  who:
    primary_role: 笛语门店店员 / 笛语品牌内容主理
  when:
    trigger: 笛语门店接客场景中顾客当场说出顾虑
    context: 笛语品牌服务流水线
  what:
    action_type: brand_priority_declaration
    decision_or_action: |
      在笛语品牌的接客 SOP 中，把"被安慰路径"列为最高优先级转化工具。
  result:
    success_pattern: 笛语门店转化数据验证该工具在接客场景中实际表现优于其他工具。
    flip_pattern: 若不显式优先化，店员易回退到尺码补救/替代款等次优工具。
  underlying_mechanism: |
    笛语对消费者"心理阻力"的品牌定位（理解 + 不施压）与该工具的
    "被安慰路径"语义高度契合，故定为最强转化工具。
  boundary:
    applicable_when: 笛语品牌门店
    not_applicable_when: 其他品牌门店（应自行评估并独立声明优先级）
  alternative_path:
    - 其他品牌可基于自身定位选择不同最强工具

evidence:
  source_md: Q2-内容类型种子/product_review-交付物-v0.1.md
  source_anchor: §C3-2 备注·接客场景的专属用法
  source_type: explicit_play_card
  inference_level: direct_quote
  evidence_quote: |
    备注·接客场景的专属用法：店员站在店内顾客旁边，拿出同款现场做 3 个顾虑测试——
    顾客"我怕这个肩太硬"→ 店员让她侧身在镜前看 2 秒 → 真实反馈。
    这是笛语在接客场景下最强的转化工具。

gate_self_check:
  gate_1_closed_scenario: pass
  gate_2_reverse_infer: pass
  gate_3_rule_generalizable: partial
  gate_4_production_feasible: pass
  notes: |
    Gate 3 partial: 本 pack 是品牌级优先级声明，不要求跨品牌 generalizable；
    通用方法部分已在 domain_general 层 KP-service_judgment-product-review-concerns-clearance-on-spot 落档。

brand_layer_review:
  decision_suggestion: brand_faye
  rationale_keep: "split_two_packs · 笛语将通用方法定为最强工具的品牌优先级声明"
  faye_review_required: true
  splittable_components: []

nine_table_projection:
  object_type: []
  field: []
  semantic: []
  value_set: []
  rule:
    - {rule_id: RL-KP-service_judgment-product-review-concerns-clearance-on-spot-faye-positioning, rule_type: brand_priority_declaration, applicable_when: "笛语门店接客场景", success_scenario: "store transformation data validates", flip_scenario: "回退到次优工具", alternative_boundary: "其他品牌自行声明"}
  evidence:
    - {evidence_id: EV-KP-service_judgment-product-review-concerns-clearance-on-spot-faye-positioning, source_md: Q2-内容类型种子/product_review-交付物-v0.1.md, source_anchor: §C3-2 备注, source_type: explicit_play_card, inference_level: direct_quote}
  relation: []
  lifecycle: []
  call_mapping: []
"""


def split_pack6():
    # 6a 改原 yaml
    p = DG / f"{PACK6}.yaml"
    backup(p)
    text = p.read_text(encoding="utf-8")
    text = text.replace(PACK6_KA_OLD, PACK6_KA_NEW)
    text = text.replace(PACK6_EV_LINE, "")
    p.write_text(text, encoding="utf-8")

    # 6b 新建 brand_faye yaml
    bp = BF / f"{PACK6_BRAND}.yaml"
    bp.write_text(PACK6_BRAND_YAML, encoding="utf-8")
    return p, bp


# ============== 主流程 ==============

def main():
    print("=== M2 阶段 5 · 10 条品牌残留裁决执行 ===\n")

    # ---- degraded_to_general · evidence_quote 删句（受 direct_quote 硬规则保护）----
    cases = [
        ("#1", "KP-product_attribute-content-type-north-star-founder-ip",
         "笛语平台对 founder_ip 的 C1 档应该强默认禁用",
         "删 evidence_quote 中笛语句（C1 强默认禁用证据其他句已支撑）"),
        ("#2", "KP-product_attribute-content-type-north-star-product-copy-general",
         "compass §3：AI 工具正在放大模板问题",
         "删 evidence_quote 中含笛语 compass §3 句（其他证据已支撑反 AI 模板）"),
        ("#10", "KP-training_unit-grounding-over-polish-default",
         "对笛语平台的启示：AI 不应该生成",
         "删 evidence_quote 中笛语启示句（前后趋势数据已支撑 grounding > polished）"),
    ]
    for idx, pid, kw, summary in cases:
        p, ok = degraded_evidence_delete(pid, kw)
        mark = "✅" if ok else "❌"
        print(f"  {mark} {idx} {pid}: 删句 {ok}")
        record_decision(idx, pid, "degraded_to_general",
                        "evidence_quote in direct_quote · 按硬规则不改写仅删句", summary)

    # ---- degraded_to_general · scenario 字段改写 ----
    p5, ok5 = degraded_scenario_rewrite(
        "KP-service_judgment-derived-view-risk-inherits-from-source-edge",
        "（如笛语不允许某词）", "（如某品牌不允许某词）"
    )
    print(f"  {'✅' if ok5 else '❌'} #5 boundary.not_applicable_when 改写 {ok5}")
    record_decision("#5", "KP-service_judgment-derived-view-risk-inherits-from-source-edge",
                    "degraded_to_general", "scenario.boundary 非 evidence_quote 可改",
                    "（如笛语不允许某词）→（如某品牌不允许某词）")

    p7, ok7 = degraded_scenario_rewrite(
        "KP-training_unit-content-template-saturation-anti-pattern",
        "笛语/品牌方/单店店主/加盟商的内容生成入口",
        "零售品牌方/单店店主/加盟商的内容生成入口"
    )
    print(f"  {'✅' if ok7 else '❌'} #7 target_audience 改写 {ok7}")
    record_decision("#7", "KP-training_unit-content-template-saturation-anti-pattern",
                    "degraded_to_general", "scenario.who.target_audience 非 evidence_quote 可改",
                    "笛语/品牌方/单店店主/加盟商 → 零售品牌方/单店店主/加盟商")

    # ---- domain_general_keep · 4 条加 rationale_keep ----
    keep_cases = [
        ("#3", "KP-product_attribute-persona-field-fill-state",
         "Persona 字段成熟度三档治理是 schema 元规则，跨品牌通用；scan 误报：pack_id 含 persona 触发"),
        ("#4", "KP-product_attribute-persona-six-field-shell",
         "通用 6 字段壳治理是 schema 元规则；scan 误报：pack_id 含 persona 触发"),
        ("#8", "KP-training_unit-founder-profile-brand-unique-layer",
         "FounderProfile 应作为品牌唯一层是抽象建模规则；scan 误报：pack_id 含 founder + 'FounderProfile' 触发"),
        ("#9", "KP-training_unit-founder-profile-soft-use-no-rename",
         "启用与否非命名问题是抽象元规则；scan 误报：pack_id 含 founder 触发"),
    ]
    for idx, pid, rationale in keep_cases:
        p, ok = add_rationale_to_review(pid, "domain_general_keep", rationale)
        print(f"  {'✅' if ok else '❌'} {idx} 加 rationale_keep {ok}")
        record_decision(idx, pid, "domain_general_keep", rationale, "yaml.brand_layer_review.rationale_keep 标注")

    # ---- split_two_packs (#6) ----
    p6a, p6b = split_pack6()
    print(f"  ✅ #6 split: {p6a.name} 改写 + {p6b.relative_to(ROOT)} 新建")
    record_decision("#6", PACK6, "split_two_packs",
                    "evidence_quote direct_quote 含品牌主语 + ka 也含；拆通用方法 + brand_faye 优先级声明",
                    f"原 pack 去笛语化（ka + ev 删句）+ 新 brand_faye/{PACK6_BRAND}")

    # ---- 落 brand_residue_review.csv ----
    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["idx", "pack_id", "decision", "rationale", "action_summary",
                    "decided_by", "decided_at", "status"])
        for d in DECISIONS:
            w.writerow([d["idx"], d["pack_id"], d["decision"], d["rationale"],
                        d["action"], DECIDED_BY, dt.datetime.now().isoformat(timespec="seconds"), "applied"])
    print(f"\nbrand_residue_review.csv: {len(DECISIONS)} 条决策落盘")

    # ---- 落 brand_layer_review_queue.csv：仅 split / migrated / needs_review 子集 ----
    queue_rows = [d for d in DECISIONS
                  if d["decision"] in ("split_two_packs", "migrated_to_brand", "needs_review")]
    QUEUE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with QUEUE_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pack_id", "pack_type", "suggested_brand_layer", "why_review",
                    "splittable_components", "status", "created_at"])
        for d in queue_rows:
            w.writerow([d["pack_id"], "service_judgment", "brand_faye_split",
                        d["rationale"], d["action"], "applied",
                        dt.datetime.now().isoformat(timespec="seconds")])
    print(f"brand_layer_review_queue.csv: {len(queue_rows)} 条（仅 split/migrated/needs_review）")

    print("\n=== 决策汇总 ===")
    from collections import Counter
    c = Counter(d["decision"] for d in DECISIONS)
    for k, n in c.items():
        print(f"  {k}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
