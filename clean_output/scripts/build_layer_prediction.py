#!/usr/bin/env python3
"""W11.1a · 三层粒度启发式预分

输入:
  audit/source_unit_adjudication.csv   (1578 章节)
  audit/source_unit_inventory.csv      (heading_path / line_no / body_first_100)
  candidates/**/*.yaml                  (194 已入库 pack)

输出:
  audit/source_unit_adjudication_v2.csv
    新增列：suggested_layer, suggested_status, confidence, rationale, needs_human_review
  audit/pack_layer_register.csv
    每条已入库 pack 一行：pack_id, suggested_layer, confidence, rationale

启发式规则（D5 决议：高置信自动签，低置信进人工队列）:
  规则集合 R1-R8 见下方注释。
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADJ = ROOT / "audit" / "source_unit_adjudication.csv"
INV = ROOT / "audit" / "source_unit_inventory.csv"
CAND = ROOT / "candidates"
OUT_SU = ROOT / "audit" / "source_unit_adjudication_v2.csv"
OUT_PK = ROOT / "audit" / "pack_layer_register.csv"

# --- 词典 ---
L2_KEYWORDS = [
    "玩法", "玩法卡", "play_card", "play card",
    "短视频结构", "选题", "脚本骨架", "栏目设计", "拍摄结构",
    "tier", "instant", "long_term", "brand_tier",
    "production_difficulty", "shooting_feasibility", "实拍",
    "1人手机", "4小时", "200元",
]
L3_KEYWORDS = [
    "镜头", "分镜", "运镜", "走位", "构图",
    "台词", "口播", "解说",
    "动作", "手势", "拍摄动作", "道具", "服装搭配清单",
    "员工分工", "角色分工", "店员", "店长指令",
    "拍摄步骤", "执行步骤", "操作步骤",
    "禁忌词", "禁区", "不可说",
]
NEGATIVE_L1_HINTS = [
    "一定不行的玩法",  # negative samples → unprocessable
]


def hits(keywords, text):
    return [k for k in keywords if k.lower() in text.lower()]


# --- 章节级预分 ---
def predict_source_unit(row, body_text):
    heading = row.get("heading_path", "")
    body = body_text or ""
    full = heading + "\n" + body[:500]
    cur_status = row["adjudication_status"]
    cur_sub = row.get("sub_reason", "")

    # 已是 unprocessable / duplicate / covered → 高置信继承
    if cur_status == "unprocessable":
        return "L_NA", "unprocessable", "high",\
               f"沿用 W10 unprocessable ({cur_sub})", False
    if cur_status == "duplicate_or_redundant":
        return "L_NA", "duplicate", "high",\
               "沿用 W10 duplicate", False
    if cur_status == "covered_by_pack":
        # 已入库的章节默认 L1，但若 heading 强 L2 则提示回标
        l2_hits = hits(L2_KEYWORDS, full)
        if l2_hits:
            return "L2", "extract_l1", "low",\
                   f"已入库默认 L1，但 heading/body 命中 L2 词 {l2_hits[:3]}，建议人工回标", True
        return "L1", "extract_l1", "high",\
               "已入库章节默认 L1（pack_layer_register 同步标）", False

    # uncovered (=W10 pending_decision) → 主决策
    # 1) 负面玩法 → unprocessable
    if any(n in heading for n in NEGATIVE_L1_HINTS):
        return "L_NA", "unprocessable", "high",\
               "标题含'一定不行的玩法'等负面样本", False

    # 2) 短节 < 100 字（W10 已分流；这里防漏网）
    body_len = int(row.get("body_length") or 0)
    if body_len < 100 and cur_status == "pending_decision":
        # 若 W10 没归 short 但实际 < 100，再筛一次
        return "L_NA", "unprocessable", "medium",\
               f"body_length={body_len} < 100，建议归 unprocessable", body_len < 50

    # 3) L3 强信号
    l3_hits = hits(L3_KEYWORDS, full)
    if len(l3_hits) >= 2:
        return "L3", "defer_l3_to_runtime_asset", "high",\
               f"L3 词 ≥2: {l3_hits[:5]}", False
    if len(l3_hits) == 1:
        return "L3", "defer_l3_to_runtime_asset", "low",\
               f"L3 词 1: {l3_hits}（低置信）", True

    # 4) L2 强信号
    l2_hits = hits(L2_KEYWORDS, full)
    if len(l2_hits) >= 2 or "玩法卡" in heading or re.search(r"#C\d", heading):
        return "L2", "extract_l2", "high",\
               f"L2 强信号：玩法卡/编号/词={l2_hits[:5]}", False
    if len(l2_hits) == 1:
        return "L2", "extract_l2", "low",\
               f"L2 词 1: {l2_hits}（低置信）", True

    # 5) 默认 L1（业务章节，无 L2/L3 信号）
    if body_len >= 300:
        return "L1", "extract_l1", "medium",\
               "未命中 L2/L3 信号，body 较长，建议 L1 抽取（中置信）", True
    return "L1", "extract_l1", "low",\
           "未命中 L2/L3 信号，建议 L1 但需人工二审", True


# --- pack 级预分 ---
def predict_pack(yaml_text):
    text = yaml_text.lower()
    l2 = hits(L2_KEYWORDS, text)
    l3 = hits(L3_KEYWORDS, text)
    if "play_card" in text or "play_card_tier" in text or "tier:" in text and "instant" in text:
        return "L2", "high", f"yaml 含 play_card/tier 字段：{l2[:3]}"
    if len(l2) >= 2:
        return "L2", "medium", f"L2 词 ≥2: {l2[:3]}"
    if len(l3) >= 2:
        return "L3", "medium", f"L3 词 ≥2: {l3[:3]}"
    if l2:
        return "L1", "low", f"含 L2 词 1（{l2}），可能 L1/L2 边界，需审"
    return "L1", "high", "无 L2/L3 强信号，默认 L1"


def main():
    # 加载 inventory 拼 body 文本
    inv = list(csv.DictReader(INV.open(encoding="utf-8")))
    inv_idx = {(r["source_md"], r["heading_path"]): r for r in inv}

    rows = list(csv.DictReader(ADJ.open(encoding="utf-8")))
    out = []
    counter_status = Counter()
    counter_layer = Counter()
    counter_conf = Counter()
    needs_review = 0

    for r in rows:
        body = inv_idx.get((r["source_md"], r["heading_path"]), {}).get("body_first_100", "")
        layer, status, conf, rationale, need_h = predict_source_unit(r, body)
        if need_h:
            needs_review += 1
        counter_status[status] += 1
        counter_layer[layer] += 1
        counter_conf[conf] += 1
        # Finding 2 修复：W10 的 rationale 字段重命名为 w10_rationale，启发式用 suggestion_rationale
        d = dict(r)
        d["w10_rationale"] = d.pop("rationale", "")
        d.update({
            "suggested_layer": layer,
            "suggested_status": status,
            "confidence": conf,
            "suggestion_rationale": rationale,
            "needs_human_review": "true" if need_h else "false",
            # 人工写回列（默认空）
            "reviewer_decision": "",
            "final_layer": "",
            "final_status": "",
            "merge_target": "",
            "production_tier": "",
            "default_call_pool": "",
            "review_notes": "",
        })
        out.append(d)

    OUT_SU.parent.mkdir(parents=True, exist_ok=True)
    # 列序：W10 base 列（rationale → w10_rationale）+ 启发式 + 人工写回
    base_cols = [c if c != "rationale" else "w10_rationale" for c in rows[0].keys()]
    cols = base_cols + [
        "suggested_layer", "suggested_status",
        "confidence", "suggestion_rationale", "needs_human_review",
        "reviewer_decision", "final_layer", "final_status",
        "merge_target", "production_tier", "default_call_pool", "review_notes",
    ]
    with OUT_SU.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    # ===== pack 预分 =====
    pack_rows = []
    pack_layer = Counter()
    pack_conf = Counter()
    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = CAND / sub
        if not d.exists():
            continue
        for y in sorted(d.glob("*.yaml")):
            text = y.read_text(encoding="utf-8")
            layer, conf, rationale = predict_pack(text)
            pack_rows.append({
                "pack_id": y.stem,
                "brand_layer_dir": sub,
                "suggested_layer": layer,
                "confidence": conf,
                "suggestion_rationale": rationale,
                "needs_human_review": "true" if conf == "low" else "false",
                # 人工写回列
                "reviewer_decision": "",
                "final_layer": "",
                "production_tier": "",
                "default_call_pool": "",
                "review_notes": "",
            })
            pack_layer[layer] += 1
            pack_conf[conf] += 1

    with OUT_PK.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "pack_id", "brand_layer_dir",
            "suggested_layer", "confidence",
            "suggestion_rationale", "needs_human_review",
            "reviewer_decision", "final_layer",
            "production_tier", "default_call_pool", "review_notes",
        ])
        w.writeheader()
        w.writerows(pack_rows)

    print("=== W11.1a 三层启发式预分 ===\n")
    print(f"【source_unit 预分】 {len(rows)} 行")
    print(f"  layer 分布   : {dict(counter_layer)}")
    print(f"  status 分布  : {dict(counter_status)}")
    print(f"  confidence   : {dict(counter_conf)}")
    print(f"  待人工复核   : {needs_review} 条 ({needs_review*100//len(rows)}%)")
    print(f"  → {OUT_SU}\n")

    print(f"【pack 预分】 {len(pack_rows)} 个")
    print(f"  layer 分布 : {dict(pack_layer)}")
    print(f"  confidence : {dict(pack_conf)}")
    needs_pk = sum(1 for r in pack_rows if r["needs_human_review"] == "true")
    print(f"  待人工复核 : {needs_pk} 条")
    print(f"  → {OUT_PK}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
