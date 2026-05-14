# Problem Task Cards Wave Matrix

> Date: 2026-05-14
> Scope: 57 task cards production-readiness audit
> Source: external review conclusion + stricter KS-DIFY-ECS-010 replay requirement
> Note: this file is an audit artifact only. It does not lower task-card standards and does not change task status.

## Summary

- Problem cards: 26 / 57
- Severity split: FAIL x13, RISKY x6, CONDITIONAL_PASS x4, BLOCKED x3
- Special note: KS-PROD-002 is both FAIL and BLOCKED because the current local command is broken and the required real staging e2e path is not available.
- Overall gate: do not promote W14 until Dify / ECS / PG / Qdrant / API production paths have real staging evidence.

## Matrix

| # | wave | task_id | current status | severity | core issue | minimal correction |
|---:|---|---|---|---|---|---|
| 1 | W0 | KS-S0-004 | done | FAIL | Raw `ci_commands` lacks `QDRANT_URL_STAGING`; current run exited 2, no current real Qdrant health evidence. | Run after `source scripts/load_env.sh`, hit real staging Qdrant, and write audit artifact. |
| 2 | W2 | KS-SCHEMA-005 | done | FAIL | Purity check exits 1 because current files exceed plan §11 directory contract. | Update the directory contract or roll status back. |
| 3 | W3 | KS-COMPILER-002 | done | RISKY | Coverage is fully missing while command exits 0. | Decide whether `coverage=missing` is allowed; if not, add real assertions. |
| 4 | W3 | KS-COMPILER-010 | done | CONDITIONAL_PASS | Rerank is declared in policy but not actually called. | Keep policy card done; validate rerank in runtime acceptance. |
| 5 | W0 | KS-POLICY-005 | done | CONDITIONAL_PASS | `model_policy` validation warned about missing `DEEPSEEK_API_KEY`; no staging model-policy runtime snapshot. | Add staging env-backed policy snapshot evidence. |
| 6 | W7 | KS-RETRIEVAL-006 | done | RISKY | Only local pytest / injected or static evidence; production API path is not wired to real Qdrant. | Make `/v1/retrieve_context` call `vector_retrieve()` against staging Qdrant. |
| 7 | W9 | KS-RETRIEVAL-008 | done | RISKY | Local pytest covers bundle/log behavior, but PG mirror is not closed in a real staging path. | Run PG mirror e2e and reconcile both sides. |
| 8 | W10 | KS-RETRIEVAL-009 | done | FAIL | Demo defaults to `structured_only_offline`, which is a bypass path for production evidence. | Make demo/API exercise the real vector path. |
| 9 | W6 | KS-VECTOR-001 | done | RISKY | `--check` validates existing chunks; no current staging rebuild proof for embedding calls. | Rebuild embeddings in staging and record run artifact with call evidence and timestamp. |
| 10 | W7 | KS-VECTOR-003 | done | FAIL | Original command uses `--offline` smoke, not real Qdrant. | Replace/augment with staging Qdrant filter test. |
| 11 | W1 | KS-DIFY-ECS-001 | done | ~~FAIL~~ → **RESOLVED 2026-05-14** | ~~Real staging mirror check exits 1 with ECS mirror drift.~~ Closed by **KS-FIX-03**: push --apply landed local→ECS, `drift_total=0`, artifact `ecs_mirror_verify_KS-FIX-03.json` evidence_level=runtime_verified. | ~~Fix ECS mirror drift and rerun.~~ Done. |
| 12 | W2 | KS-DIFY-ECS-002 | done | CONDITIONAL_PASS | Staging PG reconcile exits 0, but result is `schema_misalignment` with overlap 0. | Keep the explicit decision that legacy PG is not in the serving trust chain. |
| 13 | W6 | KS-DIFY-ECS-003 | done | FAIL | Original command is `--dry-run`; apply evidence is not current staging acceptance. | Run staging `--apply` for `serving.*` PG upload. |
| 14 | W7 | KS-DIFY-ECS-004 | done | FAIL | Original command is `--dry-run`, which cannot stand in for Qdrant upload acceptance. | Run staging `--apply` and verify via live Qdrant search. |
| 15 | W10 | KS-DIFY-ECS-005 | done | RISKY | Dual-write is covered by local pytest only; PG was not exercised in staging. | Create staging PG mirror table, write rows, and reconcile. |
| 16 | W11 | KS-DIFY-ECS-006 | done | FAIL | Smoke exits 0 while Qdrant is unreachable, `qdrant_live_hit=false`, and PG is degraded. | Require real API + real Qdrant + real PG all green; add `external_deps_reachable` gate. |
| 17 | W11 | KS-DIFY-ECS-007 | done | FAIL | API code sets `vector_res = None`; tests use TestClient; ECS staging does not prove deployed service. | Wire API to `vector_retrieve()`, deploy to ECS staging, and test via real HTTP. |
| 18 | W12 | KS-DIFY-ECS-008 | not_started | BLOCKED | DSL validates locally, but is not imported into Dify staging; URL path may drift from FastAPI route. | Align URL, import into Dify staging, and record `dify_app_id` plus one real chat response. |
| 19 | W7 | KS-DIFY-ECS-009 | done | CONDITIONAL_PASS | Guardrail local pytest is valid, but Dify / LLM integration has not been exercised. | Re-accept after Dify staging integration. |
| 20 | W11 | KS-DIFY-ECS-010 | done | RISKY | Replay currently proves a single request_id; dirty diff shows request_id / brand layer / overlay count can change while `byte_identical_replay=true`. | Replay every W11+ `request_id` from CSV and write array artifact. |
| 21 | W1 | KS-DIFY-ECS-011 | done | ~~FAIL~~ → **RESOLVED 2026-05-14** | ~~Dry-run is blocked by dirty `clean_output`; mirror push is not currently accepted.~~ Closed by **KS-FIX-02**: clean worktree committed (`22ea484`), strict dry-run + apply path real-run, artifact `ecs_mirror_dryrun_KS-FIX-02.json` status=`dry_run_strict_pass` diff_count=0. | ~~Clean the worktree and run real mirror dry-run / apply path.~~ Done. |
| 22 | W13 | KS-CD-001 | not_started | BLOCKED | `act` is missing; PG-backed release gate items are blocked by database access / role issues. | Use a real CI runner, fix PG user/database, and write artifacts for each hard gate. |
| 23 | W8 | KS-CD-002 | done | FAIL | Raw command contains `<run_id>` placeholder and fails; PG / Qdrant rollback has not been exercised. | Use a real `compile_run_id`, run staging rollback, then rerun smoke. |
| 24 | W14 | KS-PROD-001 | not_started | BLOCKED | Regression script is missing / not runnable, so S1-S13 production regression is not started. | Implement and run full S1-S13 regression. |
| 25 | W12 | KS-PROD-002 | not_started | FAIL / BLOCKED | Command path is broken; e2e file uses TestClient; commit evidence is local gate, not staging e2e. | Fix command, replace TestClient with real `requests.post(API_BASE_URL, ...)`, and exercise Qdrant / PG / Dify / ECS. |
| 26 | W8 | KS-RETRIEVAL-007 | done | CONDITIONAL_PASS | DoD §11 reviewer-pass item remains unchecked though code/test path is ready. | Check DoD after formal reviewer pass, or record the W8 conditional-to-pass decision. |

## Keep Done But Track Production Evidence

These cards can keep `done`, but should remain visible until their production evidence is linked:

- KS-COMPILER-010: policy-level rerank declaration is done; runtime rerank belongs to the live retrieval path.
- KS-POLICY-005: model policy is structurally valid; staging env snapshot is still required.
- KS-VECTOR-001: chunks exist and validate; current staging embedding rebuild proof is still required.
- KS-DIFY-ECS-002: reconcile evidence is valid only as a decision to keep legacy PG out of the serving trust chain.
- KS-DIFY-ECS-009: guardrail unit evidence is valid; Dify staging integration is pending.
- KS-RETRIEVAL-007: implementation is ready; DoD reviewer checkbox must be closed.
