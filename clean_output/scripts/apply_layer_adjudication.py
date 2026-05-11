#!/usr/bin/env python3
"""W11.1c · 三层裁决写回（强制 dry-run 默认）

依据 G19 契约（templates/G19_layer_adjudication_contract.md）：
- 默认 --dry-run：只输出变更摘要 + 冲突清单，不触碰任何文件
- 需 --apply --confirmed 才真实写回，并自动备份到 _process/_backup_w11/

读取:
  audit/source_unit_adjudication_v2.csv  (人工写回的 final_* 列)
  audit/pack_layer_register.csv          (人工写回的 final_layer / production_*)

写回（仅 --apply --confirmed）:
  audit/source_unit_adjudication.csv     (W10 主表升级到 W11 6 态)
  candidates/**/*.yaml                    (加 granularity_layer + production_* 字段)
  audit/_process/_backup_w11/             (备份)
  audit/merge_log.csv                     (追加 merge_to_existing 行)
  audit/coverage_status.json              (新增 layer_distribution 块)
"""
import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SU_V2 = ROOT / "audit" / "source_unit_adjudication_v2.csv"
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
SU_MAIN = ROOT / "audit" / "source_unit_adjudication.csv"          # W10 兼容（G16d_a 维护）
SU_W11 = ROOT / "audit" / "source_unit_adjudication_w11.csv"        # W11 三层主表（apply 维护，full_audit 不覆盖）
REVIEW_MUST = ROOT / "audit" / "review_must.csv"
PACK_REVIEW = ROOT / "audit" / "pack_review_must.csv"
CAND = ROOT / "candidates"
COV = ROOT / "audit" / "coverage_status.json"
BACKUP = ROOT / "audit" / "_process" / "_backup_w11"

REVIEWER_COLS = ["reviewer_decision", "final_layer", "final_status",
                 "merge_target", "production_tier", "default_call_pool", "review_notes"]
PACK_REVIEWER_COLS = ["reviewer_decision", "final_layer",
                      "production_tier", "default_call_pool", "review_notes"]


def merge_review_into_v2():
    """把 review_must.csv 的人工填写合并回 v2；高置自动行 reviewer_decision=accept (auto)
    返回填好 final_* 的完整 1578 行（不写盘）"""
    rows = list(csv.DictReader(SU_V2.open(encoding="utf-8")))
    review = {}
    if REVIEW_MUST.exists():
        for r in csv.DictReader(REVIEW_MUST.open(encoding="utf-8")):
            key = (r["source_md"], r["heading_path"], r.get("line_no", ""))
            review[key] = r

    auto_accept = 0
    merged = 0
    for r in rows:
        key = (r["source_md"], r["heading_path"], r.get("line_no", ""))
        if key in review:
            ans = review[key]
            for c in REVIEWER_COLS:
                r[c] = ans.get(c, "").strip()
            merged += 1
        else:
            # 自动 accept high 置信
            if r["needs_human_review"] == "false":
                r["reviewer_decision"] = "accept"
                r["final_status"] = r["suggested_status"]
                r["final_layer"] = r["suggested_layer"]
                r["review_notes"] = "auto-accept (high confidence)"
                auto_accept += 1
    return rows, merged, auto_accept


def merge_pack_review():
    rows = list(csv.DictReader(PK_REG.open(encoding="utf-8")))
    review = {}
    if PACK_REVIEW.exists():
        for r in csv.DictReader(PACK_REVIEW.open(encoding="utf-8")):
            review[r["pack_id"]] = r
    auto_accept = 0
    merged = 0
    for r in rows:
        if r["pack_id"] in review:
            ans = review[r["pack_id"]]
            for c in PACK_REVIEWER_COLS:
                r[c] = ans.get(c, "").strip()
            merged += 1
        else:
            if r["needs_human_review"] == "false":
                r["reviewer_decision"] = "accept"
                r["final_layer"] = r["suggested_layer"]
                r["review_notes"] = "auto-accept (high confidence)"
                auto_accept += 1
    return rows, merged, auto_accept

