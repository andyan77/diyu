# 纠正日志 / Corrections Log

> 仅记录**已 commit 文字**的事实纠正；对应的代码 / artifact 已是对的，本日志只对齐文字记忆。

---

## 2026-05-15 · canonical content_type 数量 17 → 18

**纠正对象**：
- commit `4240cdd` message：`fix(KS-CD-003 DSL iter-2): n3 全 17 canonical content_type + n7b/n10a 防御性解码`
- 该 commit message + 同期会话叙述中多处提及 "17 canonical content_type"

**真值**：**18** 个 canonical content_type

**真源 / source of truth**：
- `knowledge_serving/control/content_type_canonical.csv` — 18 行 data（19 行含表头）
- `knowledge_serving/views/content_type_view.csv` — 18 个 unique `canonical_content_type_id`

**18 类清单**（按字母序）：
```
behind_the_scenes   daily_fragment        emotion_expression
event_documentary   founder_ip            humor_content
knowledge_sharing   lifestyle_expression  outfit_of_the_day
personal_vlog       process_trace         product_copy_general
product_journey     product_review        role_work_vlog
store_daily         talent_showcase       training_material
```

**实现侧无误**：`dify/chatflow_dify_cloud.yml` n3_content_type_canonical_map 节点实际**已覆盖全部 18 类**（2026-05-15 grep 校核通过）；仅 commit message 与 README 描述写成 17。

**影响**：仅 commit message 文字与口头叙述；代码 / DSL / artifact 均无需修改。

**取证命令**（任意未来时间可复跑）：
```bash
# 真源 18
wc -l knowledge_serving/control/content_type_canonical.csv  # → 19（含表头）
cut -d, -f1 knowledge_serving/control/content_type_canonical.csv | tail -n +2 | sort -u | wc -l  # → 18

# chatflow 实际覆盖 18
grep -oE "(outfit_of_the_day|founder_ip|behind_the_scenes|daily_fragment|emotion_expression|event_documentary|humor_content|knowledge_sharing|lifestyle_expression|personal_vlog|process_trace|product_copy_general|product_journey|product_review|role_work_vlog|store_daily|talent_showcase|training_material)" dify/chatflow_dify_cloud.yml | sort -u | wc -l  # → 18
```
