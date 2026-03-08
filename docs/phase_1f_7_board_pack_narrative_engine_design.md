# Phase 1F.7 — Board Pack & Narrative Engine Design

## Scope
- Add a deterministic, append-only, tenant-isolated board-pack assembly module.
- Build only on frozen upstream outputs:
  - `ratio_variance_engine`
  - `financial_risk_engine`
  - `anomaly_pattern_engine`
- No mutation of upstream rows and no journal/engine writes.

## Module
- Path: `backend/financeops/modules/board_pack_narrative_engine/`
- Layers:
  - `domain`: enums, value objects, invariants, entities
  - `application`: validation, inclusion, section assembly, narrative assembly, run orchestration
  - `infrastructure`: repository, token builder
  - `api`: schemas and routes
  - `policies`: control-plane dependency (`module_code=board_pack_narrative_engine`)

## Database Objects
- Migration: `0019_phase1f7_board_pack_narrative`
- Tables:
  - `board_pack_definitions`
  - `board_pack_section_definitions`
  - `narrative_templates`
  - `board_pack_inclusion_rules`
  - `board_pack_runs`
  - `board_pack_results`
  - `board_pack_section_results`
  - `board_pack_narrative_blocks`
  - `board_pack_evidence_links`
- Supersession triggers on 4 versioned registries.
- RLS `ENABLE` + `FORCE` on all tables.
- Append-only triggers on all tables.

## Deterministic Runtime
- `run_token` hash inputs:
  - tenant/org/reporting_period
  - definition/section/template/inclusion version-token aggregates
  - source metric/risk/anomaly run IDs
  - status
- Stable ordering:
  - sections: `section_order`, `section_code`, `id`
  - narrative blocks: section + `block_order`, `id`
  - evidence: board-attention desc, severity desc, `id`

## API Surface
- Definition registries:
  - `POST/GET /board-pack/definitions`
  - `GET /board-pack/definitions/{id}/versions`
  - `POST/GET /board-pack/sections`
  - `GET /board-pack/sections/{id}/versions`
  - `POST/GET /board-pack/narrative-templates`
  - `GET /board-pack/narrative-templates/{id}/versions`
  - `POST/GET /board-pack/inclusion-rules`
  - `GET /board-pack/inclusion-rules/{id}/versions`
- Runs/results:
  - `POST /board-pack/runs`
  - `POST /board-pack/runs/{id}/execute`
  - `GET /board-pack/runs/{id}`
  - `GET /board-pack/runs/{id}/summary`
  - `GET /board-pack/runs/{id}/sections`
  - `GET /board-pack/runs/{id}/narratives`
  - `GET /board-pack/runs/{id}/evidence`

## Security/Governance
- Control-plane required for all endpoints:
  - valid context token
  - module enabled
  - RBAC check
  - quota/routing checks
- Suggested permissions:
  - `board_pack_run`
  - `board_pack_view`
  - `board_pack_definition_manage`
  - `board_pack_section_manage`
  - `board_pack_template_manage`
  - `board_pack_inclusion_rule_manage`
  - `board_pack_evidence_view`
