#!/usr/bin/env bash
# 加载本地 .env 到当前 shell / load .env into current shell
# 用法 / usage: source scripts/load_env.sh

set -e

ENV_FILE="$(dirname "${BASH_SOURCE[0]}")/../.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ .env not found at $ENV_FILE"
  echo "   先 cp .env.example .env 并填入真值"
  return 1
fi

# 安全：检查 .env 是否在 git 跟踪中（不应该）
if git ls-files --error-unmatch "$ENV_FILE" >/dev/null 2>&1; then
  echo "🚨 SECURITY: .env 已被 git 跟踪！立即 git rm --cached .env 并轮换所有 key"
  return 1
fi

# 加载
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# 自检：必需 key 是否就位
missing=()
[[ -z "${DASHSCOPE_API_KEY:-}" ]] && missing+=("DASHSCOPE_API_KEY")
[[ -z "${DEEPSEEK_API_KEY:-}" ]] && missing+=("DEEPSEEK_API_KEY")

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "⚠️  以下变量未设置 / unset: ${missing[*]}"
else
  echo "✅ env 已加载 / loaded: QWEN + DEEPSEEK keys ready"
fi
