#!/usr/bin/env bash
# run_qdrant_health_check.sh · KS-FIX-01 外审复跑入口 / external review wrapper
# 用途 / purpose:
#   外审 / CI 一键复跑 KS-FIX-01：load env → 起 tunnel → 跑健康检查 → 落 artifact → 关 tunnel
#   fail-closed：任一步失败立即非 0 退出，并尝试清理 tunnel
#
# 用法 / usage:
#   bash knowledge_serving/scripts/run_qdrant_health_check.sh
#
# 产出 / artifact:
#   knowledge_serving/audit/qdrant_health_KS-FIX-01.json
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ARTIFACT="knowledge_serving/audit/qdrant_health_KS-FIX-01.json"
TUNNEL="bash scripts/qdrant_tunnel.sh"

cleanup() {
  local rc=$?
  echo "--- cleanup: tunnel down ---"
  $TUNNEL down || true
  exit $rc
}
trap cleanup EXIT INT TERM

echo "=== KS-FIX-01 staging Qdrant health check ==="

# 1) load env / 注入 staging 环境变量
# shellcheck disable=SC1091
source scripts/load_env.sh

if [ -z "${QDRANT_URL_STAGING:-}" ]; then
  echo "❌ QDRANT_URL_STAGING 未注入 / not injected"
  exit 2
fi

# 2) tunnel up
$TUNNEL up
$TUNNEL status

# 3) 健康检查 / health check (strict + schema gate)
python3 scripts/check_qdrant_health.py \
  --env staging \
  --strict \
  --task-card KS-FIX-01 \
  --out "$ARTIFACT"

echo "✅ KS-FIX-01 health check pass; artifact: $ARTIFACT"
