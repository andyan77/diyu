#!/usr/bin/env bash
# KS-COMPILER-012 · lint_no_duplicate_log.sh
#
# context_bundle_log 唯一写入守门 / single-canonical-write guard for §4.5 context_bundle_log.
# 全仓 find context_bundle_log.csv 必须只命中
#   knowledge_serving/control/context_bundle_log.csv
# 同时校验 header == 28 字段（control_tables.schema.json $defs/context_bundle_log/required）。
#
# 退出码 / exit:
#   0  唯一 canonical + header 合规
#   1  发现重复同名 csv 或 header 不合规
#   2  fail-closed（脚本内部异常）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CANONICAL_REL="knowledge_serving/control/context_bundle_log.csv"
CANONICAL_ABS="${ROOT}/${CANONICAL_REL}"

REQUIRED_HEADER='request_id,tenant_id,resolved_brand_layer,allowed_layers,user_query_hash,classified_intent,content_type,selected_recipe_id,retrieved_pack_ids,retrieved_play_card_ids,retrieved_asset_ids,retrieved_overlay_ids,retrieved_evidence_ids,fallback_status,missing_fields,blocked_reason,context_bundle_hash,final_output_hash,compile_run_id,source_manifest_hash,view_schema_version,embedding_model,embedding_model_version,rerank_model,rerank_model_version,llm_assist_model,model_policy_version,created_at'

errors=0

# 1) 全仓搜同名 csv，必须只命中 control/ 路径
mapfile -t hits < <(find "${ROOT}/knowledge_serving" -type f -name context_bundle_log.csv | sort)
if [[ "${#hits[@]}" -eq 0 ]]; then
    echo "[FAIL] 缺 canonical / canonical missing: ${CANONICAL_REL}" >&2
    errors=$((errors + 1))
elif [[ "${#hits[@]}" -gt 1 ]]; then
    echo "[FAIL] 发现重复 context_bundle_log.csv（必须只 1 个 canonical）:" >&2
    for h in "${hits[@]}"; do echo "  - $h" >&2; done
    errors=$((errors + 1))
elif [[ "${hits[0]}" != "${CANONICAL_ABS}" ]]; then
    echo "[FAIL] context_bundle_log.csv 不在 canonical 路径 / not at canonical path:" >&2
    echo "       got:      ${hits[0]}" >&2
    echo "       expected: ${CANONICAL_ABS}" >&2
    errors=$((errors + 1))
fi

# 2) header 校验（仅当 canonical 存在）
if [[ -f "${CANONICAL_ABS}" ]]; then
    actual_header="$(head -n 1 "${CANONICAL_ABS}" | tr -d '\r')"
    if [[ "${actual_header}" != "${REQUIRED_HEADER}" ]]; then
        echo "[FAIL] header 与 schema 不匹配 / header mismatch:" >&2
        echo "       actual:   ${actual_header}" >&2
        echo "       required: ${REQUIRED_HEADER}" >&2
        errors=$((errors + 1))
    fi
    # header 后必须无数据行（落盘只允许 header）
    body_lines="$(tail -n +2 "${CANONICAL_ABS}" | sed '/^$/d' | wc -l | tr -d ' ')"
    if [[ "${body_lines}" -ne 0 ]]; then
        echo "[FAIL] canonical 必须只含 header，发现 ${body_lines} 行数据 / header-only required" >&2
        errors=$((errors + 1))
    fi
fi

if [[ "${errors}" -eq 0 ]]; then
    echo "[OK] context_bundle_log 单 canonical 守门通过"
    echo "     path: ${CANONICAL_REL}"
    echo "     header 字段数: 28"
    exit 0
fi
echo "[FAIL] context_bundle_log 守门 ${errors} 项失败" >&2
exit 1
