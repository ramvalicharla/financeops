Backend API Availability Audit
Category: Journal API
Endpoint	Status	Backend Evidence	Frontend Client	Request Schema	Response Schema	Notes
GET /api/v1/accounting/journals	EXISTS	Route re-export in accounting_layer.py (line 3), mounted under /accounting in router.py (line 114), app mounted in main.py (line 458), handler list_journals_endpoint at routes.py (line 330)	accounting-journals.ts (line 79)	Query params in handler: org_entity_id, status, limit, offset	Identifiable as list[JournalResponse] from service return and dump; schema in schemas.py (line 221)	Guarded by journal_view_guard
GET /api/v1/accounting/journals/{id}	EXISTS	Handler get_journal_endpoint at routes.py (line 496), same mount chain as above	accounting-journals.ts (line 92)	Path param journal_id	JournalResponse in schemas.py (line 221)	Guarded by journal_view_guard
POST /api/v1/accounting/journals	EXISTS	Handler create_journal_endpoint at routes.py (line 305), same mount chain	accounting-journals.ts (line 65)	JournalCreate in schemas.py (line 189)	GovernedMutationResponse built in routes.py (line 168), schema in schemas.py (line 246)	Real implementation submits intent through IntentService; not a stub
POST /api/v1/accounting/journals/{id}/submit	EXISTS	Handler submit_journal_endpoint at routes.py (line 442)	accounting-journals.ts (line 109)	No body schema; empty payload	GovernedMutationResponse	Guarded by journal_submit_guard
POST /api/v1/accounting/journals/{id}/approve	EXISTS	Handler approve_journal_endpoint at routes.py (line 354)	accounting-journals.ts (line 99)	No body schema; empty payload	GovernedMutationResponse	Also enforces _can_approve role check
POST /api/v1/accounting/journals/{id}/post	EXISTS	Handler post_journal_endpoint at routes.py (line 382)	accounting-journals.ts (line 129)	No body schema; empty payload	GovernedMutationResponse	Also enforces _can_post
POST /api/v1/accounting/journals/{id}/reverse	EXISTS	Handler reverse_journal_endpoint at routes.py (line 414)	accounting-journals.ts (line 139)	No body schema; empty payload	GovernedMutationResponse	Also enforces _can_post
Findings
All requested journal endpoints are truly implemented and mounted.
The frontend journal client already consumes all requested endpoints.
There is one extra mounted transition the frontend also uses: POST /api/v1/accounting/journals/{id}/review at routes.py (line 468).
Missing / Partial Endpoints
None from the requested journal set.
Action Items
Frontend can build journal list/detail/create/submit/approve/post/reverse now against real APIs.
Category: COA / Accounts API
Endpoint	Status	Backend Evidence	Frontend Client	Request Schema	Response Schema	Notes
GET /api/v1/coa/accounts	EXISTS	Router prefix /coa in routes.py (line 78), app mounted directly in main.py (line 493), handler get_effective_accounts at routes.py (line 259), route signature at routes.py (line 259)	coa.ts (line 282)	Query params: template_id, group_code, subgroup_code, include_inactive	list[CoaLedgerAccountResponse] at schemas.py (line 19)	Real resolver call through TenantCoaResolver.resolve_accounts(...)
GET /api/v1/coa/accounts?search=...	PARTIAL	Same mounted route exists, but handler at routes.py (line 260) defines no search query param	No frontend client method with search; current helper only sends template_id, group_code, subgroup_code, include_inactive in coa.ts (line 268)	No search request contract found	Same as above	Exact search behavior is not implemented
Findings
GET /api/v1/coa/accounts is real and mounted.
Search-by-query on that endpoint is not implemented.
The journal creation UI does not currently use this endpoint for account selection; it uses /api/v1/coa/tenant/accounts from coa.ts (line 372), so /coa/accounts is not the current journal autocomplete dependency.
CoaLedgerAccountResponse returns id, code, name, and classification metadata, but not the tenant-facing account_code/display_name shape the journal form currently consumes.
Missing / Partial Endpoints
GET /api/v1/coa/accounts?search=... — MEDIUM
Why it matters: if frontend wants server-side autocomplete on this exact endpoint, it cannot rely on it today.
Action Items
Add search support if /coa/accounts is meant to back autocomplete.
Otherwise keep journal form on tenant COA endpoints and document the distinction.
Negative evidence

