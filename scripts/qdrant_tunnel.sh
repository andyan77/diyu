#!/usr/bin/env bash
# qdrant_tunnel.sh · 本地访问 ECS 上的 Qdrant / local access to ECS Qdrant
# ============================================================
# 用途 / usage:
#   Qdrant 容器仅监听 ECS 上的 127.0.0.1:6333（不对外）
#   本脚本启动 SSH 隧道，让本机 127.0.0.1:6333 转发到 ECS 上的 127.0.0.1:6333
# ============================================================
# 用法 / usage:
#   bash scripts/qdrant_tunnel.sh up      # 起隧道
#   bash scripts/qdrant_tunnel.sh down    # 关隧道
#   bash scripts/qdrant_tunnel.sh status  # 看状态
# ============================================================

set -e
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; source .env; set +a

LOCAL_PORT=6333
REMOTE_PORT=6333
PID_FILE="/tmp/qdrant_tunnel.pid"

case "${1:-status}" in
  up)
    # 已在跑 / already running：复用，不重起
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "⚠️  隧道已在跑 / already running (pid $(cat $PID_FILE))"
      exit 0
    fi
    # 端口自检 / port pre-check：若 6333 已被别人占用（残留 ssh / 别的服务），先报错不要盲起
    if command -v ss >/dev/null 2>&1 && ss -lnt | awk '{print $4}' | grep -qE "[:.]${LOCAL_PORT}\$"; then
      echo "❌ 本机端口已被占用 / port ${LOCAL_PORT} already bound by another process; 先 \`bash scripts/qdrant_tunnel.sh down\` 或 lsof -i :${LOCAL_PORT} 排查"
      ss -lnt | awk -v p=":${LOCAL_PORT}\$" '$4 ~ p {print "  occupant:", $0}'
      exit 1
    fi
    # 起 + 最多 retry 一次（IPv6 双栈 / 残留 socket / WSL2 网络栈瞬时抖动）
    attempt_tunnel() {
      ssh -i "$ECS_SSH_KEY_PATH" -N -L "127.0.0.1:${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
          -o ExitOnForwardFailure=yes -o ServerAliveInterval=60 \
          -o AddressFamily=inet \
          "$ECS_USER@$ECS_HOST" &
      TUNNEL_PID=$!
      sleep 2
      if kill -0 "$TUNNEL_PID" 2>/dev/null \
         && curl -sS -m 3 -o /dev/null "http://127.0.0.1:${LOCAL_PORT}/readyz"; then
        echo "$TUNNEL_PID" > "$PID_FILE"
        return 0
      fi
      kill "$TUNNEL_PID" 2>/dev/null || true
      return 1
    }
    echo "起隧道 / starting tunnel: 127.0.0.1:${LOCAL_PORT} → ${ECS_USER}@${ECS_HOST}:${REMOTE_PORT}"
    if attempt_tunnel; then
      echo "✅ 隧道已起 / tunnel up (pid $(cat "$PID_FILE")) + readyz HTTP 200"
    else
      echo "⚠️  首次起失败，重试一次 / first attempt failed, retrying once …"
      sleep 1
      if attempt_tunnel; then
        echo "✅ 隧道已起（重试成功）/ tunnel up after retry (pid $(cat "$PID_FILE"))"
      else
        echo "❌ 隧道起失败（已重试 1 次）/ tunnel failed after 1 retry"
        rm -f "$PID_FILE"
        exit 1
      fi
    fi
    ;;
  down)
    KILLED=()
    # 先关 PID_FILE 记录的 / kill tracked tunnel
    if [[ -f "$PID_FILE" ]]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" && KILLED+=("$PID")
      fi
      rm -f "$PID_FILE"
    fi
    # 再清孤儿 / reap orphan ssh tunnels matching this forward
    # （-f daemon 化或上一次 PID_FILE 丢失留下的，占着 6333 但 down 不知道）
    ORPHANS=$(pgrep -af "ssh.*-L[ ]*[^ ]*${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}.*${ECS_HOST}" | awk '{print $1}')
    for pid in $ORPHANS; do
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" && KILLED+=("$pid (orphan)")
      fi
    done
    if [[ ${#KILLED[@]} -gt 0 ]]; then
      echo "✅ 隧道已关 / tunnel down: ${KILLED[*]}"
    else
      echo "⏭️  隧道未运行 / tunnel not running"
    fi
    ;;
  status)
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "✅ running (pid $(cat $PID_FILE))"
      curl -sS -m 3 -w "  readyz: HTTP %{http_code}\n" "http://localhost:${LOCAL_PORT}/readyz" || echo "  readyz: unreachable"
    else
      echo "⏭️  not running"
      rm -f "$PID_FILE" 2>/dev/null
    fi
    ;;
  *)
    echo "用法 / usage: $0 {up|down|status}"
    exit 1
    ;;
esac