VALID_FINAL_STATUS = {
    "extract_l1", "extract_l2", "defer_l3_to_runtime_asset",
    "merge_to_existing", "unprocessable", "duplicate",
}
VALID_LAYER = {"L1", "L2", "L3", "L_NA"}
VALID_TIER = {"instant", "long_term", "brand_tier"}
VALID_DECISION = {"accept", "override", "defer"}


def validate_su_rows(rows):
    """G19 契约校验，返回冲突清单"""
    issues = []
    pack_ids = set()
    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = CAND / sub
        if d.exists():
            pack_ids |= {y.stem for y in d.glob("*.yaml")}

    for i, r in enumerate(rows, start=2):
        fs = r.get("final_status", "").strip()
        fl = r.get("final_layer", "").strip()
        rd = r.get("reviewer_decision", "").strip()
        notes = r.get("review_notes", "").strip()

        # 1. 全行非空
        if not fs:
            issues.append((i, r["heading_path"][:40], "final_status 为空"))
            continue
        if fs not in VALID_FINAL_STATUS:
            issues.append((i, r["heading_path"][:40], f"非法 final_status={fs}"))
            continue
        if rd and rd not in VALID_DECISION:
            issues.append((i, r["heading_path"][:40], f"非法 reviewer_decision={rd}"))

        # 2. 按 final_status 必填
        if fs == "extract_l1":
            if fl != "L1":
                issues.append((i, r["heading_path"][:40], f"extract_l1 但 final_layer={fl}"))
            if rd == "override" and len(notes) < 10:
                issues.append((i, r["heading_path"][:40], "override 但 review_notes < 10 字"))
        elif fs == "extract_l2":
            if fl != "L2":
                issues.append((i, r["heading_path"][:40], f"extract_l2 但 final_layer={fl}"))
            tier = r.get("production_tier", "").strip()
            pool = r.get("default_call_pool", "").strip().lower()
            if tier not in VALID_TIER:
                issues.append((i, r["heading_path"][:40], f"L2 production_tier 非法: {tier}"))
            if pool not in {"true", "false"}:
                issues.append((i, r["heading_path"][:40], f"L2 default_call_pool 非法: {pool}"))
        elif fs == "defer_l3_to_runtime_asset":
            if fl != "L3":
                issues.append((i, r["heading_path"][:40], f"defer_l3 但 final_layer={fl}"))
            if len(notes) < 10:
                issues.append((i, r["heading_path"][:40], "L3 review_notes < 10 字（应说明 asset_type）"))
        elif fs == "merge_to_existing":
            mt = r.get("merge_target", "").strip()
            if not mt:
                issues.append((i, r["heading_path"][:40], "merge_to_existing 但 merge_target 为空"))
            elif mt not in pack_ids:
                issues.append((i, r["heading_path"][:40], f"merge_target={mt} 不存在"))
        elif fs in ("unprocessable", "duplicate"):
            if fl != "L_NA":
                issues.append((i, r["heading_path"][:40], f"{fs} 但 final_layer={fl}（应为 L_NA）"))

        # 3. accept 一致性
        if rd == "accept":
            if fs != r.get("suggested_status") or fl != r.get("suggested_layer"):
                issues.append((i, r["heading_path"][:40],
                              f"accept 但 final({fs}/{fl}) != suggested({r.get('suggested_status')}/{r.get('suggested_layer')})"))

    return issues


