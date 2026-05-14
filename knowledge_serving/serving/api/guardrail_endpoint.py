"""KS-CD-003 · guardrail HTTP wrapper.

只包一层 HTTP，调用既有 `serving/guardrail.py` 纯函数 `check(...)`。
不动 guardrail.py 本体；不接 LLM；不读外部 IO（除 policy yaml）。

红线 / red lines：
  - 不调 LLM
  - policy yaml 缺失 → 5xx，不能静默 200（fail-closed）
  - 输入字段校验由 pydantic 强制
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from knowledge_serving.serving import guardrail as _guardrail_mod

router = APIRouter()


class GuardrailRequest(BaseModel):
    generated_text: str = Field(..., description="LLM 生成文本")
    # KS-CD-003 reimport bug fix：Dify HTTP body 模板在 bundle/brief 为 null/缺失时
    # 会传字面 null；wrapper 应接受并归一为 {}，由 guardrail.check 自行判断
    bundle: Optional[dict[str, Any]] = Field(default=None, description="context_bundle（KS-RETRIEVAL-008 输出）；null→{}")
    business_brief: Optional[dict[str, Any]] = Field(default=None, description="商业 brief；null→{}")


def _policy_path() -> Path:
    """允许测试通过 env 重定向 policy 文件（fail-closed 验证用）。"""
    override = os.environ.get("DIYU_GUARDRAIL_POLICY_OVERRIDE")
    if override:
        return Path(override)
    # 默认 canonical 路径：knowledge_serving/policies/guardrail_policy.yaml
    return Path(__file__).resolve().parents[2] / "policies" / "guardrail_policy.yaml"


@router.post("/v1/guardrail")
def post_guardrail(req: GuardrailRequest) -> dict[str, Any]:
    # 1) policy preflight —— 缺则 5xx fail-closed
    policy_p = _policy_path()
    if not policy_p.exists():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "guardrail_policy_missing",
                "policy_path": str(policy_p),
                "hint": "guardrail_policy.yaml 不可达；fail-closed，不静默通过",
            },
        )

    # 2) 调既有纯函数；若内部 raise → 转 500 + 携带类型，避免静默 200
    try:
        # guardrail._load_policy() 内部读 default 路径；若 override 通过 env，需要
        # 临时把 module-level 路径常量改写。简单做法：直接走 module._load_policy 不传参，
        # 让它读默认路径；override 仅控制 preflight 是否 raise。对正常运行不增加间接层。
        if os.environ.get("DIYU_GUARDRAIL_POLICY_OVERRIDE"):
            # 测试场景：通过 monkeypatching _guardrail_mod 一些常量绕过；此处 preflight 已挡，
            # 走到这里说明 override path 真存在，正常调 check 即可
            pass
        result = _guardrail_mod.check(
            generated_text=req.generated_text,
            bundle=req.bundle or {},
            business_brief=req.business_brief or {},
        )
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail={"error": "bad_input", "message": str(e)})
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "guardrail_policy_missing", "message": str(e)},
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"error": "guardrail_internal", "type": type(e).__name__, "message": str(e)},
        )

    # 3) 直接返回 guardrail.check 的契约 schema
    return {
        "status": result["status"],
        "violations": result["violations"],
    }
