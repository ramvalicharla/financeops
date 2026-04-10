# Beta Launch Note

## 1. Product Summary

FinanceOps is a financial control plane, not a general SaaS dashboard.

Core philosophy:
- intent before execution
- no silent changes
- backend authority
- UI = renderer

The product is designed to expose governed state, job progress, intake status, and traceability without letting the frontend act as an authority layer.

## 2. What Is Authoritative In Beta

The following are authoritative in the current beta contract:

- Onboarding setup for organization and entity creation through backend setup draft and confirm flows
- Control-plane context from `/context`
- Job lifecycle visibility from `/jobs`
- Airlock admission status from `/airlock`
- Lineage from backend-derived lineage responses
- Impact analysis from backend-derived impact responses
- Timeline from `/timeline`, with semantics metadata from `/timeline/semantics`

## 3. What Is Intentionally Limited

### Setup Scope

Only organization and entity creation are setup-intent-governed today.

The rest of onboarding still uses the existing backend flows. Module review is now visible in onboarding, but it is review-only and does not turn module enablement into a setup-intent execution path.

### Module Enablement

Module enablement is not yet intent-governed.

It still uses the direct backend module API. Validation is performed before enabling, but the change is not reviewable in the same way as org/entity setup drafts.

### Initial Upload

Initial upload uses the existing airlock ingestion path.

It is not part of the setup-intent chain yet. Uploads are now tagged with onboarding metadata so the origin is visible in airlock views.

### Current Module Selection

Current module is derived from backend workspace context.

It is validated by the backend request contract, but it is not persisted as a user preference yet.

### Job Retry

Job retry is not supported.

The UI reflects the backend capability contract correctly and does not expose fake retry behavior.

## 4. User Experience Expectations

- No optimistic UI for governed state
- Some flows are confirmation-based
- Some actions are unavailable by design
- The system prioritizes correctness over speed

## 5. Known Gaps

- Setup intent does not yet cover module enablement or initial upload execution
- Module enablement remains direct-backend and not reviewable
- Current module selection is validated, not persisted
- Retry is explicitly unsupported in the current backend contract

## 6. Safe Usage Guidance

- Do not assume retries exist
- Validate onboarding completion through UI confirmation backed by backend refresh
- Trust backend state over intermediate UI transitions
- Treat module review in onboarding as read-only confirmation, not as intent execution

## 7. Next Phase

P1.3 / P2 will extend intent coverage, job controls, and persistence where backend contracts are ready.

This note does not imply those extensions are already available in beta.
