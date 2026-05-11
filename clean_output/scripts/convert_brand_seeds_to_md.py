#!/usr/bin/env python3
"""W13.A.3 · 把 7 份笛语 brand JSON 转为 markdown，落到 Q-brand-seeds/

目标:
  - 保留全部字段（不丢知识）
  - 顶层字段 → H2，嵌套对象 → H3，列表项 → bullet
  - 加 frontmatter 标记 source_workspace（W13.A 跨工作区引入护栏）
  - 输出文件名与 entity_id 对齐
"""
import json
from pathlib import Path

SRC = Path("/home/faye/dev/diyu-infra-05/data/mvp/seeds")
DST = Path("/home/faye/20-血肉-2F种子/Q-brand-seeds")

BRAND_FILES = [
    SRC / "brand_tone" / "brandtone_diyu_001.json",
    SRC / "persona" / "persona_founder_demo.json",
    SRC / "persona" / "persona_franchise_owner_demo.json",
    SRC / "persona" / "persona_sample_maker_demo.json",
    SRC / "content_type" / "ctype_founder_ip.json",
    SRC / "content_type" / "ctype_process_trace.json",
    SRC / "content_type" / "ctype_store_daily.json",
]


def render_value(v, level=0):
    """把 JSON 值递归渲染为 markdown 文本"""
    indent = "  " * level
    if isinstance(v, str):
        # 多行字符串原样输出
        return v
    if isinstance(v, (int, float, bool)) or v is None:
        return str(v)
    if isinstance(v, list):
        out = []
        for item in v:
            if isinstance(item, dict):
                # 列表里嵌字典：每个字典作子节
                out.append("")
                for k2, v2 in item.items():
                    out.append(f"{indent}- **{k2}**: {render_value(v2, level+1) if not isinstance(v2, (dict, list)) else ''}")
                    if isinstance(v2, dict):
                        for k3, v3 in v2.items():
                            out.append(f"{indent}    - {k3}: {render_value(v3, level+2)}")
                    elif isinstance(v2, list):
                        for it in v2:
                            out.append(f"{indent}    - {render_value(it, level+2)}")
            else:
                out.append(f"{indent}- {render_value(item, level+1)}")
        return "\n".join(out)
    if isinstance(v, dict):
        out = [""]
        for k, val in v.items():
            if isinstance(val, (dict, list)):
                out.append(f"{indent}- **{k}**:")
                rendered = render_value(val, level+1)
                if isinstance(val, dict):
                    out.append(rendered)
                else:
                    out.append(rendered)
            else:
                out.append(f"{indent}- **{k}**: {render_value(val, level+1)}")
        return "\n".join(out)
    return str(v)


def json_to_md(data: dict, src_path: Path) -> str:
    """整文件渲染：顶层字段 → H2"""
    eid = data.get("entity_id", src_path.stem)
    etype = data.get("entity_type", "?")
    display = data.get("display_name") or data.get("brand_name") or eid

    lines = []
    # frontmatter（来源标记 + reviewer 元信息，便于反查）
    lines.append("---")
    lines.append(f"source_workspace: diyu-infra-05/data/mvp/seeds")
    lines.append(f"source_path: {src_path.relative_to(SRC.parent.parent.parent.parent)}")
    lines.append(f"entity_id: {eid}")
    lines.append(f"entity_type: {etype}")
    lines.append(f"visibility: {data.get('visibility', 'unknown')}")
    lines.append(f"brand_id: {data.get('brand_id', 'diyu_001')}")
    lines.append(f"imported_at: 2026-05-04")
    lines.append(f"import_decision: clean_output/audit/_process/cross_workspace_import_decision.md")
    lines.append("---")
    lines.append("")
    # 标题
    lines.append(f"# {display}")
    lines.append("")
    lines.append(f"> entity_id: `{eid}` · entity_type: `{etype}` · visibility: `brand`")
    lines.append("")

    # 顶层字段全部展开
    skip_top = {"entity_id", "entity_type", "visibility", "industry_scope"}
    for key, val in data.items():
        if key in skip_top:
            continue
        lines.append(f"## {key}")
        lines.append("")
        if isinstance(val, str):
            lines.append(val)
        elif isinstance(val, (int, float, bool)) or val is None:
            lines.append(str(val))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    lines.append("")
                    for k2, v2 in item.items():
                        if isinstance(v2, list):
                            lines.append(f"- **{k2}**:")
                            for it in v2:
                                lines.append(f"    - {it}")
                        elif isinstance(v2, dict):
                            lines.append(f"- **{k2}**:")
                            for k3, v3 in v2.items():
                                lines.append(f"    - {k3}: {v3}")
                        else:
                            lines.append(f"- **{k2}**: {v2}")
                else:
                    lines.append(f"- {item}")
        elif isinstance(val, dict):
            for k2, v2 in val.items():
                if isinstance(v2, list):
                    lines.append(f"### {k2}")
                    lines.append("")
                    for it in v2:
                        if isinstance(it, dict):
                            lines.append("")
                            for k3, v3 in it.items():
                                lines.append(f"- **{k3}**: {v3}")
                        else:
                            lines.append(f"- {it}")
                    lines.append("")
                elif isinstance(v2, dict):
                    lines.append(f"### {k2}")
                    lines.append("")
                    for k3, v3 in v2.items():
                        lines.append(f"- **{k3}**: {v3}")
                    lines.append("")
                else:
                    lines.append(f"- **{k2}**: {v2}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    DST.mkdir(parents=True, exist_ok=True)
    for src in BRAND_FILES:
        data = json.loads(src.read_text(encoding="utf-8"))
        md = json_to_md(data, src)
        out = DST / f"{src.stem}.md"
        out.write_text(md, encoding="utf-8")
        print(f"  ✅ {src.name} → {out.relative_to(DST.parent)}  ({len(md)} chars)")
    print(f"\n总计 {len(BRAND_FILES)} 份转换完成 → {DST}")


if __name__ == "__main__":
    main()
