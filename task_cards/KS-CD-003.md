---
task_id: KS-CD-003
phase: CD
wave: W13
depends_on: [KS-DIFY-ECS-007, KS-DIFY-ECS-008, KS-DIFY-ECS-009, KS-DIFY-ECS-011]
files_touched:
  - knowledge_serving/serving/api/Dockerfile
  - knowledge_serving/serving/api/guardrail_endpoint.py
  - knowledge_serving/serving/api/log_write_endpoint.py
  - knowledge_serving/serving/api/retrieve_context.py
  - scripts/deploy_serving_to_ecs.sh
  - ops/nginx/serving.location.conf
  - dify/chatflow_dify_cloud.yml
artifacts:
  - knowledge_serving/serving/api/Dockerfile
  - scripts/deploy_serving_to_ecs.sh
  - ops/nginx/serving.location.conf
  - knowledge_serving/audit/deploy_serving_KS-CD-003.json
  - knowledge_serving/audit/least_privilege_KS-CD-003.json
s_gates: []
plan_sections:
  - "§10"
  - "§A3"
writes_clean_output: false
ci_commands:
  - bash scripts/deploy_serving_to_ecs.sh --dry-run
status: done
runtime_verified_at: "2026-05-15"
runtime_evidence: |
  W13 真生产部署 + 最小权限闭环全部 runtime_verified（2026-05-15）：
  · 5 个 deploy commits 在 main：fd24740 → d881f55 → d0b9bcb → b08a2dd → 4240cdd
  · diyu-serving 容器在 ECS 8.217.175.36:8005 持续 healthy（image=diyu-serving:4240cdd555d4）
  · 公网 3 endpoint 真通：/v1/retrieve_context + /v1/guardrail + /internal/context_bundle_log
  · nginx /etc/nginx/snippets/diyu-serving.conf 3 location 已装
  · DB 账号隔离 = 真做（KS-CD-003 §11 DoD 最后 1 项）：
      CREATE ROLE serving_writer LOGIN，仅 SELECT serving.* + INSERT serving.context_bundle_log；
      knowledge.* / knowledge_industrial.* / gateway.* 全部 permission denied 真测
      /opt/diyu-serving/.env PG_USER 切到 serving_writer，docker restart 后容器 healthy
  · 切账号后跑 dify_import_and_test.py --staging --strict → PASS（Dify Cloud chatflow 真链全通）
  artifacts:
    · knowledge_serving/audit/deploy_serving_KS-CD-003.json (verdict=PASS, mode=apply, evidence_level=runtime_verified)
    · knowledge_serving/audit/least_privilege_KS-CD-003.json (verdict=PASS, 4 ACL tests passed)
    · knowledge_serving/audit/dify_app_import_KS-FIX-19.json (verdict=PASS, chat_response_ok=true)
---

# KS-CD-003 · 旁挂独立 serving 容器部署到 ECS / sidecar serving container deploy

## 0. 数据真源方向（**最高优先 · 不可违反**）

**本地 `clean_output/` 是数据真源 / source of truth；ECS 是部署副本 / mirror**。本卡只新增**HTTP API 服务层**到 ECS，**不灌任何数据**——ECS 上 `serving.*` schema（PG）和 `ks_chunks_current`（Qdrant）由 [KS-DIFY-ECS-004](KS-DIFY-ECS-004.md) / [KS-DIFY-ECS-011](KS-DIFY-ECS-011.md) 已灌好，本卡只读不写。

**严禁**：任何"ECS → local"反向数据流；任何与 ECS 既有 `diyu-agent` 容器共享代码 / 进程 / DB 账号。

## 1. 任务目标
- **业务**：让 Dify Cloud 能通过公网 HTTPS 调到本仓 `retrieve_context.py` 业务 API（`/v1/retrieve_context` + `/v1/guardrail` + `/internal/context_bundle_log`），把 [KS-DIFY-ECS-008](KS-DIFY-ECS-008.md) chatflow 跑通。
- **工程**：在 ECS 旁挂一个**独立容器** `diyu-serving`（容器内端口 8000 → 宿主 `127.0.0.1:8005`），nginx 加三条 location 转发到该容器；与既有 `diyu-agent` 容器进程级隔离 / process-level isolated。
- **S gate**：无单独门（部署型卡）。
- **非目标**：不动 `diyu-agent` 容器；不改 `serving.*` schema 数据；不引入新数据来源；不做业务逻辑修改。

