# Backend Auth / Users Structure Audit

Date: 2026-04-13
Scope: `D:\finos\backend`
Mode: Read-only audit findings captured as documentation

This report audits the current auth, users, roles, permissions, and dashboard-related structure in the Finqor backend. It does not include code changes.

## Structure Map

- [backend/financeops/db/models/users.py](/d:/finos/backend/financeops/db/models/users.py:14): `model` - `UserRole`, `IamUser`, `IamSession`; this is the main identity file and it mixes platform and org roles in one enum/model.
- [backend/financeops/db/models/auth_tokens.py](/d:/finos/backend/financeops/db/models/auth_tokens.py:1): `model` - MFA recovery codes and password reset tokens.
- [backend/financeops/services/auth_service.py](/d:/finos/backend/financeops/services/auth_service.py:1): `service` - login, MFA, token issuance/refresh, logout, JWT claims, `/me`-adjacent auth logic.
- [backend/financeops/services/user_service.py](/d:/finos/backend/financeops/services/user_service.py:1): `service` - tenant user lifecycle, lookup, role update, offboarding.
- [backend/financeops/core/auth.py](/d:/finos/backend/financeops/core/auth.py:21): `mixed` - another auth helper layer with `get_current_user`, role checks, MFA requirement.
- [backend/financeops/api/__init__.py](/d:/finos/backend/financeops/api/__init__.py:95): `mixed` - older duplicate dependency/auth helper layer.
- [backend/financeops/api/deps.py](/d:/finos/backend/financeops/api/deps.py:167): `mixed` - current dependency layer: session deps, auth, role guards, entitlement checks, permission dependency factory.
- [backend/financeops/api/v1/auth.py](/d:/finos/backend/financeops/api/v1/auth.py:1): `mixed` - auth router plus inline request models; registration, MFA, password reset, refresh/logout, `/me`, `entity-roles`.
- [backend/financeops/api/v1/users.py](/d:/finos/backend/financeops/api/v1/users.py:1): `router` - offboarding endpoint.
- [backend/financeops/api/v1/platform_users.py](/d:/finos/backend/financeops/api/v1/platform_users.py:26): `mixed` - platform-user router, platform-role helpers, platform-tenant distinction, invite/provision flow.
- [backend/financeops/api/v1/tenants.py](/d:/finos/backend/financeops/api/v1/tenants.py:49): `mixed` - tenant profile, tenant user invites/role changes, credits, display preferences.
- [backend/financeops/api/v1/schemas/auth_responses.py](/d:/finos/backend/financeops/api/v1/schemas/auth_responses.py:1): `schema` - typed auth response models.
- [backend/financeops/api/v1/router.py](/d:/finos/backend/financeops/api/v1/router.py:1): `router` - top-level API aggregator wiring auth/users/platform routes.
- [backend/financeops/seed/platform_owner.py](/d:/finos/backend/financeops/seed/platform_owner.py:16): `bootstrap/service` - seeds platform tenant and platform users into the same `IamUser` table.
- [backend/financeops/platform/db/models/user_membership.py](/d:/finos/backend/financeops/platform/db/models/user_membership.py:13): `model` - org/entity assignments for users.
- [backend/financeops/platform/db/models/user_role_assignments.py](/d:/finos/backend/financeops/platform/db/models/user_role_assignments.py:13): `model` - contextual RBAC user-role assignments.
- [backend/financeops/platform/db/models/roles.py](/d:/finos/backend/financeops/platform/db/models/roles.py:12): `model` - DB-backed roles.
- [backend/financeops/platform/db/models/permissions.py](/d:/finos/backend/financeops/platform/db/models/permissions.py:9): `model` - DB-backed permissions.
- [backend/financeops/platform/db/models/role_permissions.py](/d:/finos/backend/financeops/platform/db/models/role_permissions.py:12): `model` - DB-backed role-permission grants.
- [backend/financeops/platform/schemas/rbac.py](/d:/finos/backend/financeops/platform/schemas/rbac.py:1): `schema` - RBAC request/response models.
- [backend/financeops/platform/services/tenancy/entity_access.py](/d:/finos/backend/financeops/platform/services/tenancy/entity_access.py:1): `service` - entity scoping for users.
- [backend/financeops/platform/services/rbac/user_plane.py](/d:/finos/backend/financeops/platform/services/rbac/user_plane.py:8): `service` - maps runtime `UserRole` values into a tenant-role abstraction.
- [backend/financeops/platform/services/rbac/permission_matrix.py](/d:/finos/backend/financeops/platform/services/rbac/permission_matrix.py:46): `service/config` - static permission matrix and role aliases.
- [backend/financeops/platform/services/rbac/permission_engine.py](/d:/finos/backend/financeops/platform/services/rbac/permission_engine.py:98): `service` - static permission evaluator and FastAPI dependency helpers.
- [backend/financeops/platform/services/rbac/evaluator.py](/d:/finos/backend/financeops/platform/services/rbac/evaluator.py:1): `service` - DB-backed RBAC evaluator.
- [backend/financeops/platform/services/rbac/permission_service.py](/d:/finos/backend/financeops/platform/services/rbac/permission_service.py:1): `service` - permission CRUD/grants.
- [backend/financeops/platform/services/rbac/role_service.py](/d:/finos/backend/financeops/platform/services/rbac/role_service.py:1): `service` - role CRUD/assignment.
- [backend/financeops/platform/api/v1/roles.py](/d:/finos/backend/financeops/platform/api/v1/roles.py:1): `router` - RBAC admin API.
- [backend/financeops/platform/api/v1/control_plane.py](/d:/finos/backend/financeops/platform/api/v1/control_plane.py:422): `mixed` - workspace context, intents, jobs, airlock, timeline, determinism, lineage, impact, snapshots, audit pack.
- [backend/financeops/platform/services/enforcement/auth_modes.py](/d:/finos/backend/financeops/platform/services/enforcement/auth_modes.py:1): `service/config` - route auth-mode grouping.
- [backend/financeops/platform/services/enforcement/control_plane_authorizer.py](/d:/finos/backend/financeops/platform/services/enforcement/control_plane_authorizer.py:1): `service` - control-plane authorization orchestration.
- [backend/financeops/modules/erp_sync/policies/permissions.py](/d:/finos/backend/financeops/modules/erp_sync/policies/permissions.py:3): `config` - module-local permission constants.
- [backend/financeops/modules/payment/policies/permissions.py](/d:/finos/backend/financeops/modules/payment/policies/permissions.py:3): `config` - module-local permission constants.

