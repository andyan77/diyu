#!/usr/bin/env bash
# check_no_secrets.sh · KS-S0-003 CI 门禁 / CI gate
# 扫描 git 追踪文件中是否有明文 API key / scan tracked files for plaintext keys
# 用法 / usage: bash scripts/check_no_secrets.sh
# 退出码 / exit: 0 干净 / 1 命中 / 2 工具错

set -e

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "=== check_no_secrets · 扫描追踪文件中的明文密钥 / scan tracked files ==="

# 1. .env 是否被追踪 / is .env tracked?
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "🚨 .env 已被 git 跟踪 / .env is tracked! 立即 git rm --cached .env"
  exit 1
fi
echo "✅ .env 未被追踪 / not tracked"

# 2. 扫描所有追踪文件 / scan all tracked files
# 模式 / patterns:
#   - sk-[0-9a-f]{32}   DeepSeek / QWEN 风格
#   - sk-[A-Za-z0-9]{32,}   OpenAI / 通用风格
#   - "password\s*[:=]\s*['\"][^'\"]+['\"]"   密码硬编码
HITS=$(git ls-files | xargs -I {} grep -lEn "sk-[A-Za-z0-9]{20,}|password\s*[:=]\s*['\"][^'\"\$\{]+['\"]" {} 2>/dev/null || true)

# 排除 / exclude: 文档中讨论密钥模式但无明文（含 sk-... 占位的不算）
FILTERED=""
if [[ -n "$HITS" ]]; then
  while IFS= read -r f; do
    # 跳过 .env.example / docs / task_cards / .md 中的纯讨论
    if echo "$f" | grep -qE "\.env\.example$|task_cards/|knowledge_serving_plan|README\.md$"; then
      continue
    fi
    # 真实长 hex key 模式
    if grep -qE "sk-[0-9a-f]{32}|sk-[A-Za-z0-9]{40,}" "$f" 2>/dev/null; then
      FILTERED="${FILTERED}${f}\n"
    fi
  done <<< "$HITS"
fi

if [[ -n "$FILTERED" ]]; then
  echo "🚨 发现明文密钥 / plaintext key found:"
  echo -e "$FILTERED"
  exit 1
fi

echo "✅ 追踪文件中无明文密钥 / no plaintext keys in tracked files"
echo ""
echo "=== 全部检查通过 / all checks passed ==="
exit 0
