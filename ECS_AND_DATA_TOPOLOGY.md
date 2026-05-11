# ECS 接入信息 + 数据拓扑与能力边界

> 用途：让未来会话能直接连 ECS 做审查验证，并理解本仓 `clean_output/` 与 ECS 数据库各自的能力边界。
> 首版：2026-05-11 · 维护人：faye
> 实测等级：本文档中 `runtime_verified` = 已实测，`inferred` = 据容器名 / 表名推断未读源码

---

## Part 1 · ECS 访问信息（给 Claude 复用）

### 1.1 SSH 接入

| 项 | 值 |
|---|---|
| 公网 IP | `8.217.175.36`（中国香港 D） |
| 端口 | `22`（安全组对 `0.0.0.0/0` 开放） |
| 用户 | `root` |
| 系统 | Ubuntu 22.04 64 位 |
| 实例 ID | `i-j6chm57l2pyy6xb6iicw` |
| 私钥（本机路径）| `${ECS_SSH_KEY_PATH}`（默认 `~/.ssh/diyu-hk.pem`，权限 600；**不入 git**，仅本机存在） |

**连接命令**（先 `source scripts/load_env.sh` 加载 env / load env first）：
```bash
ssh -i $ECS_SSH_KEY_PATH $ECS_USER@$ECS_HOST
```

⚠️ **安全提示 / security note**：密钥与密码统一走 `.env`（已 gitignored）；变量名见 `.env.example`。如需轮换，在阿里云控制台「密钥对」处重建并更新 `.env`。

### 1.2 ECS 上的目录布局（runtime_verified）

| ECS 路径 | 内容 |
|---|---|
| `/data/clean_output/` | 与本仓 `clean_output/` 同步的产出（2026-05-08 快照，比本地旧 3 天，仅 3 个 `audit/*` 文件存在等长修订差异） |
| `/root/` | root 家目录 |

> 注意：ECS 上**没有外层 `20-血肉-2F种子/`**，`clean_output` 直接挂在 `/data/` 下。

### 1.3 ECS 上运行的服务（runtime_verified）

通过 `docker ps` 实测：

| 容器名 | 镜像 | 端口（仅本机） | 用途（inferred） |
|---|---|---|---|
| `diyu-brand-faye-app-1` | `diyu-agent:p5-06-5dc92a4` | `0.0.0.0:8004→8000` | 笛语品牌 agent 应用（runtime） |
| `diyu-infra-postgres-1` | `pgvector/pgvector:pg16` | `127.0.0.1:5432` | 主数据库（PostgreSQL + pgvector） |
| `diyu-infra-qdrant-1` | `qdrant/qdrant:v1.12.5` | `127.0.0.1:6333` | 向量数据库（unhealthy 状态，需关注） |
| `diyu-infra-redis-1` | `redis:7-alpine` | `127.0.0.1:6379` | 缓存 / 会话 |
| `diyu-infra-minio-1` | `minio/minio:latest` | `127.0.0.1:9000-9001` | 对象存储 |

宿主上还有 nginx（80/443）做反向代理；另有一个 `lxd` 用户跑的原生 postgres 进程（非业务库）。

### 1.4 PostgreSQL 连接信息（runtime_verified）

从 `docker inspect diyu-infra-postgres-1` 读取的环境变量：

| 项 | 值 |
|---|---|
| 容器 | `diyu-infra-postgres-1` |
| 监听 | `${PG_HOST}:${PG_PORT}` = `127.0.0.1:5432`（**仅本机**，不对外） |
| 默认数据库 | `diyu` |
| 业务数据库 | `${PG_DATABASE}` = `diyu_brand_faye` |
| 用户 | `${PG_USER}` = `diyu` |
| 密码 | `${PG_PASSWORD}`（见 `.env`，**不入 git** / see .env, never committed） |

**所有数据库**（`SELECT datname FROM pg_database WHERE datistemplate=false`）：
- `postgres`（PG 默认）
- `diyu`（空，只有系统表）
- `diyu_brand_faye`（**业务库**）

**`diyu_brand_faye` 的 schema**：
- `public` — 应用层表（org / users / sessions / conversations / media / usage 等）
- `knowledge` — 知识层表（**本仓产出的下游消费目标**，详见 Part 2）
- `knowledge_industrial` — 行业级知识（空 schema 占位 inferred）
- `gateway` — API key 与审计日志

### 1.5 常用审查命令模板

