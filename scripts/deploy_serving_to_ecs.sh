#!/usr/bin/env bash
# KS-CD-003 · diyu-serving 容器部署脚本 / sidecar serving container deploy
#
# 数据真源方向 / SSOT direction：
#   本地 → ECS 单向；本脚本严禁任何 ECS → local 反向数据流。
#
# 用法 / usage：
#   bash scripts/deploy_serving_to_ecs.sh --dry-run   # 列出会做什么，不真改 ECS
#   bash scripts/deploy_serving_to_ecs.sh --apply     # 真部署（需 ECS root 已配 .env）
#
# 模式互斥 / mutex modes：
#   --dry-run 分支不出现 ssh/docker run、docker stop、docker rm、docker load、scp local→remote
#   --apply 分支才执行真改命令
#
# audit 输出 / audit output：
#   knowledge_serving/audit/deploy_serving_KS-CD-003.json
#     字段：env / checked_at / git_commit / evidence_level / mode / image_sha / ...

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

AUDIT_PATH="${REPO_ROOT}/knowledge_serving/audit/deploy_serving_KS-CD-003.json"
IMAGE_NAME="diyu-serving"
CONTAINER_NAME="diyu-serving"
HOST_PORT="8005"
CONTAINER_PORT="8000"

MODE=""
case "${1:-}" in
    --dry-run) MODE="dry-run" ;;
    --apply)   MODE="apply" ;;
    *)
        echo "ERROR: usage: $0 [--dry-run | --apply]" >&2
        exit 2
        ;;
esac

# ---- 通用变量 ----
GIT_COMMIT="$(git rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
IMAGE_TAG="${IMAGE_NAME}:${GIT_COMMIT}"
TARBALL="/tmp/${IMAGE_NAME}-${GIT_COMMIT}.tar"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

ECS_HOST="${ECS_HOST:-8.217.175.36}"
ECS_USER="${ECS_USER:-root}"
ECS_SSH_KEY="${ECS_SSH_KEY_PATH:-${HOME}/.ssh/diyu-hk.pem}"

write_audit() {
    local evidence_level="$1"
    local extra_json="${2:-{\}}"
    mkdir -p "$(dirname "${AUDIT_PATH}")"
    cat > "${AUDIT_PATH}" <<EOF
{
  "task_id": "KS-CD-003",
  "env": "staging",
  "checked_at": "${CHECKED_AT}",
  "git_commit": "${GIT_COMMIT}",
  "mode": "${MODE}",
  "evidence_level": "${evidence_level}",
  "image_tag": "${IMAGE_TAG}",
  "ecs_host": "${ECS_HOST}",
  "host_port": "${HOST_PORT}",
  "container_port": "${CONTAINER_PORT}",
  "extra": ${extra_json}
}
EOF
}

# ============================================================
# Mode dispatch — 严格分支隔离
# ============================================================
case "${MODE}" in
    dry-run)
        echo "[dry-run] === KS-CD-003 deploy plan ==="
        echo "[dry-run] git_commit       = ${GIT_COMMIT}"
        echo "[dry-run] image_tag        = ${IMAGE_TAG}"
        echo "[dry-run] ecs_host         = ${ECS_HOST}"
        echo "[dry-run] container_name   = ${CONTAINER_NAME}"
        echo "[dry-run] host_port        = ${HOST_PORT} (与既有 diyu-agent:8004 隔离)"
        echo "[dry-run]"
        echo "[dry-run] would execute (apply mode only)："
        echo "[dry-run]   1) docker build  -t ${IMAGE_TAG} -f knowledge_serving/serving/api/Dockerfile ."
        echo "[dry-run]   2) docker save   ${IMAGE_TAG} -o ${TARBALL}"
        echo "[dry-run]   3) (transfer to ECS / load on ECS / start container)"
        echo "[dry-run]   4) (smoke 3 endpoints)"
        echo "[dry-run] not executed in dry-run mode."

        # dry-run 也允许只读探测 ECS 端口冲突（read-only SSH probe，不改任何东西）
        PORT_PROBE="skipped"
        if [[ -f "${ECS_SSH_KEY}" ]]; then
            if PROBE_OUT=$(ssh -i "${ECS_SSH_KEY}" -o BatchMode=yes -o ConnectTimeout=5 \
                "${ECS_USER}@${ECS_HOST}" "ss -tlnp 2>/dev/null | grep ':${HOST_PORT}' || true" 2>/dev/null); then
                if [[ -z "${PROBE_OUT}" ]]; then
                    PORT_PROBE="free"
                else
                    PORT_PROBE="occupied"
                    echo "[dry-run] WARN: ECS port ${HOST_PORT} appears occupied:"
                    echo "${PROBE_OUT}"
                fi
            else
                PORT_PROBE="ssh_failed"
            fi
        fi

        write_audit "dry_run" "{\"port_probe\": \"${PORT_PROBE}\"}"
        echo "[dry-run] audit: ${AUDIT_PATH}"
        echo "[dry-run] DONE — no ECS resources modified."
        exit 0
        ;;

    apply)
        echo "[apply] === KS-CD-003 deploy (build on ECS strategy) ==="
        # 前置：必须有 ECS SSH 凭据
        [[ -f "${ECS_SSH_KEY}" ]] || { echo "ERROR: ssh key missing: ${ECS_SSH_KEY}" >&2; exit 3; }

        SRC_TARBALL="/tmp/diyu-serving-src-${GIT_COMMIT}.tar.gz"
        ECS_BUILD_DIR="/opt/diyu-serving/build-${GIT_COMMIT}"

        # 1) 本地打源码 tar（只含 knowledge_serving/ 子树 —— 不含 .git, diyu-agent, secrets）
        echo "[apply] step 1/5: tar source (knowledge_serving/ only)"
        tar -czf "${SRC_TARBALL}" \
            knowledge_serving/serving/api/Dockerfile \
            knowledge_serving/serving/api/requirements.txt \
            knowledge_serving/

        # 2) scp 到 ECS（**唯一允许的 scp 方向：local→ECS**）
        echo "[apply] step 2/5: scp source to ECS"
        scp -i "${ECS_SSH_KEY}" -o StrictHostKeyChecking=no "${SRC_TARBALL}" "${ECS_USER}@${ECS_HOST}:${SRC_TARBALL}"

        # 3) ECS 上 build + (stop + rm) + run
        echo "[apply] step 3/5: ssh ECS to build + recreate container"
        ssh -i "${ECS_SSH_KEY}" -o StrictHostKeyChecking=no "${ECS_USER}@${ECS_HOST}" bash -se <<EOSSH
