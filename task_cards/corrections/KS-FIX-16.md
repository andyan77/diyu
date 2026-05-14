---
task_id: KS-FIX-16
corrects: KS-DIFY-ECS-007
severity: FAIL
phase: Dify-ECS
wave: W11
depends_on: [KS-FIX-15]
files_touched:
  - knowledge_serving/serving/api/retrieve_context.py
  - knowledge_serving/tests/test_api_real_http.py
creates:
  - knowledge_serving/tests/test_api_real_http.py
artifacts:
  - knowledge_serving/audit/api_ecs_deployment_KS-FIX-16.json
status: done
---

# KS-FIX-16 · API 真接 vector_retrieve + ECS staging 部署 + 真 HTTP 测

## 1. 任务目标
- **business**：原卡 API 代码 `vector_res=None`、测试用 TestClient、未部署到 ECS。本卡：删 None、部署到 ECS、真实 HTTP client 跑测。
- **engineering**：`requests.post("http://<ecs_api_host>:<port>/v1/retrieve_context", ...)` 200；bundle.vector_res 非空。
- **S-gate**：S11 ECS 服务上线。
- **non-goal**：不做 Dify 节点（FIX-19）。

## 2. 前置依赖
- KS-FIX-15（vector path 默认绿）。

## 3. 输入契约
- staging ECS 实例运行 FastAPI；HTTP 端口走 env。

## 4. 执行步骤
1. 删 API 内 `vector_res = None` 兜底（如还留）。
2. 部署到 ECS staging（compose / systemd）。
3. 跑 `pytest test_api_real_http.py --api-base $STAGING_API_BASE` → real HTTP 200。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/api_ecs_deployment_KS-FIX-16.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | TestClient 冒充 staging：`STAGING_API_BASE` 包含 testserver/localhost/127.0.0.1 | **fail-closed**：测试拒跑（守门 base_url 必须公网 ECS） |
| AT-02 | API 源码遗留 `vector_res = None` 兜底（未 structured_only 守护） | source-scan grep 拦下 |
| AT-03 | 公网 HTTPS 真实 5+ 次 POST + vector_meta.candidate_count > 0 | real HTTP 200 ≥ 5 且 vector_res 非空 |
| AT-04 | ECS 容器 /healthz down | SSH curl 容器 127.0.0.1:8005/healthz → 非 200 时 fail-closed |

## 7. 治理语义一致性
- API 不收 brand_layer 入参（红线）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_api_real_http.py -v --staging
pass:    real_http_200_count >= 5 且 vector_res 非空
```

## 9. CD / 环境验证
- staging：ECS 服务；prod：FIX-25。
- 健康检查：/healthz from real HTTP。
- 监控：QPS / p99 / 5xx。

## 10. 独立审查员 Prompt
> 验：1) 测试 base_url 真打 ECS；2) `vector_res=None` 代码 0 命中；3) /healthz 真返 200；4) ECS 进程 ps 看得到。

## 11. DoD
- [x] real HTTP 200（6 distinct queries via 公网 https://kb.diyuai.cc → 6/6 HTTP 200 + vector_meta.candidate_count=2 each；pytest test_real_http_200_at_least_5 PASS）
- [x] ECS service 启动（diyu-serving 容器 Up 7 minutes (healthy)；container /healthz=200；KS-CD-003 §4.2-4.4 已部署）
- [x] artifact runtime_verified（`knowledge_serving/audit/api_ecs_deployment_KS-FIX-16.json` env=staging / checked_at=2026-05-14T15:25:16Z / git_commit=4240cdd / evidence_level=runtime_verified）
- [x] 审查员 pass（reviewer_prompt_coverage §10 三项 + KS-FIX-16 §10 四项均 PASS；verdict=PASS）
- [x] 原卡 KS-DIFY-ECS-007 回写（§14 追加 KS-FIX-16 real HTTP wire 补证段）
- [x] dangling create 清理：原 `knowledge_serving/deploy/ecs_service.yaml` 从未落地（实际 staging 部署走 KS-CD-003 `deploy_serving.sh` + docker compose，证据落 `deploy_serving_KS-CD-003.json`）；本次从 creates 列表移除，files_touched 同步删除避免 C15 dangling 误报。

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_base_url_not_testclient` | knowledge_serving/tests/test_api_real_http.py |
| AT-02 | `test_no_unguarded_vector_res_none_in_source` | knowledge_serving/tests/test_api_real_http.py |
| AT-03 | `test_real_http_200_at_least_5` | knowledge_serving/tests/test_api_real_http.py |
| AT-04 | `test_ecs_container_healthz_via_ssh` | knowledge_serving/tests/test_api_real_http.py |

## 16. 被纠卡同步 / sync original card

- 被纠卡：**KS-DIFY-ECS-007**（W11 主卡 · `/v1/retrieve_context` HTTP API wrapper）。
- 同步动作：原卡 §14 实施记录已追加 KS-FIX-16 real HTTP wire 补证段（详见原卡 §14）。
- 双写 runtime artifact：[knowledge_serving/audit/api_ecs_deployment_KS-FIX-16.json](../../knowledge_serving/audit/api_ecs_deployment_KS-FIX-16.json)（本卡 §5 唯一 artifact，env=staging / evidence_level=runtime_verified / 6 distinct queries via 公网 https://kb.diyuai.cc 全 HTTP 200）。
- 同步时间戳：2026-05-14T15:25:16Z（real HTTP 探针 + ECS 容器 /healthz 通过）。
