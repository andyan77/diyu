"""
KS-POLICY-001 · validate_policy_yaml.py 测试套件 / test suite

覆盖 / coverage:
  - real fallback_policy.yaml happy path（baseline 必须 pass）
  - F2 缺状态 / F2 多余状态
  - F3 状态重名
  - F4 阻断状态缺 block_reason
  - F5 trigger 注入 LLM 关键词（多 keyword 变体）
  - F5 no_llm_in_decision 关闭
  - F6 matrix_alignment 字段缺失 / source 路径不存在
  - F7 evaluation_pipeline 引用非法 state
  - F1 yaml 语法错（顶层非 mapping / 解析失败）
  - 未知 policy 名字 → exit 2
  - 缺文件 → exit 1

共 ≥ 14 case。直接 import + 注入 POLICY_REGISTRY，避免污染真路径。
"""
from __future__ import annotations

import copy
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "validate_policy_yaml.py"
REAL_YAML = REPO_ROOT / "knowledge_serving" / "policies" / "fallback_policy.yaml"


def _load_mod():
    spec = importlib.util.spec_from_file_location("validate_policy_yaml", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_mod()


@pytest.fixture
def real_yaml_obj():
    with REAL_YAML.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _stage(tmp_path: Path, obj) -> Path:
    p = tmp_path / "fallback_policy.yaml"
    p.write_text(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def _run(mod, registry_path: Path, name: str = "fallback_policy") -> int:
    mod.POLICY_REGISTRY[name] = registry_path
    return mod.main(["validate_policy_yaml.py", name])


# ---------- baseline ----------

def test_baseline_real_yaml_passes(mod):
    """真实落盘 yaml 必须 pass（防 E2 假绿：先确认 happy path 绿，mutation 才有意义）"""
    rc = mod.main(["validate_policy_yaml.py", "fallback_policy"])
    assert rc == 0


# ---------- F2 五状态枚举 ----------

def test_F2_missing_state_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    obj["states"] = [s for s in obj["states"] if s["name"] != "domain_only"]
    assert _run(mod, _stage(tmp_path, obj)) == 1


def test_F2_extra_unknown_state_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    obj["states"].append({
        "name": "rogue_state",
        "is_blocking": False,
        "trigger": {"x": "y"},
    })
    assert _run(mod, _stage(tmp_path, obj)) == 1


# ---------- F3 重名 ----------

def test_F3_duplicate_state_name_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    obj["states"].append(copy.deepcopy(obj["states"][0]))
    assert _run(mod, _stage(tmp_path, obj)) == 1


# ---------- F4 阻断状态 block_reason ----------

def test_F4_blocking_state_missing_block_reason_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    for s in obj["states"]:
        if s["name"] == "blocked_missing_business_brief":
            s.pop("block_reason", None)
    assert _run(mod, _stage(tmp_path, obj)) == 1


# ---------- F5 LLM 关键词扫描 ----------

@pytest.mark.parametrize("payload", [
    {"decision_by": "llm_judge"},
    {"source": "openai_completion"},
    {"resolver": "anthropic"},
    {"intent_predict": "gpt-4o"},
    {"strategy": "ask_llm_for_classification"},
])
def test_F5_llm_keyword_in_trigger_fails(mod, real_yaml_obj, tmp_path, payload):
    obj = copy.deepcopy(real_yaml_obj)
    obj["states"][0]["trigger"] = payload
    assert _run(mod, _stage(tmp_path, obj)) == 1


def test_F5_no_llm_flag_off_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    obj["no_llm_in_decision"] = False
    assert _run(mod, _stage(tmp_path, obj)) == 1


def test_F5_no_llm_flag_missing_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    obj.pop("no_llm_in_decision", None)
    assert _run(mod, _stage(tmp_path, obj)) == 1


# ---------- F6 matrix_alignment ----------

def test_F6_missing_matrix_alignment_key_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    obj["matrix_alignment"].pop("hard_missing_to_state")
    assert _run(mod, _stage(tmp_path, obj)) == 1


def test_F6_matrix_alignment_source_not_found_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    obj["matrix_alignment"]["source"] = "knowledge_serving/control/does_not_exist.csv"
    assert _run(mod, _stage(tmp_path, obj)) == 1


# ---------- F7 evaluation_pipeline 闭合 ----------

def test_F7_pipeline_references_unknown_state_fails(mod, real_yaml_obj, tmp_path):
    obj = copy.deepcopy(real_yaml_obj)
    obj["evaluation_pipeline"][0]["on_missing"] = "ghost_state"
    assert _run(mod, _stage(tmp_path, obj)) == 1


# ---------- F1b yamllint ----------

def test_F1b_yamllint_violation_fails(mod, real_yaml_obj, tmp_path):
    """注入 trailing space + tab 缩进，yamllint 必拒；validator 必返回 1。"""
    p = tmp_path / "fallback_policy.yaml"
    # 故意写一个 lint 不通过的样本（trailing space + 不合法缩进 + 末尾无换行）
    bad_text = (
        "policy_id: fallback_policy_v1   \n"   # trailing whitespace
        "states:\n"
        "\t- name: brand_full_applied\n"        # tab 缩进
        "no_llm_in_decision: true"              # no newline at end of file
    )
    p.write_text(bad_text, encoding="utf-8")
    assert _run(mod, p) == 1


# ---------- F1 yaml 解析 ----------

def test_F1_top_level_not_mapping_fails(mod, tmp_path):
    p = tmp_path / "fallback_policy.yaml"
    p.write_text("- just\n- a\n- list\n", encoding="utf-8")
    assert _run(mod, p) == 1


def test_F1_yaml_syntax_error_fails(mod, tmp_path):
    p = tmp_path / "fallback_policy.yaml"
    p.write_text("states: [\n  - name: x\n  bad_indent\n", encoding="utf-8")
    assert _run(mod, p) == 1


# ---------- CLI 边界 ----------

def test_unknown_policy_name_exit_2(mod):
    assert mod.main(["validate_policy_yaml.py", "nonexistent_policy"]) == 2


def test_missing_file_exit_1(mod, tmp_path):
    ghost = tmp_path / "ghost.yaml"
    # 不创建文件
    assert _run(mod, ghost) == 1


def test_no_args_exit_2(mod):
    assert mod.main(["validate_policy_yaml.py"]) == 2


# ---------- 反 LLM 源码硬扫 ----------

def test_validator_source_no_llm_call():
    """validator 自身不许 import / 调用 LLM SDK（R2 红线）"""
    src = SCRIPT.read_text(encoding="utf-8").lower()
    for forbidden in ["import anthropic", "import openai", "from anthropic", "from openai"]:
        assert forbidden not in src, f"validator 含 LLM SDK 调用 / contains LLM SDK: {forbidden}"