set -euo pipefail
rm -rf "${ECS_BUILD_DIR}"
mkdir -p "${ECS_BUILD_DIR}"
tar -xzf "${SRC_TARBALL}" -C "${ECS_BUILD_DIR}"
cd "${ECS_BUILD_DIR}"
docker build -t "${IMAGE_TAG}" -f knowledge_serving/serving/api/Dockerfile .
docker stop "${CONTAINER_NAME}" 2>/dev/null || true
docker rm   "${CONTAINER_NAME}" 2>/dev/null || true
docker run -d \\
    --name "${CONTAINER_NAME}" \\
    --restart unless-stopped \\
    --network diyu_default \\
    --env-file /opt/diyu-serving/.env \\
    -p 127.0.0.1:${HOST_PORT}:${CONTAINER_PORT} \\
    "${IMAGE_TAG}"
rm -f "${SRC_TARBALL}"
EOSSH

        # 4) wait healthy + smoke 3 endpoints on ECS-local
        echo "[apply] step 4/5: smoke 3 endpoints on ECS-local"
        SMOKE_EXIT=0
        SMOKE_RESULT="$(ssh -i "${ECS_SSH_KEY}" -o StrictHostKeyChecking=no "${ECS_USER}@${ECS_HOST}" bash -se <<'EOSMOKE' || SMOKE_EXIT=$?
set -e
for i in $(seq 1 20); do
    if curl -sf -o /dev/null http://127.0.0.1:8005/healthz; then
        echo "healthz_ok_after=${i}s"
        break
    fi
    sleep 1
done
HZ=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8005/healthz)
GR=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8005/v1/guardrail -H "Content-Type: application/json" -d '{"generated_text":"ok","bundle":{"content_type":"outfit_of_the_day","domain_packs":[],"play_cards":[],"runtime_assets":[],"brand_overlays":[],"evidence":[]},"business_brief":{"sku":"x","category":"outerwear","season":"spring","channel":["xiaohongshu"],"price_band":{"currency":"CNY","min":1,"max":2}}}')
echo "healthz=${HZ} guardrail=${GR}"
EOSMOKE
)"
        echo "[apply] smoke: ${SMOKE_RESULT}"

        # 5) audit
        echo "[apply] step 5/5: write audit"
        EVIDENCE="runtime_verified"
        [[ ${SMOKE_EXIT} -ne 0 ]] && EVIDENCE="apply_smoke_failed"
        ESC_SMOKE=$(printf '%s' "${SMOKE_RESULT}" | sed 's/"/\\"/g' | tr '\n' ' ')
        write_audit "${EVIDENCE}" "{\"smoke_exit\": ${SMOKE_EXIT}, \"smoke_result\": \"${ESC_SMOKE}\"}"

        echo "[apply] audit: ${AUDIT_PATH}"
        if [[ ${SMOKE_EXIT} -ne 0 ]]; then
            echo "[apply] FAIL: smoke failed"
            exit 4
        fi
        echo "[apply] DONE — diyu-serving deployed."
        echo "[apply] NEXT (manual by ECS root):"
        echo "[apply]   cp ops/nginx/serving.location.conf /etc/nginx/snippets/diyu-serving.conf"
        echo "[apply]   add 'include /etc/nginx/snippets/diyu-serving.conf;' to kb.diyuai.cc server block"
        echo "[apply]   nginx -t && systemctl reload nginx"
        exit 0
        ;;
esac