## Separation Of Concerns

- There is not a clean identity split.
- There is one user model: [IamUser in users.py](/d:/finos/backend/financeops/db/models/users.py:29).
- Platform users are not a separate model or table; they are `IamUser` rows under [a special platform tenant in platform_users.py](/d:/finos/backend/financeops/api/v1/platform_users.py:28>) and seeded the same way in [seed/platform_owner.py](/d:/finos/backend/financeops/seed/platform_owner.py:16>).
- There is no `is_platform_user` or `is_superuser` field on `IamUser`; `is_platform_user` exists only as [a router helper](/d:/finos/backend/financeops/api/v1/platform_users.py:57>), and “superuser” is just the `super_admin` enum value in [UserRole](/d:/finos/backend/financeops/db/models/users.py:15>).

## Dashboard Summary

- There is no single backend “dashboard module” for the normal product home.
- There are feature-specific dashboards, for example partner, working capital, compliance, debt covenants, and service registry.
- The normal frontend home page at [frontend/app/(dashboard)/dashboard/HomePageClient.tsx](/d:/finos/frontend/app/(dashboard)/dashboard/HomePageClient.tsx:269>) composes data from:
- `/api/v1/erp/connectors` via [listErpConnectors](/d:/finos/frontend/app/(dashboard)/dashboard/HomePageClient.tsx:270>)
- `/api/v1/anomalies` via [fetchAnomalyAlerts](/d:/finos/frontend/app/(dashboard)/dashboard/HomePageClient.tsx:290>)
- `/api/v1/accounting/journals` via [listJournals](/d:/finos/frontend/app/(dashboard)/dashboard/HomePageClient.tsx:278>)
- `/api/v1/platform/control-plane/context` for workspace tabs/context via [ModuleTabs](/d:/finos/frontend/components/layout/ModuleTabs.tsx:18>) and [getControlPlaneContext](/d:/finos/frontend/lib/api/control-plane.ts:274>)
- The backend “control plane” context is not platform-staff-only; it is guarded by [require_finance_team in control_plane.py](/d:/finos/backend/financeops/platform/api/v1/control_plane.py:426>), so it is really tenant-user workspace context.

## Findings