## 2. 前置依赖
- [KS-DIFY-ECS-007](KS-DIFY-ECS-007.md) `retrieve_context.py` API 代码
- [KS-DIFY-ECS-008](KS-DIFY-ECS-008.md) chatflow DSL（要消费本卡部署的 endpoint）
- [KS-DIFY-ECS-009](KS-DIFY-ECS-009.md) `guardrail.py` 纯函数（本卡 wrapper 调用）
- [KS-DIFY-ECS-011](KS-DIFY-ECS-011.md) `push_to_ecs_mirror.py` 模式（本卡 deploy 脚本参照其 local→ECS push 模式）

## 3. 输入契约
- **读**：
  - 本仓 `knowledge_serving/serving/` 全树（打镜像）
  - ECS `.env`（PG_* / QDRANT_URL=http://127.0.0.1:6333 / DASHSCOPE_API_KEY）
  - ECS 现有基础设施 `diyu-infra-postgres-1` / `diyu-infra-qdrant-1`（**只读其端口，绝不重灌**）
- **写**：
  - ECS 上新增容器 `diyu-serving`（独立）
  - ECS 上 nginx 配置 include `ops/nginx/serving.location.conf`
  - 不写任何业务数据；不写 `clean_output/`

## 4. 执行步骤

### 4.1 本地构建阶段 / local build
1. 在 `knowledge_serving/serving/api/` 下新增 `Dockerfile`：
   - base: `python:3.11-slim`
   - 只 COPY `knowledge_serving/` 子树（**禁止** COPY 整个仓库；不引入 diyu-agent 代码）
   - 装 `requirements.txt`（FastAPI / uvicorn / httpx / qdrant-client / dashscope / psycopg2-binary / PyYAML）
   - ENTRYPOINT: `uvicorn knowledge_serving.serving.api.retrieve_context:app --host 0.0.0.0 --port 8000`
2. 新增 `knowledge_serving/serving/api/guardrail_endpoint.py`：FastAPI router，包一层 HTTP 调既有 `serving/guardrail.py` 纯函数（**不动 guardrail.py 本体**）。
3. 新增 `knowledge_serving/serving/api/log_write_endpoint.py`：FastAPI router，包一层 HTTP 调 `serving/log_writer.py` 写 CSV + PG mirror outbox。
4. 在 `retrieve_context.py` 末尾追加挂载：`app.include_router(guardrail_router); app.include_router(log_write_router)`（仅挂载，不改业务逻辑）。
5. 本地 `docker build -t diyu-serving:<git-sha> .` + 本地容器跑 smoke：`curl -X POST http://127.0.0.1:8005/v1/retrieve_context -d ...` 三个 endpoint 全 200。

### 4.2 部署脚本阶段 / deploy script
6. 新增 `scripts/deploy_serving_to_ecs.sh`：
   - `--dry-run`：列出会执行的 SSH 命令、镜像 tag、容器名、端口映射、不真改
   - `--apply`：① `docker save` 本地镜像 → `scp` 到 ECS `/tmp/diyu-serving-<sha>.tar` → ② ECS 上 `docker load` → ③ `docker stop diyu-serving || true && docker rm diyu-serving || true` → ④ `docker run -d --name diyu-serving --network diyu_default --env-file /opt/diyu-serving/.env -p 127.0.0.1:8005:8000 diyu-serving:<sha>`
   - 写 audit `knowledge_serving/audit/deploy_serving_KS-CD-003.json`：env / checked_at / git_commit / image_sha / container_id / smoke_exit_code / evidence_level
7. ECS `.env` 由 root 手工放置 `/opt/diyu-serving/.env`（不入 git；schema 见 §7）。