Searched backend/financeops/modules/coa/api, frontend/lib/api/coa.ts, and frontend/app/(dashboard)/accounting/journals/new/PageClient.tsx.
Search terms used: coa/accounts, search, account_code, tenant_coa_account_id.
Files examined without a search parameter on the endpoint: routes.py, coa.ts.
Category: Job Control API
Endpoint	Status	Backend Evidence	Frontend Client	Request Schema	Response Schema	Notes
GET /api/v1/platform/control-plane/jobs	EXISTS	/platform mount in router.py (line 327), /control-plane mount in init.py:25 (line 25), handler list_jobs_endpoint at control_plane.py (line 520), app mount in main.py (line 458)	control-plane.ts (line 324)	Query params: entity_id, status, limit	Identifiable from _serialize_job at control_plane.py (line 131) and frontend ControlPlaneJob at control-plane.ts (line 59)	Real query over CanonicalJob + CanonicalIntent
POST /api/v1/platform/control-plane/jobs/{job_id}/retry	MISSING	No such handler found in control_plane.py; _serialize_job explicitly marks retry unsupported at control_plane.py (line 132)	No retry client method in control-plane.ts	None	None	There is a different ERP-sync-specific retry route at ops.py (line 339), but it is not the requested generic control-plane job retry API
Findings
Job listing exists and is mounted.
Generic control-plane retry does not exist.
Backend intentionally exposes retry metadata only: supported: false, allowed: false, reason: "Not supported in current backend contract".
Missing / Partial Endpoints
POST /api/v1/platform/control-plane/jobs/{job_id}/retry — HIGH
Why it matters: frontend can display retry state but cannot perform generic retry from the control-plane jobs surface.
Action Items
Build generic retry endpoint if retry UX is required.
Or keep retry hidden except for module-specific flows.
Negative evidence

Searched backend/financeops/platform/api/v1, backend/financeops/core, and frontend/lib/api/control-plane.ts.
Search terms used: retry, /jobs/.../retry, retry_count, max_retries.
Files examined without the requested endpoint: control_plane.py, control-plane.ts.
Category: Job Progress Support
Endpoint / Contract	Status	Backend Evidence	Frontend Client	Request Schema	Response Schema	Notes
Progress fields on GET /api/v1/platform/control-plane/jobs	PARTIAL	_serialize_job at control_plane.py (line 131) returns status/timestamps/retry/error fields only	ControlPlaneJob at control-plane.ts (line 59) models no progress, percent_complete, progress_percent, eta, or current_step	N/A	No progress fields in contract	Frontend can render status only, not a real progress bar
Findings
No audited job API exposes real progress fields.
The current control-plane jobs contract supports only indeterminate execution state: queued/running/failed timestamps and retry counters.
Missing / Partial Endpoints
Job progress fields on current jobs API — MEDIUM
Why it matters: frontend can only show spinner/indeterminate state, not percentage or step progress.
Action Items
Add progress fields to the job serializer if product needs real progress UI.
Negative evidence