Finding: Platform users and org users share one identity model and one role enum.  
File: [backend/financeops/db/models/users.py](/d:/finos/backend/financeops/db/models/users.py:14>)  
Issue: `UserRole` contains both platform and tenant roles, and `IamUser` is the single table for both. The platform/org boundary is not modeled at the identity layer.  
Severity: HIGH

Finding: Platform-user status is derived in router code, not in the model layer.  
File: [backend/financeops/api/v1/platform_users.py](/d:/finos/backend/financeops/api/v1/platform_users.py:28>)  
Issue: The distinction depends on `PLATFORM_TENANT_ID` plus `_is_platform_user()`. That is a critical business rule living in one router instead of a shared identity service/model.  
Severity: HIGH

Finding: Auth/dependency logic exists in three overlapping layers.  
File: [backend/financeops/api/deps.py](/d:/finos/backend/financeops/api/deps.py:167>), [backend/financeops/api/__init__.py](/d:/finos/backend/financeops/api/__init__.py:95>), [backend/financeops/core/auth.py](/d:/finos/backend/financeops/core/auth.py:21>)  
Issue: All three define overlapping `get_current_user` and role-check helpers. That creates drift risk and makes it unclear which layer is authoritative.  
Severity: HIGH

Finding: Authorization has two parallel RBAC systems.  
File: [backend/financeops/platform/services/rbac/permission_matrix.py](/d:/finos/backend/financeops/platform/services/rbac/permission_matrix.py:46>), [backend/financeops/platform/services/rbac/permission_engine.py](/d:/finos/backend/financeops/platform/services/rbac/permission_engine.py:98>), [backend/financeops/platform/services/rbac/evaluator.py](/d:/finos/backend/financeops/platform/services/rbac/evaluator.py:1>)  
Issue: There is a static permission matrix/engine and a separate DB-backed RBAC engine. They can diverge, and the static engine is not clearly demoted to legacy/bootstrap only.  
Severity: HIGH

Finding: The static permission engine still allows legacy pass-through.  
File: [backend/financeops/platform/services/rbac/permission_engine.py](/d:/finos/backend/financeops/platform/services/rbac/permission_engine.py:98>)  
Issue: `require_permission(..., strict=False)` logs an `allow_legacy` path instead of being a hard deny, so policy enforcement is not a single crisp contract.  
Severity: HIGH

Finding: Three role vocabularies coexist.  
File: [backend/financeops/db/models/users.py](/d:/finos/backend/financeops/db/models/users.py:14>), [backend/financeops/platform/services/rbac/user_plane.py](/d:/finos/backend/financeops/platform/services/rbac/user_plane.py:8>), [backend/financeops/platform/db/models/roles.py](/d:/finos/backend/financeops/platform/db/models/roles.py:12>)  
Issue: Runtime `UserRole`, derived `TenantRole`, and DB `CpRole` are separate concepts with overlapping meaning. That makes permission debugging and onboarding harder than it should be.  
Severity: MEDIUM

Finding: Role checks are still scattered across feature routers.  
File: [backend/financeops/modules/accounting_layer/api/routes.py](/d:/finos/backend/financeops/modules/accounting_layer/api/routes.py:74>), [backend/financeops/modules/compliance/api/routes.py](/d:/finos/backend/financeops/modules/compliance/api/routes.py:90>), [backend/financeops/modules/backup/api/routes.py](/d:/finos/backend/financeops/modules/backup/api/routes.py:31>), [backend/financeops/modules/erp_integration/api/routes.py](/d:/finos/backend/financeops/modules/erp_integration/api/routes.py:29>)  
Issue: Even with central deps, many routers still define local `_require_*` or `_assert_*` helpers using raw `UserRole` comparisons.  
Severity: MEDIUM

Finding: The auth router is too broad for one file.  
File: [backend/financeops/api/v1/auth.py](/d:/finos/backend/financeops/api/v1/auth.py:1>)  
Issue: Registration, tenant bootstrap, MFA, password reset, refresh/logout, `/me`, and entity-role lookup all live together, along with inline request models.  
Severity: MEDIUM

Finding: The tenant router is also a grab-bag of unrelated concerns.  
File: [backend/financeops/api/v1/tenants.py](/d:/finos/backend/financeops/api/v1/tenants.py:49>)  
Issue: Tenant profile, tenant-user invites/role changes, entity assignment, credits, and display preferences are coupled in one file.  
Severity: MEDIUM