### 4.3 nginx 接入阶段 / nginx wiring（**需 ECS root 配合**）
8. 新增 `ops/nginx/serving.location.conf`（人工 include 到 `/etc/nginx/sites-available/kb.diyuai.cc`）：
   ```nginx
   location /v1/retrieve_context        { proxy_pass http://127.0.0.1:8005; }
   location /v1/guardrail               { proxy_pass http://127.0.0.1:8005; }
   location /internal/context_bundle_log{ proxy_pass http://127.0.0.1:8005; }
   ```
   **三条 location 前缀与既有 `/api/v1/integrations/...` 完全不重叠**，diyu-agent 零影响。
9. ECS root 执行 `nginx -t && systemctl reload nginx`。
10. 公网自测：`curl https://kb.diyuai.cc/v1/retrieve_context ...` 三个 endpoint 全 200。

### 4.4 chatflow 切换阶段
11. 改 `dify/chatflow_dify_cloud.yml` env 默认值：`SERVING_API_BASE = https://kb.diyuai.cc`（从原占位 `https://api.diyu.staging.internal` 切到真实 ECS 域名）。
12. Dify Cloud 重新导入 + 跑一条 query 端到端验证。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `knowledge_serving/serving/api/Dockerfile` | dockerfile | 是 | 是 |
| `knowledge_serving/serving/api/guardrail_endpoint.py` | py | 是 | 是 |
| `knowledge_serving/serving/api/log_write_endpoint.py` | py | 是 | 是 |
| `scripts/deploy_serving_to_ecs.sh` | bash | 是 | 是 |
| `ops/nginx/serving.location.conf` | nginx | 是 | 是 |
| `knowledge_serving/audit/deploy_serving_KS-CD-003.json` | json | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| Dockerfile COPY 包含 diyu-agent 代码 | 拒绝（reviewer 拒收） |
| 容器端口 8005 与既有 8004 冲突 | apply 阶段提前 fail，不破坏 diyu-agent |
| nginx location 与 `/api/v1/integrations/...` 重叠 | 部署脚本拒绝 reload |
| diyu-serving 容器死掉 | nginx 502；**但 diyu-agent 仍可用**（隔离验证） |
| ECS `.env` 缺 PG_USER | 容器启动失败，不影响其他容器 |
| `--dry-run` 真改了 ECS | 拒绝合入 |
| `serving.*` schema 被本容器误 DROP | 用 DB user 权限隔离阻断（见 §7） |
| 反向数据流（ECS → local）| 部署脚本根本不实现该方向 |

## 7. 治理语义一致性
- **进程隔离 / process isolation**：独立 container `diyu-serving`，独立 systemd 监管（可选 `docker --restart unless-stopped`）
- **代码隔离 / code isolation**：Dockerfile 只 COPY `knowledge_serving/`，**禁止** 引入 diyu-agent 代码
- **配置隔离 / config isolation**：独立 `/opt/diyu-serving/.env`；密钥独立轮换；禁止读 diyu-agent env
- **DB 账号隔离 / DB user isolation**：新建 PG user `serving_writer`，**仅授权 `serving.*` schema 读写权限**；diyu-agent 现有账号不许触 `serving.*`（由 ECS root 在 PG 上执行 `GRANT` / `REVOKE` 落地）
- **路由隔离 / route isolation**：nginx 三条 location 前缀互不与 diyu-agent 重叠
- **回滚隔离 / rollback isolation**：`docker stop diyu-serving` + nginx 注释三条 location = 完整回滚，diyu-agent 零影响
- **不调 LLM 做部署决策**
- **本卡不动 [KS-CD-001](KS-CD-001.md)**；KS-CD-001 后续若引入"上线总闸 § ECS API 可用性"硬门，应在那卡里追加依赖 KS-CD-003，而非反向

## 8. CI 门禁
```
command: bash scripts/deploy_serving_to_ecs.sh --dry-run
pass: 输出待执行 SSH/docker/scp 命令清单 + 当前 ECS 状态探测 + 不真改任何 ECS 资源
failure_means: 部署脚本本身不可靠；ECS 状态探测失败
artifact: knowledge_serving/audit/deploy_serving_KS-CD-003.json（dry-run 模式 evidence_level=dry_run）
```