Searched backend/financeops/platform/api/v1/control_plane.py, backend/financeops/core, frontend/lib/api/control-plane.ts, and control-plane frontend components.
Search terms used: progress, percent_complete, progress_percent, eta, current_step.
Files examined without those fields: control_plane.py, control-plane.ts.
Category: Determinism / Report Hash API
Endpoint	Status	Backend Evidence	Frontend Client	Request Schema	Response Schema	Notes
GET /api/v1/reports/{report_id}/determinism	MISSING	No mounted route in custom_report_builder/routes.py; reports router is mounted in main.py (line 460) but exposes /run, /runs/{id}, /runs/{id}/result instead	No client method in report-builder.ts	None	None	Alternative exists: generic control-plane determinism GET /api/v1/platform/control-plane/determinism?subject_type=...&subject_id=... at control_plane.py (line 695) and control-plane.ts (line 418)
GET /api/v1/reports/{report_id}/snapshots	MISSING	No mounted route in custom_report_builder/routes.py	No client method in report-builder.ts	None	None	Alternative exists: generic control-plane snapshots GET /api/v1/platform/control-plane/snapshots?... at control_plane.py (line 777) and control-plane.ts (line 450)
Findings
The exact report-specific determinism and snapshot endpoints are missing.
Real determinism evidence is still implemented:
report run response includes determinism_hash and snapshot_refs in custom_report_builder/routes.py:125 (line 125) and custom_report_builder/routes.py:218 (line 218)
report result response includes result_hash and snapshot_refs in custom_report_builder/routes.py:145 (line 145) and custom_report_builder/routes.py:471 (line 471)
Frontend mismatch: report types only expose result_hash, not determinism_hash / snapshot_refs, in report-builder.ts (line 100).
Missing / Partial Endpoints
GET /api/v1/reports/{report_id}/determinism — MEDIUM
GET /api/v1/reports/{report_id}/snapshots — MEDIUM
Action Items
Either build report-specific convenience endpoints, or have frontend use the generic control-plane determinism/snapshot APIs.
Update frontend report run/result types to include backend-returned determinism fields already available today.
Negative evidence

Searched backend/financeops/modules/custom_report_builder, backend/financeops/platform/api/v1/control_plane.py, frontend/lib/api/report-builder.ts, and reports pages.
Search terms used: determinism, snapshot, result_hash, report_id, /reports/.../determinism, /reports/.../snapshots.
Files examined without the requested endpoints: custom_report_builder/routes.py, report-builder.ts.
Category: Timeline / Lineage API
Endpoint	Status	Backend Evidence	Frontend Client	Request Schema	Response Schema	Notes
GET /api/v1/timeline/{object_type}/{object_id}	MISSING	No such mounted path found; control-plane timeline is query-param based at control_plane.py (line 640)	Frontend uses control-plane.ts (line 384)	None	None	Alternative: GET /api/v1/platform/control-plane/timeline?subject_type=...&subject_id=...
GET /api/v1/lineage/forward/{report_id}	MISSING	No forward path route found; generic lineage route at control_plane.py (line 739)	Frontend uses control-plane.ts (line 426)	None	None	Generic lineage response contains both forward and reverse graphs
GET /api/v1/lineage/reverse/{journal_id}	MISSING	Same as above	Frontend uses control-plane.ts (line 426)	None	None	Use generic control-plane lineage query
Findings
The exact unified path-shaped timeline and forward/reverse lineage endpoints are missing.
There is a real alternative API surface:
GET /api/v1/platform/control-plane/timeline
GET /api/v1/platform/control-plane/lineage
GET /api/v1/platform/control-plane/impact
Frontend can compose object timeline and lineage views from these existing control-plane endpoints.
Missing / Partial Endpoints
GET /api/v1/timeline/{object_type}/{object_id} — MEDIUM
GET /api/v1/lineage/forward/{report_id} — MEDIUM
GET /api/v1/lineage/reverse/{journal_id} — MEDIUM
Action Items
Frontend should use existing control-plane timeline/lineage APIs now.
Add path-shaped convenience routes only if product requires those exact REST shapes.
Negative evidence

