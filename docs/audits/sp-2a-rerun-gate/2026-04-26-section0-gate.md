# SP-2A Re-Run — Section 0 Gate Report

**Date:** 2026-04-26  
**Branch:** feat/sp-2a-orgswitcher-repurpose  
**Base commit:** 0ea41da  

---

## Check 1 — SwitchOrgResponse nested shape

```
backend/financeops/api/v1/users.py:415:class SwitchOrgResponse(BaseModel):
backend/financeops/api/v1/users.py:417:    target_org: SwitchTargetOrg
backend/financeops/api/v1/users.py:441:@router.post("/users/me/orgs/{tenant_id}/switch", response_model=SwitchOrgResponse)
backend/financeops/api/v1/users.py:446:) -> SwitchOrgResponse:
backend/financeops/api/v1/users.py:448:    return SwitchOrgResponse(
backend/financeops/api/v1/users.py:450:        target_org=SwitchTargetOrg(
```

**Result:** PASS — response has nested `target_org: { id, name, role }`, NOT a flat shape.

---

## Check 2 — ViewingAsBanner hardcoded copy

```
frontend/components/layout/ViewingAsBanner.tsx:60:              · Read-only · 15 min token
```

**Result:** PASS — "Read-only · 15 min token" copy is still hardcoded at line 60.

---

## Check 3 — enterSwitchMode signature in tenant.ts

```
frontend/lib/store/tenant.ts:38:  enterSwitchMode: (params: {
frontend/lib/store/tenant.ts:96:      enterSwitchMode: ({ switch_token, tenant_id, tenant_name, tenant_slug }) =>
```

**Result:** PASS — `enterSwitchMode` signature still takes `{ switch_token, tenant_id, tenant_name, tenant_slug? }`.

---

## Additional finding — orgs.ts already exists (baseline only)

`frontend/lib/api/orgs.ts` exists with 3 exports (`SubscriptionTier`, `OrgSummary`, `listUserOrgs`). The SP-2A additions (SP-2A switchable orgs types and functions) are NOT present. This is the expected pre-SP-2A state. Additive work will be safe.

---

## Verdict: PROCEED

All three gate checks pass. Situation is unchanged from the spec description. Proceeding to Section 1 (switch_mode discriminator in tenant store).
