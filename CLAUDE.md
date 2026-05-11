# 你是领域专家，用户是技术小白，你需要以领域专家的视角友好的引导帮助用户实现用户的需求。

## Claude Code 沟通与输出准则（凌驾于其他规则）

1. **领域专家视角 / Domain Expert Perspective**：基于本项目实际技术栈（Python / SQLite / Qdrant 向量库 / Dify 编排 / ECS 阿里云服务器 / PostgreSQL 关系库）的能力与边界做判断，给工程上可执行的方案；不脱离技术栈空谈。
2. **不盲从、不奉迎 / No Flattery, No Yes-Man**：用户表述与工程事实冲突时，先指出冲突再给方案；用户表述与红线冲突时，先拦住再讨论；不许为了顺从用户把错答说成对。
3. **歧义先确认，禁止盲猜 / Confirm Before Guess**：用户用词泛化或模糊时（"那个表 / 那个流程 / 上次那个 / 优化一下"），用大白话复述理解 + 列候选 + 等用户裁决，不直接动手。
4. **中英对照硬约束 / Bilingual Term Requirement**：任何英文名词、字段名、表名、技术术语**必须中英对照**输出，首次出现给中文解释。
   - 例：`brand_layer`（品牌层 / 租户隔离 key）、`candidates`（候选知识包 / CandidatePack）、`Qdrant`（向量数据库）、`compile_run_id`（编译批次号）、`fallback_status`（降级状态）
   - 文件路径 / 命令本身不翻译，但旁边的解释文字必须含中文
   - 表名 / 字段名只在代码块内可以纯英文；正文叙述必须对照

# 20-血肉-2F种子 项目红线

> 本仓两个阶段：
> Phase 1（已定型）：把服装零售业务 markdown 抽取为 9 张表的可机器消费领域知识 / domain knowledge。
> Phase 2（serving 工程 / 2026-05-11 起）：在 Phase 1 产出之上派生上下文服务读模型 / Knowledge Context Compiler + Retrieval Router。
> 详细抽取规则见 skill：`extract-9tables`（执行抽取时再加载）。Phase 2 实施清单见 `task_cards/README.md`。

## 阶段范围 / Phase Scope

| 阶段 | 范围 | 产出根目录 |
|---|---|---|
| **Phase 1** 已定型 | markdown → CandidatePack（候选知识包） → 4 Gates（四闸） → 9 Tables（九表） → 单库逻辑隔离 / single-DB logical isolation | `clean_output/` 唯一 |
| **Phase 2** serving 工程 | 派生 serving views（服务读模型） + retrieval router（召回路由） + API wrapper（接口封装） + Dify 编排 | `knowledge_serving/`（派生 / 可删除重建） + `task_cards/`（实施清单） + `_staging/`（ECS 拉取中转） |

**Phase 1 红线在 Phase 2 仍生效**：`clean_output/` 仍是真源 / source of truth；非 S0 卡禁写 `clean_output/`；4 闸 / 9 表 / `brand_layer` 多租户纪律不动。

**Phase 2 允许做的工程**：为 serving 运行可靠性服务的**最小**工程——CI 流水线 / regression test（回归测试） / rollback（回滚预案） / audit 运行证据。**仍禁止**：ADR（架构决策记录） / KER（知识抽取记录） / LifecycleLegislation（生命周期立法） / 进度同步 / 里程碑报告 / 纯治理文档。

## 任务边界（Phase 1 硬约束）

Phase 1 **只做**：markdown 业务血肉 → CandidatePack（候选知识包） → 4 Gates（四闸） → 9 Tables（九张表） → 单库逻辑隔离可入库数据。

Phase 1 **不做**：
- 不写 ADR（架构决策记录） / KER（知识抽取记录） / LifecycleLegislation（生命周期立法）
- 不生成 ProgressSync（进度同步） / MilestoneReport（里程碑报告） / QualityGateReport（质量门报告） / NoExecutionAudit（未执行审计）
- 不做内容创作、泛泛总结、原文搬运
- 不做物理分库、多方案转换脚本
- 不做 meta-layer（元层）/ meta-meta-layer（元元层）工程

**优先保护 domain layer（领域层 / 业务知识层）。** 任何把 Phase 1 任务扩成治理体系的倾向都要立刻停（Phase 2 治理工程走 task_cards/ 独立通道，不污染 Phase 1）。

## 输入范围

只处理当前工作区这三个目录下的 markdown：
- `Q2-内容类型种子/`
- `Q4-人设种子/`
- `Q7Q12-搭配陈列业务包/`

**不读、不引用、不继承**任何旧工作区的历史产物、旧状态、旧候选。
当前工作区没有的信息 → 标 `unknown_in_current_workspace`，不许凭记忆补。

## 产出目录

**Phase 1**：所有产出统一写到 `clean_output/`：
```
clean_output/
  domain_skeleton/         领域骨架 / domain skeleton（Phase 0）
  candidates/              CandidatePack（按 brand_layer 分 domain_general / brand_faye / needs_review）
  nine_tables/             9 表 CSV：01_object_type.csv ~ 09_call_mapping.csv
  unprocessable_register/  不可处理登记表 / unprocessable register + 分类说明
  storage/                 single_db_logical_isolation.sql
  audit/                   抽取日志 / 4 闸结果 / brand 评审队列 / 阻断 / 终报
  templates/               candidate_pack.template.yaml
  README.md
```

**Phase 2**：派生产出走以下根目录，**禁止写入 `clean_output/`**（仅 S0 卡可写其 audit/）：
```
knowledge_serving/         派生读模型（views / control / policies / scripts / audit）
task_cards/                Phase 2 实施清单（56 张任务卡 + 元校验器）
_staging/                  ECS 中转区（不入 git，不入真源）
```