Searched backend/financeops/platform/api/v1, backend/financeops, and frontend/lib/api/control-plane.ts.
Search terms used: timeline, lineage, forward, reverse, timeline/{, lineage/forward, lineage/reverse.
Files examined without the requested paths: control_plane.py, control-plane.ts.
Category: Period Close API
Endpoint	Status	Backend Evidence	Frontend Client	Request Schema	Response Schema	Notes
GET /api/v1/monthend/	EXISTS	Mounted under /monthend in router.py (line 310), app mount via main.py (line 458), handler list_monthend_checklists at monthend.py (line 108)	No frontend client under frontend/lib/api calls this path	Query params: entity_name, checklist_status, limit, offset	Inline dict response: { checklists: [...], count } in monthend.py (line 118)	Read access uses get_current_user
GET /api/v1/monthend/{id}	EXISTS	Handler get_monthend_checklist at monthend.py (line 141)	No frontend client under frontend/lib/api calls this path	Path param checklist_id	Inline dict response with tasks, closed_at, created_at in monthend.py (line 149)	Read access uses get_current_user
POST /api/v1/monthend/{id}/close	PARTIAL	Handler close_monthend_checklist at monthend.py (line 237)	No frontend client under frontend/lib/api calls this path	CloseChecklistRequest in monthend.py (line 61)	Inline dict response includes checklist_id, status, closed_at, intent_id, job_id in monthend.py (line 252)	closed_at is exposed, closed_by is not exposed even though model tracks it at monthend.py model:35 (line 35)
Findings
All requested /monthend endpoints are mounted and implemented.
closed_at is returned on detail and close.
closed_by exists in the DB model and service layer, but is not returned by the route response.
The current frontend close workflow does not use /api/v1/monthend/*; it uses /api/v1/close/* from close-governance.ts.
Missing / Partial Endpoints
POST /api/v1/monthend/{id}/close — MEDIUM
Why it matters: frontend cannot identify the closing actor from the public API response.
Action Items
Add closed_by to month-end detail and close responses if UI needs attribution.
Decide whether frontend should stay on /close/* or move to /monthend/*; right now they are different APIs.
Negative evidence / contract mismatch

Searched frontend/lib/api, frontend/app, and backend monthend files.
Search terms used: monthend, checklist, close, closed_at, closed_by.
Frontend files examined without /api/v1/monthend client usage: close-governance.ts, close checklist pages under frontend/app/(dashboard)/close.
Final Summary
1. Launch-critical verdict
Mostly supported, blocked in specific places.

What is fully backend-supported now:

Journal CRUD-like governed flows the frontend already expects
Control-plane jobs listing
Generic control-plane timeline, lineage, determinism, snapshots, impact, audit pack
Month-end checklist list/detail/close at /api/v1/monthend/*
Generic COA accounts list
What is blocked or incomplete:

Generic control-plane job retry action
Real job progress fields
Exact report-specific determinism/snapshot endpoints
Exact path-shaped timeline/lineage endpoints
COA search on /api/v1/coa/accounts
closed_by missing from month-end close responses
Frontend/backend contract mismatch on report determinism fields and close-vs-monthend API usage
2. Exact missing backend items
POST /api/v1/platform/control-plane/jobs/{job_id}/retry — missing
Job progress fields on control-plane jobs (progress, percent_complete, progress_percent, eta, current_step) — missing
GET /api/v1/reports/{report_id}/determinism — missing
GET /api/v1/reports/{report_id}/snapshots — missing
GET /api/v1/timeline/{object_type}/{object_id} — missing
GET /api/v1/lineage/forward/{report_id} — missing
GET /api/v1/lineage/reverse/{journal_id} — missing
search support on GET /api/v1/coa/accounts — missing
closed_by in /api/v1/monthend/{id} and /api/v1/monthend/{id}/close responses — missing field exposure
3. Frontend-safe build guidance
Frontend can build now against real APIs:

Journals list/detail/create/submit/approve/post/reverse
Control-plane jobs list, timeline, lineage, impact, determinism, snapshots, audit pack
Reports and board-packs using their existing run/result APIs
Month-end checklist views if frontend chooses to use /api/v1/monthend/*
Read-only COA account listing
Should use adapters or limited UI for now:

Job retry buttons
Job progress bars
Report-specific determinism/snapshot convenience views
Path-shaped timeline/lineage routes if those exact URLs are required
COA server-side search/autocomplete on /api/v1/coa/accounts
Must wait for backend work if exact contract is required:

Generic job retry mutation
Progress-rich job telemetry
Report-specific determinism and snapshots routes
closed_by attribution in month-end close responses
Search-capable /coa/accounts if that endpoint is intended for autocomplete