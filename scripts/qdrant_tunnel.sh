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
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "⚠️  隧道已在跑 / already running (pid $(cat $PID_FILE))"
      exit 0
    fi
    echo "起隧道 / starting tunnel: localhost:$LOCAL_PORT → $ECS_USER@$ECS_HOST:$REMOTE_PORT"
    ssh -i "$ECS_SSH_KEY_PATH" -N -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
        -o ExitOnForwardFailure=yes -o ServerAliveInterval=60 \
        "$ECS_USER@$ECS_HOST" &
    TUNNEL_PID=$!
    echo "$TUNNEL_PID" > "$PID_FILE"
    sleep 2
    if kill -0 "$TUNNEL_PID" 2>/dev/null; then
      echo "✅ 隧道已起 / tunnel up (pid $TUNNEL_PID)"
      echo "   测试 / test: curl http://localhost:${LOCAL_PORT}/readyz"
    else
      echo "❌ 隧道起失败 / tunnel failed"
      rm -f "$PID_FILE"
      exit 1
    fi
    ;;
  down)
    if [[ -f "$PID_FILE" ]]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "✅ 隧道已关 / tunnel down (pid $PID)"
      fi
      rm -f "$PID_FILE"
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