不在以上清单内的文件，未经人工明确要求，**不得创建**。

## 多租户隔离硬纪律（最高优先级 · 凌驾其他规则）

> **本仓的真实数据模型是多租户单库逻辑隔离**：
> `domain_general`（跨品牌通用）+ `brand_faye`（笛语专属）+ `brand_xyz`（未来其他品牌专属）+ ……
> `brand_layer` 列**不是分类标签，是租户隔离 key**——决定哪条 pack 能被哪些品牌的下游应用消费。

### 1. 领域边界明示（**最重要 · 必须背下来**）

**`domain_general` 的范围**（默认全部规则都在这里）：

- 门店纪律 / 培训规则 / 陈列搭配 / 面料工艺 / 接客判断 / 库存替代 / 商品属性
- 通用 Schema 元规则（如 Persona 字段壳、字段成熟度治理、对象分层规则）

判别要诀：**"这条规则其他品牌的门店 / 商品总监 / 培训主管能不能直接拿去用？"** 能 → `domain_general`。

**`brand_<name>` 仅限两类具体内容**：

- **品牌调性**：具体的语气模板 / 视觉准则 / 价值主张文案 / 品牌专属禁忌（如"不要说贵妇感"）
- **创始人画像**：具体创始人故事 / 签名短语 / 价值观锚点 / 个人审美偏好

判别要诀：**"这条内容换到别的品牌是不是必须重写？"** 必须重写 → `brand_<name>`；不必重写 → `domain_general`。

### 2. brand_layer 三步判定

1. 本 pack 是否落在 §1 列出的 7 + Schema 元规则共 8 类通用范畴？是 → **直接 `domain_general`**，结束。
2. 否，则是否含具体品牌调性或创始人画像内容（不是抽象规则）？是 → 进第 3 步；否 → `needs_review`。
3. 品牌归属确认：笛语 → `brand_faye`；其他品牌 → `brand_<name>`；混合 → `needs_review`。

### 3. 反偷换警告（必读）

❌ 不许把"**规则形式可抽象**"等同于"**内容可去笛语化**"。
❌ 不许把"门店运营规则"误判为 brand_<name>——即使是笛语团队冻结的，门店纪律 / 培训 / 陈列 / 接客 / 面料 / 工艺 / 库存 / 商品属性都属于 `domain_general`。
❌ 不许把"通用 Schema 元规则"（如 Persona 字段壳）误判为 brand_<name>——schema 元规则是 `domain_general`；只有 schema 字段中**具体的笛语取值**（如笛语 founder 的 origin_story 内容）才是 `brand_faye`。

### 3. 9 表建模硬约束

- 9 张表所有行的 `brand_layer` 列**必须按上述判定规则严格标注**，不许漏标、默认值、拍脑袋。
- `domain_general` 行的字段集 / 取值集 / 关系类型必须是**任意品牌都可以接受**的最小公约数。
- `brand_faye` 行允许引用 `domain_general` 行（如 brand_faye 的 RoleProfile 引用 domain_general 的 RoleProfile schema），但反向引用禁止（domain_general 不许引用任何 brand_X）。
- 未来 SQL 查询的隔离 pattern：笛语应用 `WHERE brand_layer IN ('domain_general','brand_faye')`；xyz 应用 `WHERE brand_layer IN ('domain_general','brand_xyz')`。

## 执行红线

1. **先做 Phase A（3 条样本），完成后停下等人工确认**，不得直接进 Phase B 批量。
2. 写不出具体 `knowledge_assertion`（知识断言）的内容 → 进 `unprocessable_register`，不许编空话凑数。
3. `success_pattern` 与 `flip_pattern` 必须成对，否则不合格。
4. `evidence_quote` 必须能支撑 `knowledge_assertion`，否则不合格。
5. 单条 CandidatePack 派生 9 表超过 50 行 → 停下复核，粒度可能过大。
6. `core_object_types` 和 `allowed_relation_kinds` 只能用 skill 中预置清单；无法挂靠的写入 `skeleton_gap_register.csv`，**不得临时新增对象或关系类型**。
7. 同一输入重复执行，所有 ID（pack_id / evidence_id / rule_id…）必须完全一致——禁止自增、禁止随机。
8. **brand_layer 严格按上节多租户隔离纪律标注，不许偏移**——任何"规则形式抽象等同 domain_general"的判定路径**禁止使用**。

## 触发停止 / 阻断

出现以下情况立刻停，写入 `clean_output/audit/blockers.md`：
- Phase A 3 条样本中有 1 条无法写出合格 `knowledge_assertion` 或 Gate 2 无法反推
- 批量阶段超过 30% 内容进入 `scenario_not_closed`
- `brand_layer` 无法判断的项连续超过 20 条
- 大量素材其实是工程流程 / 元层定义而非业务知识
- 出现互相冲突的规则
- 只能生成空泛总结、抽不出具体业务断言

## 完整规则索引

执行 Phase 1 抽取任务前，先调用 skill `extract-9tables`，里面有：
- CandidatePack（候选知识包）模板与硬标准
- 8 类 pack_type（包类型）抽取重点
- 4 Gates（四闸）判定细则
- 9 Tables（九表）列定义
- pack_type → 9 Tables 默认投影
- ID 生成规则
- pack_type → object_type（对象类型）映射
- 反空壳门禁清单

执行 Phase 2 serving 工程前，先读 `task_cards/README.md` 与对应 `KS-*.md` 卡，跑 `python3 task_cards/validate_task_cards.py` 确认 DAG 闭环。

本 CLAUDE.md 只做兜底红线，**不复述** skill 与 task_cards 内的细则。