Finding: The “platform control plane” file is actually serving normal tenant dashboard context too.  
File: [backend/financeops/platform/api/v1/control_plane.py](/d:/finos/backend/financeops/platform/api/v1/control_plane.py:422>)  
Issue: Its folder/name suggests internal platform governance, but it provides workspace tabs/current entity/current module for the regular dashboard and is guarded by `require_finance_team`, not platform-only auth.  
Severity: MEDIUM

Finding: There is no single backend owner for the home dashboard.  
File: [frontend/app/(dashboard)/dashboard/HomePageClient.tsx](/d:/finos/frontend/app/(dashboard)/dashboard/HomePageClient.tsx:269>), [backend/financeops/platform/api/v1/control_plane.py](/d:/finos/backend/financeops/platform/api/v1/control_plane.py:422>)  
Issue: `/dashboard` is assembled client-side from ERP, anomalies, journals, and workspace-context endpoints. That works, but ownership is spread across modules instead of being explicit.  
Severity: MEDIUM

Finding: Platform admin/ops surfaces are buried under business-module locations.  
File: [backend/financeops/modules/service_registry/api/routes.py](/d:/finos/backend/financeops/modules/service_registry/api/routes.py:85>), [backend/financeops/modules/backup/api/routes.py](/d:/finos/backend/financeops/modules/backup/api/routes.py:49>), [backend/financeops/api/v1/admin_ai_providers.py](/d:/finos/backend/financeops/api/v1/admin_ai_providers.py:1>)  
Issue: Operational control-plane endpoints are not grouped together, which makes permission review and ownership discovery harder.  
Severity: MEDIUM

## Verdict

Yes, the architect is basically right.

The folder structure is not catastrophic, but the auth/identity boundary is genuinely problematic for a production SaaS. The core issue is not “too many files”; it is that platform identity, org identity, RBAC, and dashboard/control-plane concerns do not have one obvious source of truth. The biggest real risks if left as-is are permission drift, platform-vs-tenant confusion, accidental privilege mistakes during new feature work, and slower incident/debug response because engineers have to reason across multiple auth layers and two RBAC systems.

If this were an earlier-stage product, I’d call it acceptable debt. For a production multi-tenant finance platform, it is beyond “just cosmetic” and worth restructuring before the next big permissions or admin-surface expansion.

## Recommended Folder Structure

- Create a single `identity/` boundary and move current identity files under it.  
  Files: `db/models/users.py`, `db/models/auth_tokens.py`, `services/auth_service.py`, `services/user_service.py`, `api/v1/auth.py`, `api/v1/platform_users.py`, `api/v1/users.py`, `api/v1/schemas/auth_responses.py`  
  Effort: M  
  Alembic migration: No

- Consolidate auth/dependency helpers so only one dependency layer remains.  
  Files: `api/deps.py`, `api/__init__.py`, `core/auth.py`  
  Effort: S  
  Alembic migration: No

- Split `api/v1/auth.py` by concern into auth/session/profile endpoints under that same identity boundary.  
  Current concerns to separate: register/bootstrap, MFA, password reset, session lifecycle, `/me`, entity roles  
  Effort: M  
  Alembic migration: No

- Split `api/v1/tenants.py` into tenant profile, tenant users, credits, and display preferences.  
  Effort: M  
  Alembic migration: No

- Keep `platform/rbac/` as the single RBAC home and make the static matrix clearly compatibility/bootstrap only, or fold it into the DB-backed layer.  
  Files: `platform/db/models/*roles*`, `platform/db/models/*permissions*`, `platform/services/rbac/*`  
  Effort: M  
  Alembic migration: No

- Split `platform/api/v1/control_plane.py` into smaller modules by actual concern.  
  Current concerns present: workspace context, intents/jobs, airlock, timeline, determinism/lineage/impact, snapshots/audit pack  
  Effort: M  
  Alembic migration: No

- Group platform ops/admin surfaces together instead of burying them in business modules.  
  Files: `modules/service_registry/api/routes.py`, `modules/backup/api/routes.py`, `api/v1/admin_ai_providers.py`  
  Effort: S  
  Alembic migration: No

- Keep one `IamUser` table short-term, but create an explicit shared service for “platform user vs org user” classification so it is not router-local.  
  Effort: S  
  Alembic migration: No

- Optional long-term hard split into separate platform-user and org-user tables/models.  
  Why optional: this is the only change that truly enforces the boundary at the data model itself.  
  Effort: XL  
  Alembic migration: Yes
