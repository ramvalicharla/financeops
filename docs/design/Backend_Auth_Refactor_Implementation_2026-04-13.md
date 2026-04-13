# Backend Auth Refactor Implementation

Date: 2026-04-13
Scope: `D:\finos\backend`
Checkpoint: Auth / platform identity / dependency-layer consolidation

## Summary

`1068/1068` tests passing. Clean checkpoint reported after the three auth-structure changes below.

## Final Summary Table

| Change | Files modified | Tests before | Tests after | Notes |
| --- | --- | ---: | ---: | --- |
| 1 - Fix `require_permission(strict=False)` pass-through | `platform/services/rbac/permission_engine.py` | 1050 | 1050 | `strict` default changed `False -> True`; branching removed; every failed check now raises `AuthorizationError`. Legacy `allow_legacy` log path gone. |
| 2 - Create shared `is_platform_user()` service | `services/platform_identity.py` (new), `api/v1/platform_users.py`, `api/v1/admin_ai_providers.py`, `modules/service_registry/api/routes.py`, `tests/unit/test_platform_identity.py` (new, 18 tests) | 1050 | 1068 | Single canonical `PLATFORM_TENANT_ID`, `is_platform_user`, `require_platform_user`, `require_platform_owner` - all raising `AuthorizationError`. Three local copies removed. |
| 3 - Consolidate 3 auth dependency layers | `api/deps.py` (`+require_role`, `+require_mfa`), `api/__init__.py` (shim), `core/auth.py` (shim) | 1068 | 1068 | `deps.py` is the single authoritative source. Both legacy files re-export from it. No duplicate logic remains across the three files. |

## Outcome

- Permission checks now fail closed by default.
- Platform-user detection is centralized behind one shared implementation.
- `api/deps.py` is now the single authoritative auth dependency layer.
- Legacy duplicate auth helpers were reduced to shims instead of parallel logic.

## Architectural Impact

These three changes directly reduce the highest-risk auth drift points identified in the audit:

- hidden pass-through authorization behavior
- duplicated platform-user classification
- duplicated `get_current_user` / role-helper implementations

The result is a clearer identity boundary, less router-local auth logic, and lower risk of future permission inconsistency.