def summarize_changes(rows):
    transitions = Counter()
    for r in rows:
        old = r.get("adjudication_status", "")
        new = r.get("final_status", "")
        if old and new:
            transitions[(old, new)] += 1
    return transitions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirmed", action="store_true")
    args = ap.parse_args()

    if not SU_V2.exists():
        print(f"❌ 缺 {SU_V2.relative_to(ROOT)}（先跑 build_layer_prediction.py）")
        return 2

    rows, merged_su, auto_su = merge_review_into_v2()
    pack_rows, merged_pk, auto_pk = merge_pack_review()

    print("=== W11.1c · 三层裁决写回 ===\n")
    print(f"模式: {'apply' if args.apply else 'dry-run（默认）'}")
    print(f"输入: {len(rows)} source_unit + {len(pack_rows)} pack")
    print(f"  source_unit: 人工裁决合并 {merged_su} + 高置自动 accept {auto_su} (合计 {merged_su+auto_su}/{len(rows)})")
    print(f"  pack       : 人工裁决合并 {merged_pk} + 高置自动 accept {auto_pk} (合计 {merged_pk+auto_pk}/{len(pack_rows)})\n")

    # G19 契约校验
    issues = validate_su_rows(rows)
    print(f"--- G19 契约校验 ---")
    if issues:
        print(f"❌ 发现 {len(issues)} 项契约违规（前 10 条）:")
        for line, head, msg in issues[:10]:
            print(f"  L{line:>4} {head:40s} {msg}")
        # 落违规清单
        out = ROOT / "audit" / "_process" / "g19_violations.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["line", "heading_excerpt", "issue"])
            w.writerows(issues)
        print(f"  完整清单 → {out}")
    else:
        print("  ✅ 契约校验通过（无违规）")

    # 变更摘要
    transitions = summarize_changes(rows)
    print(f"\n--- 变更摘要（from → to）---")
    for (old, new), n in sorted(transitions.items(), key=lambda x: -x[1]):
        if old != new:
            print(f"  {old:25s} → {new:30s} {n}")
    same = sum(n for (old, new), n in transitions.items() if old == new)
    print(f"  （状态不变 {same} 行）")

    # pack 摘要
    pack_layer_changes = Counter(r.get("final_layer", "") for r in pack_rows)
    print(f"\n--- pack 三层分布（final_layer）---")
    for k, v in pack_layer_changes.items():
        print(f"  {k or '(空)':10s} {v}")

    # 预览本次会触碰的文件清单（dry-run 也输出，便于人工确认）
    pack_layer_map = {r["pack_id"]: r for r in pack_rows}
    yaml_changes = []
    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = CAND / sub
        if not d.exists():
            continue
        for y in sorted(d.glob("*.yaml")):
            entry = pack_layer_map.get(y.stem)
            if not entry:
                continue
            yaml_changes.append((y, entry))

    print(f"\n--- 写回文件清单（dry-run 仅展示） ---")
    print(f"  audit/source_unit_adjudication.csv      [覆盖：1578 行，新增 final_status/final_layer/reviewer_decision/...]")
    print(f"  audit/pack_layer_register.csv           [覆盖：194 行，写入 final_layer + production 字段]")
    print(f"  audit/coverage_status.json              [新增 layer_distribution 块]")
    print(f"  candidates/**/*.yaml                    [194 个 yaml 注入 granularity_layer 字段；L2 加 production 块]")
    print(f"    L1 yaml: {sum(1 for _,e in yaml_changes if e.get('final_layer')=='L1')}")
    print(f"    L2 yaml: {sum(1 for _,e in yaml_changes if e.get('final_layer')=='L2')}")
    print(f"    L3 yaml: {sum(1 for _,e in yaml_changes if e.get('final_layer')=='L3')}")
    print(f"  备份目标: {BACKUP.relative_to(ROOT)}/<utc-timestamp>/")

    if args.apply and args.confirmed and not issues:
        print("\n--- 真实写回 ---")
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snap = BACKUP / ts
        snap.mkdir(parents=True, exist_ok=True)

        # 1) 备份
        if SU_MAIN.exists():
            shutil.copy2(SU_MAIN, snap / "source_unit_adjudication.csv")
        if SU_W11.exists():
            shutil.copy2(SU_W11, snap / "source_unit_adjudication_w11.csv")
        if PK_REG.exists():
            shutil.copy2(PK_REG, snap / "pack_layer_register.csv")
        if COV.exists():
            shutil.copy2(COV, snap / "coverage_status.json")
        for sub in ("domain_general", "brand_faye", "needs_review"):
            d = CAND / sub
            if d.exists():
                tgt = snap / f"candidates_{sub}"
                tgt.mkdir(parents=True, exist_ok=True)
                for y in d.glob("*.yaml"):
                    shutil.copy2(y, tgt / y.name)
        print(f"  ✅ 备份完成: {snap.relative_to(ROOT)}")

        # 2) 写 W11 主表 source_unit_adjudication_w11.csv（独立文件，full_audit 不覆盖）
        keep_cols = ["source_md", "heading_path", "heading_level", "body_length",
                     "body_hash", "adjudication_status", "sub_reason", "adjudicator",
                     "priority", "w10_rationale", "batch_target",
                     "suggested_layer", "suggested_status", "confidence",
                     "suggestion_rationale", "needs_human_review",
                     "reviewer_decision", "final_layer", "final_status",
                     "merge_target", "production_tier", "default_call_pool", "review_notes"]
        with SU_W11.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keep_cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"  ✅ source_unit_adjudication_w11.csv 已写入（{len(rows)} 行 / {len(keep_cols)} 列）")
        print(f"     注: source_unit_adjudication.csv 保持 W10 4 态（G16d 维护，向后兼容）")

        # 3) 写 pack_layer_register.csv
        pcols = ["pack_id", "brand_layer_dir",
                 "suggested_layer", "confidence", "suggestion_rationale",
                 "needs_human_review", "reviewer_decision", "final_layer",
                 "production_tier", "default_call_pool", "review_notes"]
        with PK_REG.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=pcols, extrasaction="ignore")
            w.writeheader()
            w.writerows(pack_rows)
        print(f"  ✅ pack_layer_register.csv 升级为 W11 版（{len(pack_rows)} 行）")

        # 4) yaml 注入 granularity_layer + production 块
        injected = 0
        for ypath, entry in yaml_changes:
            text = ypath.read_text(encoding="utf-8")
            layer = entry.get("final_layer", "").strip()
            if not layer:
                continue
            # 幂等：若已含 granularity_layer，跳过 layer 行写入
            if "granularity_layer:" not in text:
                # 在文件首行（或 pack_id 行后）插入
                lines = text.splitlines()
                inject_idx = 0
                for i, l in enumerate(lines[:5]):
                    if l.startswith("pack_id:"):
                        inject_idx = i + 1
                        break
                lines.insert(inject_idx, f"granularity_layer: {layer}")
                if layer == "L2":
                    tier = entry.get("production_tier", "").strip()
                    pool = entry.get("default_call_pool", "").strip()
                    if tier:
                        lines.insert(inject_idx + 1, f"production_tier: {tier}")
                    if pool:
                        lines.insert(inject_idx + 2, f"default_call_pool: {pool}")
                ypath.write_text("\n".join(lines) + "\n", encoding="utf-8")
                injected += 1
        print(f"  ✅ yaml 注入 granularity_layer: {injected} 个")

        # 5) coverage_status.json 新增 layer_distribution
        if COV.exists():
            cov = json.loads(COV.read_text(encoding="utf-8"))
            from collections import Counter as _C
            su_dist = _C(r["final_status"] for r in rows)
            pk_dist = _C(r.get("final_layer", "") for r in pack_rows)
            biz_total = cov.get("knowledge_point_coverage", {}).get("business_total", 1148)
            cov["layer_distribution"] = {
                "source_unit_final_status": dict(su_dist),
                "pack_final_layer": dict(pk_dist),
                "business_total": biz_total,
                "l1_pct": round(su_dist.get("extract_l1", 0) * 100 / max(biz_total, 1), 1),
                "l2_pct": round(su_dist.get("extract_l2", 0) * 100 / max(biz_total, 1), 1),
                "l3_pct": round(su_dist.get("defer_l3_to_runtime_asset", 0) * 100 / max(biz_total, 1), 1),
            }
            COV.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ✅ coverage_status.json 新增 layer_distribution")

        print(f"\n  ✅ 写回完成。请重跑 full_audit 验证 24 道硬门不回退。")
        return 0

    if args.apply and issues:
        print("\n❌ 有 G19 契约违规，拒绝写回。请先修 v2 表后再 --apply --confirmed")
        return 1

    print(f"\n💡 当前是 dry-run；如需真实写回，等审完后跑 --apply --confirmed")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