**列出 knowledge schema 所有表的行数**：
```bash
ssh -i $ECS_SSH_KEY_PATH $ECS_USER@$ECS_HOST \
  "docker exec diyu-infra-postgres-1 psql -U diyu -d diyu_brand_faye -c \"
   SELECT 'knowledge.'||table_name AS t,
          (xpath('/row/c/text()', query_to_xml('SELECT count(*) c FROM knowledge.'||quote_ident(table_name), false, true, '')))[1]::text::int AS rows
   FROM information_schema.tables WHERE table_schema='knowledge' ORDER BY 1;\""
```

**对比 `clean_output/` 一致性**（本地 vs ECS，hash 比对）：
```bash
LC_ALL=C find clean_output -type f ! -path "*/.*" | sort | xargs sha256sum > /tmp/local.sum
ssh -i $ECS_SSH_KEY_PATH $ECS_USER@$ECS_HOST \
  'cd /data && find clean_output -type f ! -path "*/.*" | sort | xargs sha256sum' \
  | LC_ALL=C sort > /tmp/ecs.sum
diff <(LC_ALL=C sort /tmp/local.sum) /tmp/ecs.sum
```

**进 PG 交互式（应急排查）**：
```bash
ssh -i $ECS_SSH_KEY_PATH $ECS_USER@$ECS_HOST \
  'docker exec -it diyu-infra-postgres-1 psql -U diyu -d diyu_brand_faye'
```

### 1.6 操作纪律（写给未来的 Claude）

1. **只读优先**：审查任务一律只 `SELECT / find / sha256sum`，不 `INSERT / UPDATE / DELETE / DROP / rm / mv`。
2. **改动需明确授权**：任何写操作必须先经用户确认。
3. **不要把密钥 / 密码贴回对话**：本文档已登记，引用即可。
4. **核对再行动**：先 `ssh ... 'echo CONNECTED && date'` 验证连通，再做后续。
5. **不假设跨时间窗连续**：ECS 上的快照时间戳必须现场 `stat / git log` 验证。

---

## Part 2 · 数据拓扑与能力边界

### 2.1 两边数据的真实关系（一张图）

```
[ Q2/Q4/Q7Q12 三个输入 markdown ]
            │
            ▼
[ 本仓 clean_output/ ] —— 抽取层 / 元数据 SSOT
   nine_tables/    : 9 表知识图谱范式（object_type, field, semantic, value_set, relation, rule, evidence, lifecycle, call_mapping）
   candidates/     : 候选 CandidatePack（按 brand_layer 分租户）
   audit/          : 覆盖率、4 闸结果、登记表、最终报告
   templates/      : 抽取模板
   schema/         : 9 表 JSON schema

            ↓（投影 / ETL，目前**未完成**）

[ ECS diyu_brand_faye DB ] —— 应用消费层
   knowledge.*     : 业务领域表（persona, role_profile, content_blueprint, brand_tone, content_type, compliance_rule, global_knowledge, narrative_arc, enterprise_narrative_example）
   public.*        : 应用运行时（users, conversations, sessions, media, usage…）
   gateway.*       : API key 与审计
```

### 2.2 当前两边的内容对照（runtime_verified, 2026-05-11）

**本仓 `clean_output/nine_tables/` 行数**：

| 表 | 行数 |
|---|---:|
| 01_object_type | 19 |
| 02_field | 99 |
| 03_semantic | 164 |
| 04_value_set | 605 |
| 05_relation | 174 |
| 06_rule | 202 |
| 07_evidence | 955 |
| 08_lifecycle | 2 |
| 09_call_mapping | 244 |
| **合计** | **2,464** |

**ECS `diyu_brand_faye.knowledge.*` 行数**：

| 表 | 行数 | 备注 |
|---|---:|---|
| brand_tone | 1 | 仅 1 行 |
| compliance_rule | **0** | 空 |
| content_blueprint | 45 | 有数据 |
| content_type | 3 | 仅 3 行 |
| enterprise_narrative_example | **0** | 空 |
| global_knowledge | 1,394 | 全部 `entity_type='GlobalKnowledge'`（单一类型 JSONB 通用桶）|
| narrative_arc | **0** | 空 |
| persona | **0** | 空 |
| role_profile | 8 | 与本仓 RoleProfile 数量级吻合 |
| **合计** | **1,451** | |

**关键事实**：