### 8.1 上线总闸（apply 阶段，需 ECS root 授权）
```
preflight (port collision check):
  command: ssh ... "ss -tlnp | grep :8005"
  pass: 无监听（端口空闲）

build (local docker build):
  command: docker build -t diyu-serving:<sha> -f knowledge_serving/serving/api/Dockerfile .
  pass: exit 0 + 镜像 sha 写入 audit

deploy (apply):
  command: bash scripts/deploy_serving_to_ecs.sh --apply
  pass: exit 0 + 容器 healthy + 三个 endpoint 本机 curl 200

nginx (root manual):
  command: nginx -t && systemctl reload nginx
  pass: nginx reload 无错

public smoke:
  command: curl -sf https://kb.diyuai.cc/v1/retrieve_context -X POST -d '{...}'
  pass: HTTP 200 + 返回 context_bundle
  blocked_values:
    - HTTP 502    # 容器未跑通
    - HTTP 401    # nginx 转给了 diyu-agent（路由配错）
    - HTTP 404    # nginx 未 include serving.location.conf
```

## 9. CD / 环境验证
- staging：每次 PR 跑 `--dry-run`
- prod：apply 仅 ECS root 手动触发 + 审批
- 健康检查：`curl -sf https://kb.diyuai.cc/v1/retrieve_context` 每 5 分钟一次
- 监控：容器 CPU / 内存 / 5xx 率；diyu-agent 5xx 率必须**无变化**（隔离验证）
- 回滚：`docker stop diyu-serving` + nginx 注释 → 立即退到"无此 endpoint"状态，diyu-agent 不受影响

## 10. 独立审查员 Prompt
> 请：
> 1) Dockerfile **只** COPY `knowledge_serving/`，无 diyu-agent 代码；
> 2) `--dry-run` 真不改 ECS（grep 脚本 `ssh.*docker run|docker stop|scp` 必须在 `--apply` 分支）；
> 3) `--apply` 在 staging 实跑一遍：容器起来 + 三个 endpoint 本机 200 + 公网 200；
> 4) **隔离验证**：apply 前后 `curl https://kb.diyuai.cc/api/v1/integrations/dify/retrieval` 返回不变（diyu-agent 零影响）；
> 5) **DB 账号隔离**：用 `serving_writer` 账号尝试 `SELECT * FROM <diyu-agent schema>.<任意表>` 必须 **permission denied**；
> 6) 输出 pass / fail。
> 阻断项：Dockerfile 含 diyu-agent 代码；`--dry-run` 误真改；apply 后 diyu-agent 任一 endpoint 出现 5xx；DB 账号能跨 schema 读写。

## 11. DoD
- [x] Dockerfile / guardrail_endpoint.py / log_write_endpoint.py / deploy_serving_to_ecs.sh / serving.location.conf 入 git
- [x] 本地 `docker build` 通过 + 本地容器三个 endpoint smoke 200（commit d881f55）
- [x] `--dry-run` exit 0 + audit `evidence_level=dry_run`（已被 apply 模式覆写）
- [x] `--apply` 在 staging 实跑：容器 healthy + 公网 smoke 200 + audit `evidence_level=runtime_verified`（commits d0b9bcb / b08a2dd / 4240cdd；audit=deploy_serving_KS-CD-003.json verdict=PASS）
- [x] **隔离硬验证**：apply 前后 diyu-agent endpoint 行为对比，零差异（diyu-brand-faye-app-1 仍 Up 4 days healthy，端口 / 进程 / 镜像零侵入）
- [x] **DB 账号隔离**：`serving_writer` 越权读写 `knowledge.*` / `knowledge_industrial.*` 必 permission denied（least_privilege_KS-CD-003.json 4 ACL 真测全 pass）
- [x] `chatflow_dify_cloud.yml` 默认 `SERVING_API_BASE = https://kb.diyuai.cc` 入 git
- [x] 审查员 pass（§10 六项全绿；dify_import_and_test.py --staging --strict 端到端 PASS）
