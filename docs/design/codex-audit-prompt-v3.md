🔒 CODEX AUDIT PROMPT — FINOPS PLATFORM (LOCKED)

Version 3.1 | 2026-04-07

🧾 TITLE

STRICT READ-ONLY AUDIT — FINOPS PLATFORM v1.0 (GOVERNANCE-FIRST)

⚠️ EXECUTION RULES (NON-NEGOTIABLE)
Rule	Description
READ-ONLY MODE	DO NOT MODIFY ANY FILES. Analyze only.
DO NOT ASSUME	ONLY REPORT WHAT EXISTS. Never imply missing features exist.
EVIDENCE REQUIRED	EVERY claim MUST include: file path, line numbers, function/class name, test (if exists)
MISSING means MISSING	If something is missing, say "MISSING". Not "partially" unless truly partial.
PARTIAL means PARTIAL	If partially implemented, state WHAT EXISTS and WHAT IS MISSING separately.
NO PRAISE	Do not praise code. Report facts.
NO SUMMARY WITHOUT EVIDENCE	Every summary claim must reference evidence from earlier sections.
NO SPECULATION	If evidence is not found → output "NO EVIDENCE FOUND". DO NOT infer behavior.
📏 SCOPE (MANDATORY)
INCLUDE:
- backend/
- frontend/
- docs/

EXCLUDE:
- node_modules/
- .next/
- dist/
- build/
- coverage/
- .git/
- venv/
- __pycache_/

IGNORE:
- generated files
- compiled assets
- minified code
🛑 STOP CONDITIONS
IF any of the below conditions occur, STOP immediately and report:

- Repository root not found
- Specification file not found at:
  D:\finos\docs\design\finops-ui-spec-v3.0.md
- Backend folder not found → "MISSING: BACKEND"
- Frontend folder not found → "MISSING: FRONTEND"
- No readable source files

DO NOT CONTINUE PARTIAL AUDIT AFTER STOP CONDITION
📂 CONTEXT INPUTS
D:\finos\docs\design\finops-ui-spec-v3.0.md
🔁 CROSS-CHECK REQUIREMENT (MANDATORY)
- If frontend implements a feature → verify backend supports it
- If backend implements a feature → verify frontend exposes it
- If mismatch found → mark as CRITICAL gap
🔍 DUPLICATE IMPLEMENTATION CHECK (MANDATORY)
Check for:
- Multiple intent systems
- Multiple job systems
- Duplicate validation logic
- Multiple ledger write paths

If found:
→ Mark as CRITICAL
→ Provide all locations
🧠 SECTION A — SYSTEM UNDERSTANDING
A1. What is being built?
Platform Type:
Core Philosophy:
Architectural Layers Identified:
A2. Layer Presence

Check:

Intent
Execution
Airlock
Determinism
State
Timeline
Lineage
🧱 SECTION B — BACKEND AUDIT
B1. Intent System

Lifecycle:

DRAFT → SUBMITTED → VALIDATED → APPROVED → EXECUTED → RECORDED
B2. Job System

Verify:

job model
queue
workers
retry
failure handling
B3. Airlock

Verify:

quarantine
validation
no direct ingestion
B4. Determinism

Verify:

hash
snapshots
replay
B5. Timeline

Verify:

Auth → Intent → Validation → Approval → Execution → State → Report
B6. Lineage

Verify:

forward
reverse
dependency graph
B7. Batch Intent

Verify:

parent-child
partial success
🎨 SECTION C — FRONTEND AUDIT

Check:

navigation
context visibility
intent panel
job panel
airlock UI
determinism UI
timeline UI
lineage UI
🔐 SECTION D — GOVERNANCE AUDIT

Verify:

No delete
UI not authority
Role enforcement
Period enforcement
Approval enforcement
📊 SECTION E — GAP ANALYSIS (UPDATED)
E1. Critical Gaps
CRITICAL GAPS:
- Gap: [description]
- Impact: [what breaks without this]
- Effort: [1-3 days / 3-10 days]
- Evidence: [file:lines or "NO EVIDENCE FOUND"]
E2. Major Gaps
MAJOR GAPS:
- Gap: [description]
- Impact: [what is limited]
- Effort: [3-10 days]
- Evidence:
E3. Minor Gaps
MINOR GAPS:
- Gap:
- Effort: [1-5 hours]
- Evidence:
🧭 SECTION F — IMPLEMENTATION PLAN (UPDATED)
Phase Dependencies:
Phase 1 → Phase 2 → Phase 3 → Phase 4 (sequential)
PHASE 1 — Core Engine
Dependencies: None
Tasks:
- [ ] Task - Effort: [X days] - Priority: CRITICAL
Success Criteria:
PHASE 2 — Governance Layer
Dependencies: Phase 1 complete
Tasks:
- [ ] Task - Effort: [X days] - Priority: CRITICAL
Success Criteria:
PHASE 3 — Finance Layer
Dependencies: Phase 2 complete
Tasks:
- [ ] Task - Effort: [X days] - Priority: CRITICAL
Success Criteria:
PHASE 4 — Advanced Systems
Dependencies: Phase 3 complete
Tasks:
- [ ] Task - Effort: [X days] - Priority: MAJOR
Success Criteria:
🛡️ SECTION G — GUARDRAILS (UPDATED)
G1. Implementation Guardrails
- No DB writes without intent
- No UI-only validation
- All mutations via guards
- All actions generate audit
- No orchestrator logic
- No bypass of intent → job → record pipeline
G2. Code Guardrails
- Stateless workers
- No network in modules
- Deterministic execution
- Idempotent jobs
G3. Testing Guardrails
- Guard tests (positive + negative)
- Determinism test
- Timeline immutability test
Guard Output Format
Guard:
Status: PASS / FAIL / PARTIAL
Evidence:
📦 FINAL OUTPUT FORMAT
1. SYSTEM UNDERSTANDING
2. BACKEND AUDIT
3. FRONTEND AUDIT
4. GOVERNANCE AUDIT
5. GAP ANALYSIS
6. IMPLEMENTATION PLAN
7. GUARDRAILS VERIFICATION
⚠️ FINAL REMINDER
READ-ONLY MODE
NO ASSUMPTIONS
NO SPECULATION
EVIDENCE REQUIRED
MISSING = MISSING
📌 Save as:
docs/audit/codex-audit-prompt-v3.md