- 两边的表**完全不同名**——本仓是 9 表元数据范式，ECS 是 9 个业务领域表，没有任何一张表能直接对应。
- ECS `knowledge.*` 多数表为空，**抽取产出尚未灌入 ECS**。
- ECS `global_knowledge` 1394 行的 `entity_type` 只有 `GlobalKnowledge` 一种，**不是 9 表 evidence 行的扁平化投影**。
- 本仓与 ECS `/data/clean_output/` 的**文件层**一致（836/836 文件名相同，仅 3 个 `audit/*` 文件内容修订），ECS 上的文件是 2026-05-08 快照。

### 2.3 各自的能力边界

#### A. 本仓 `clean_output/` 能做什么 / 不能做什么

| 能做 | 说明 |
|---|---|
| ✅ 知识抽取的 SSOT | 9 表是抽取层"是什么"的唯一真相源 |
| ✅ 反空壳质量审计 | 4 闸结果、evidence_quote 反向核验、anchor_quote 违规检测 |
| ✅ 证据溯源 | evidence_id → 原文段落，可追到 Q2/Q4/Q7Q12 markdown 哪一行 |
| ✅ 多租户隔离 key 校验 | brand_layer 列决定 pack 能被哪些品牌消费 |
| ✅ Schema 演进决策 | object_type / allowed_relation_kinds 是封闭清单，控制建模边界 |
| ✅ 候选评审与归档 | CandidatePack + needs_review / unprocessable_register |

| 不能做 | 说明 |
|---|---|
| ❌ 应用运行时服务 | 没有应用层表（无 users / sessions / org），不能直接被 agent 调用 |
| ❌ 向量检索 | 没有 embedding 列，需要 Qdrant 才能做语义搜索 |
| ❌ 持续高并发查询 | CSV/YAML 文件不适合 OLTP，需要先入库 |
| ❌ 实时写入 | 抽取产出是离线批处理形态，不接受实时变更 |

#### B. ECS `diyu_brand_faye` 数据库能做什么 / 不能做什么

| 能做 | 说明 |
|---|---|
| ✅ 笛语 agent 应用运行时 | `diyu-brand-faye-app-1` 容器消费 `public.*` 应用表 |
| ✅ 用户 / 会话 / 配额管理 | users / sessions / conversations / usage_budgets / org_members |
| ✅ 媒体对象存储索引 | personal_media_objects / enterprise_media_objects（实物在 MinIO） |
| ✅ 审计与计费 | audit_events / llm_usage_records / tool_usage_records |
| ✅ 向量检索 | pgvector 扩展 + Qdrant 容器（向量库当前 unhealthy） |
| ✅ 会话短期记忆 | memory_items / memory_receipts |

| 不能做 | 说明 |
|---|---|
| ❌ 完整的知识查询 | `knowledge.*` 多数表为空，目前不是完整知识源 |
| ❌ 抽取过程溯源 | 没有 evidence 行、没有 4 闸记录、没有 candidate pack |
| ❌ 多品牌隔离的 schema-level 区分 | brand_layer 信息只在 payload JSONB 内（如果有），不是 schema-level 物理隔离 |
| ❌ 替代本仓做抽取质量审计 | 没有抽取阶段中间产物 |

### 2.4 当前缺口（重要 · 决定下一步动作的依据）

1. **抽取 → 入库的 ETL 链路尚未完成**：
   - 本仓 9 表 2464 行，ECS `knowledge.*` 只有 1451 行且多数表空。
   - ECS `global_knowledge` 是 JSONB 通用桶（单一 entity_type），**不是 9 表的扁平化投影**——说明现在 ECS 上的"知识"是另一条独立写入路径，与本仓抽取**没有打通**。
2. **ECS 文件层 `/data/clean_output/` 是 3 天前的快照**：
   - 即便有 ETL，源也是过期的。
3. **Qdrant 向量库 unhealthy**：
   - 语义检索能力暂不可用，需要排查。

### 2.5 一句话总结（给非技术读者）

- **本仓 `clean_output/`** = **"原料 + 化验单"**：原始知识结构化后的、有据可查的、可被审计的元数据。
- **ECS 数据库** = **"出货车间 + 仓库"**：跑应用、接用户、记账单的运行时数据。
- **两边目前没有打通**：原料车间产出的知识，目前还没有完整流水线灌进 ECS 仓库。要做的是设计并执行 **9 表 → ECS knowledge.*** 的投影/ETL 路径。

---

## 附录 · 变更记录

| 日期 | 修改 |
|---|---|
| 2026-05-11 | 初版（faye 请求）。Part 1 ECS 接入信息 + Part 2 数据拓扑与能力边界。 |
