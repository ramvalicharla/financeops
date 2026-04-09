FinanceOps — UI/UX Design Specification
STATUS: LOCKED
VERSION: 3.0
CHANGE POLICY:
- No inline edits
- Only versioned updates (v3.1, v4.0)
- All changes must include rationale + impact

Table of Contents

Mental Model
Hierarchy (Canonical)
Navigation Architecture (Definitive)
Global Layout
Onboarding Flow
Org Launcher
Entity Workspace
Module Structures
ERP Connection Module
Dynamic Module System
Platform Control Panel
Intent Layer
Execution / Job Visibility
Determinism / Evidence Hash
Airlock / Input Governance UI
High-Value Differentiators
Governance Rules
Role Permission Matrix
Chart of Accounts Setup
UX Principles
Responsive Behaviour
Frontend Stack
Implementation Notes
Requirements Traceability


1. Mental Model
FinanceOps is not a finance app. It is a Financial Control Plane — a platform where:

Every action is an intent before it becomes a state
Every execution is a job with full visibility
Every number has a determinism proof (hash + replayable lineage)
Every external input passes through an airlock before touching financial data
Every button triggers a state transition, never a direct mutation

The UI is a state machine visualiser and intent orchestrator.
The user always knows three things at all times:

Which entity they are operating in
Which period is active
Which layer they are acting on (intent / execution / committed state)


2. Hierarchy (Canonical)
Platform (Owner / Admin / Developer)
└── Tenant (Customer Organisation)
      └── Organisation (Legal Entity Group)
            └── Entity (Subsidiary / Branch / Unit)
                  └── Module (Financial Capability)
                        └── Sub-tab (Feature Area)
                              └── Workflow / Data / Report / Action
This hierarchy is sacred. Every screen must make the user's current position within it immediately visible.

3. Navigation Architecture (Definitive)
This is the confirmed, final navigation model. It must not be changed without a full spec revision.
3.1 The Two-Axis Model
AXIS 1 — LEFT NAVIGATION (persistent, always visible)
  Purpose: WHERE YOU ARE
  Contains: Org structure, entity list, module list, settings
  Width: 240px desktop, icon-only 56px tablet, hidden mobile

AXIS 2 — HORIZONTAL MODULE TABS (top of content area)
  Purpose: WHAT YOU ARE DOING
  Contains: Enabled modules for the current entity
  Behaviour: Driven by Module Registry per tenant
3.2 Full Layout Diagram
┌─────────────────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                                     │
│ [Logo]  [Global Search]            [Jobs] [Notifications] [User] [Settings] │
├──────────────────────┬──────────────────────────────────────────────────────┤
│                      │ MODULE TABS                                          │
│  LEFT NAVIGATION     │ [Financials][FAR][Consolidation][Banking][GST][+]   │
│                      ├──────────────────────────────────────────────────────┤
│  ORG SWITCHER        │ SUB-TABS (module-specific)                          │
│  ┌─────────────────┐ │ [Overview][Journals][Trial Balance][P&L][Close]     │
│  │ Acme Holdings ▼ │ ├──────────────────────────────────────────────────────┤
│  └─────────────────┘ │ CONTEXT BAR                                         │
│                      │ Acme Holdings → Acme India → Financials → Journals  │
│  ENTITIES            ├──────────────────────────────────────────────────────┤
│  ● All entities      │                                                      │
│  ● Acme India ←      │  CONTENT AREA                                        │
│  ● Acme US           │                                                      │
│  ● Acme EU           │  (data tables, forms, reports, visualisations)       │
│                      │                                                      │
│  ──────────────────  │                                                      │
│  MODULES             │                                                      │
│  📊 Financials ←     │                                                      │
│  🏗 FAR              │                                                      │
│  🌐 Consolidation    │                                                      │
│  💸 Prepaids         │                                                      │
│  📜 Lease Acctg      │                                                      │
│  🏦 Banking          │                                                      │
│  🧾 GST / Tax        │                                                      │
│  📈 Budgeting        │                                                      │
│  📁 Reports          │                                                      │
│                      │                                                      │
│  ──────────────────  │                                                      │
│  ⚙ Settings          │                                                      │
│  👤 Ram V · Owner    │                                                      │
└──────────────────────┴──────────────────────────────────────────────────────┘
3.3 Navigation Behaviour Rules
Left nav — Org Switcher:
Clicking opens a dropdown listing all orgs the user belongs to. Selecting an org reloads the workspace with that org's entities and modules. Returns user to the same module if it exists in the new org, otherwise defaults to Overview.
Left nav — Entities section:
Lists all entities in the current org. "All entities" at the top is a consolidated view (read-only for most modules, fully functional for Consolidation). Clicking an entity switches context — all module tabs and content immediately reflect that entity's data. The active entity is highlighted with a filled dot and bold label.
Left nav — Modules section:
Lists all modules enabled for the current tenant. Clicking a module item is equivalent to clicking its tab in the horizontal tab bar — they are synchronised. The active module is highlighted in both the left nav and the tab bar simultaneously. This dual-highlight confirms to the user they are in the right place.
Horizontal Module Tabs:
Show the same enabled modules as the left nav modules section. Serve as a fast-switching mechanism — one click to jump between Financials and FAR without moving the mouse to the left. The + button at the end opens the Dynamic Module panel (platform owner/admin only).
Sub-tabs:
Appear below the module tab bar. Specific to the active module. Persist the last-visited sub-tab per module per user (stored in localStorage).
Context Bar:
Always visible below the sub-tabs. Clickable breadcrumbs. Entity segment has a dropdown for instant entity switching without leaving the current module and sub-tab.

4. Global Layout
4.1 Top Bar (always visible, 52px height)
┌─────────────────────────────────────────────────────────────────────────────┐
│ [F] FinanceOps   [🔍 Search journals, entities, reports...    ⌘K]           │
│                                           [Jobs ●2][🔔3][Ram V ▼][⚙]       │
└─────────────────────────────────────────────────────────────────────────────┘
Elements left to right:

Logo + product name — click returns to Org Launcher
Global search — full-width centre, keyboard shortcut ⌘K, scope-filtered (see Section 16)
Jobs indicator — shows count of running jobs, click opens Job Panel
Notifications bell — count badge, click opens categorised notification panel
User menu — name + avatar, dropdown: Profile, MFA settings, Sign out
Settings cog — org settings for regular users, platform settings for platform_owner/admin

4.2 Left Navigation (240px, always visible on desktop)
Four sections separated by dividers:
Section 1 — Org Switcher (top)
Org name with dropdown chevron. Click to switch organisation.
Section 2 — Entities
Label: "Entities" (uppercase, muted, 11px)

All entities (consolidated)
[Entity 1 name] with colour dot
[Entity 2 name] with colour dot
[Entity 3 name] with colour dot
+ Add entity link (admin only)

Section 3 — Modules
Label: "Modules" (uppercase, muted, 11px)
One item per enabled module with icon and name. Active module highlighted. Order is drag-reorderable by admin.
Section 4 — Bottom (pinned)

⚙ Settings
👤 [User name] · [Role badge]

4.3 Period Selector
Embedded in the Context Bar, not the top bar. Shows current fiscal period (e.g. "Mar 2026"). Click opens period picker with: current period highlighted, closed periods shown with lock icon, future periods shown as greyed. Selecting a closed period shows the Period Lock overlay (see Section 16.1).

5. Onboarding Flow
Triggered on first login for a new tenant. Full-screen wizard, five steps. Progress bar at top. Two-column layout: left = form (60%), right = Governance Impact panel (40%).
Governance Impact Panel (right column, all steps)
Fixed panel. Content changes per step. Always shows:

What this step controls in the system
What cannot be changed after this step
Any governance or compliance implications
Warnings in amber for irreversible decisions


Step 1 — Account Setup
┌───────────────────────────────────────┬─────────────────────────────────────┐
│ Set up your account                   │  GOVERNANCE IMPACT                  │
│                                       │                                     │
│ Full name                             │  MFA is mandatory for all           │
│ [Ram Valicharla__________________]    │  FinanceOps accounts.               │
│                                       │                                     │
│ Work email                            │  This satisfies audit               │
│ [ram@acme.com___________________]     │  requirements for SOC 2,            │
│                                       │  ISO 27001, and most                │
│ Password              [strength bar]  │  enterprise security                │
│ [••••••••••••••••••]                  │  policies.                          │
│                                       │                                     │
│ MFA Setup (mandatory)                 │  Your account is the                │
│ ┌─────────────────────────────────┐  │  platform owner. Every              │
│ │  [QR CODE]   Scan with:         │  │  action you take will               │
│ │              Google Authenticator│  │  be attributed to this              │
│ │              Authy               │  │  identity permanently.              │
│ │  Enter code: [______]  Verify   │  │                                     │
│ └─────────────────────────────────┘  │                                     │
│                                       │                                     │
│                          [Continue]   │                                     │
└───────────────────────────────────────┴─────────────────────────────────────┘

Step 2 — Create Organisation
Fields:

Organisation legal name
Display name
Country (dropdown)
Base currency (auto-suggested from country)
Fiscal year start month
Reporting framework: IND-AS / IFRS / US GAAP / Local GAAP
Industry: Manufacturing / Financial services / Technology / Retail / Healthcare / Other

Advanced section (collapsed, expandable):

Consolidation required? (toggle — if yes, auto-enables Consolidation module in Step 4)
Multi-entity organisation? (toggle — if yes, activates full Entity Structure step)
Audit requirement level: Internal only / Statutory / Big-4 ready

Governance Impact panel: Reporting framework is irreversible after entity creation. Fiscal year controls period open/close for all entities.

Step 3 — Define Entity Structure
Toggle between two views:
Tree View (default):
Acme Holdings Pvt Ltd  [Holding · INR · India]
├── Acme Manufacturing Ltd  [Subsidiary · 100% · INR · India]
├── Acme US Inc             [Subsidiary · 100% · USD · USA]
└── Acme EU GmbH            [Branch · 80% · EUR · Germany]

[+ Add Entity]   [Set Intercompany Links]
Each node: click to edit inline. Drag to reorder. Click + on any node to add a child entity.
Table View:
Entity NameTypeParentCountryCurrencyOwnership %IntercoAcme ManufacturingSubsidiaryAcme HoldingsIndiaINR100%☑Acme US IncSubsidiaryAcme HoldingsUSAUSD100%☑Acme EU GmbHBranchAcme HoldingsGermanyEUR80%☑
Per-entity fields: Legal name, Display name, Country, Functional currency, Ownership %, Intercompany counterparts (multi-select from sibling entities), Reporting framework (inherited, overridable).
This data directly powers: Consolidation module, FX translation engine, Intercompany elimination engine, Ownership waterfall reports.
Governance Impact panel: Each entity is an independent accounting boundary. Journals posted to one entity cannot affect another unless explicitly modelled as an intercompany transaction.

Step 4 — Enable Modules
Core modules (always on, cannot be disabled):

Financials — GL, P&L, Balance Sheet, Cash Flow
Banking — bank recon, cash management
GST / Tax — returns, reconciliation
Reports — standard financial reports
Settings — org, users, roles

Add-on modules (toggle, auto-suggested from Step 2):
ModuleAuto-suggested forToggleFixed Assets (FAR)Manufacturing, AnyOnConsolidationMulti-entityOnLease AccountingIFRS / IND-ASOffPrepaid & AccrualsAnyOffBudgeting & ForecastingAnyOffBoard PackAnyOffAccounting LayerBig-4 audit levelOffM&A / FDDFinancial servicesOff
Each module card shows: name, icon, one-line description, estimated setup time, toggle. Hover reveals "What this includes" tooltip.
Governance Impact panel: Modules you enable appear in the left navigation and tab bar for all users. Disabling a module hides it but never deletes its data.

Step 5 — Review and Launch
Summary screen:

Org name, country, framework, fiscal year
Entity list with types and currencies
Enabled modules (count + names)
Invite team (optional): email + role rows, add multiple

Primary action: "Launch workspace"

Creates org in backend
Applies all migrations
Seeds Chart of Accounts (goes to COA Review screen before workspace — see Section 19)
Sends invite emails if team was added
Redirects to COA Review → then workspace

Governance Impact panel: Launching creates your organisation's immutable audit chain. From this point all actions are logged, timestamped, and attributed to a user. Nothing can be deleted — only reversed.

6. Org Launcher
Shown after login if user belongs to multiple organisations, or if no org exists.
┌─────────────────────────────────────────────────────────────────────────────┐
│ Welcome back, Ram                                     [🔍 Search orgs...]   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐│
│  │ AH  Acme Holdings    │  │ BI  Beta Industries   │  │  +  New            ││
│  │     3 entities       │  │     1 entity          │  │     Organisation   ││
│  │     8 modules        │  │     5 modules         │  │                    ││
│  │     ● Active         │  │     ◑ Trial           │  │                    ││
│  │     Today            │  │     Mar 15            │  │                    ││
│  │  [Open] [···]        │  │  [Open] [···]         │  │                    ││
│  └──────────────────────┘  └──────────────────────┘  └────────────────────┘│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
Card ··· menu: Open, Settings, Duplicate structure, Archive.
Status badges: Active (green) / Trial (amber) / Suspended (red) / Setup incomplete (grey).
Platform owners and admins see all tenant orgs across all customers. Regular users see only their assigned orgs.

7. Entity Workspace
7.1 Landing State
When user opens an org from the launcher, they land on:

Entity: All entities (default)
Module: Financials (default, or last visited)
Sub-tab: Overview

7.2 Entity Dashboard (Financials → Overview)
┌─────────────────────────────────────────────────────────────────────────────┐
│ [Revenue ₹48.2 Cr ▲12%] [EBITDA ₹9.1 Cr ▲8%] [Net Cash ₹3.4 Cr ▼4%] [Open Items 14]│
├──────────────────────────────────────┬──────────────────────────────────────┤
│ Period close status                  │ Alerts & exceptions                  │
│ ─────────────────────                │ ────────────────────                 │
│ Mar 2026  Acme India    ● Closed    │ ⚠ 3 journals pending approval        │
│ Mar 2026  Acme US       ◑ In review │ ⚠ Bank recon: 5 unmatched items      │
│ Mar 2026  Acme EU       ○ Open      │ ✓ ERP sync completed 2 mins ago      │
│                                      │                                      │
│ Recent journal activity              │ Quick actions                        │
│ ─────────────────────                │ ─────────────────                    │
│ JE-1024  Salary accrual  ₹42L  Ram  │ [New journal]  [Import statement]   │
│ JE-1023  Depreciation    ₹8L   Sys  │ [Run depreciation]  [Start close]   │
│ JE-1022  FX revaluation  ₹1L   Sys  │                                      │
└──────────────────────────────────────┴──────────────────────────────────────┘
7.3 Entity Isolation Rule
When a specific entity is selected in the left nav, all modules show only that entity's data. No cross-entity leakage at any layer — UI, API, or database.
The only exception is the Consolidation module, which explicitly aggregates across entities and permanently labels all views as "Consolidated View — Acme Holdings."
When "All entities" is selected:

Financials, FAR, Banking, GST → show read-only consolidated summary with a banner: "Consolidated view. Select an entity to create or edit records."
Consolidation → fully functional
Reports → shows org-level reports


8. Module Structures
Every module follows the identical layout pattern:
Left nav (module highlighted) → Module tabs (module tab active) → Sub-tabs → Context bar → Content
8.1 Financials
Sub-tabs: Overview · Journal Entries · Trial Balance · General Ledger · P&L · Balance Sheet · Cash Flow · Period Close
Journal Entries sub-tab:
Table columns: JE number, Date, Description, Debit, Credit, Status (Draft/Submitted/Approved/Posted), Created by, Actions.
Actions per row: View, Edit (if Draft), Approve (if user has role), Post (if Approved), Reverse (if Posted).
Top actions: New Journal, Import, Filter, Export.
Trial Balance sub-tab:
Live TB. Columns: Account code, Account name, Opening balance, Period debits, Period credits, Closing balance. Click any row to drill to General Ledger for that account. Toggle: show zero-balance accounts.
Period Close sub-tab:
Checklist of close tasks with owner, due date, status. Progress bar. Signoff chain. Blockers highlighted in red. "Start close" and "Complete close" actions gated by checklist completion and role.

8.2 Fixed Assets (FAR)
Sub-tabs: Asset Register · Add Asset · Depreciation Runs · Transfers · Disposals · Reports
Asset Register sub-tab:
Columns: Asset ID, Description, Category, Date of purchase, Cost, Accumulated depreciation, WDV, Status (Active/Disposed/Transferred). Filterable by category, entity, status.
Depreciation Runs sub-tab:
Shows scheduled and completed runs. Run a depreciation batch: select period, preview journal entries before posting, confirm. Creates a job (visible in Job Panel).

8.3 Consolidation
Sub-tabs: Overview · Structure · Intercompany · FX Translation · Run Consolidation · Reports
Structure sub-tab:
Interactive entity ownership graph. Nodes are entities with currency labels. Edges show ownership % and intercompany relationship direction. Click a node to open that entity's dashboard. Click an edge to see intercompany transactions between those two entities.
Run Consolidation sub-tab:
Step-by-step wizard:

Select period
Confirm entity scope
Review FX rates (editable with reason field)
Review intercompany eliminations (approve or flag discrepancies)
Preview consolidated trial balance
Confirm and run (creates a job, produces determinism hash on completion)


8.4 Lease Accounting
Sub-tabs: Lease Contracts · Amortisation Schedule · Remeasurement · Journal Entries · Disclosures
Lease Contracts sub-tab:
Register all leases. Per lease: commencement date, term, payments, incremental borrowing rate, classification (finance/operating). System auto-calculates ROU asset and lease liability on save.

8.5 Prepaid & Accruals
Sub-tabs: Prepaid Register · Accrual Register · Schedules · Auto-Run · Reports
Schedules sub-tab:
Calendar view showing amortisation postings across months. Click a month cell to see which prepaids/accruals post in that month and for how much.

8.6 Banking
Sub-tabs: Accounts · Import Statement · Reconciliation · Cash Position · Reports
Reconciliation sub-tab:
Two-panel view: left = bank statement transactions, right = system transactions. Drag-match or auto-match. Unmatched items flagged in red. Match confidence score shown for auto-match suggestions. Manual override always available.

8.7 GST / Tax
Sub-tabs: Returns · Reconciliation · Input Tax Credit · Filing · Reports
Returns sub-tab:
Table of all return types (GSTR-1, GSTR-3B, GSTR-9) with period, due date, status (Pending/Prepared/Filed/Overdue). Actions: Prepare, Review, File. Filing action triggers an intent that goes through approval before submission.

8.8 Budgeting & Forecasting
Sub-tabs: Budget · Forecast · Scenarios · Variance · Reports
Scenarios sub-tab:
Create named scenarios (Base / Upside / Downside). Each scenario has its own set of assumptions. Variance tab shows all three scenarios against actuals in a single table with variance columns.

8.9 Reports
Sub-tabs: Standard Reports · Custom Reports · Scheduled · Export
Standard Reports sub-tab:
P&L, Balance Sheet, Cash Flow, Trial Balance, Notes to Accounts. Each report has: period selector, entity selector, comparative period toggle, Audit Mode toggle, Download button (PDF/Excel/XBRL).

8.10 Accounting Layer
Sub-tabs: Chart of Accounts · Account Mapping · Journal Controls · Approval Policies · Audit Trail
Approval Policies sub-tab:
Define approval chains by: journal amount threshold, account type, entity, or user role. Visual approval chain builder — drag roles into sequence, set parallel vs sequential approval. This feeds the Intent Layer's approval routing.

9. ERP Connection Module
Location: Settings → Integrations → ERP Connections
9.1 ERP Connections Screen
┌─────────────────────────────────────────────────────────────────────────────┐
│ ERP Connections — Acme India                        [+ Add Connection]      │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Zoho Books                                          ● Connected        │ │
│ │ Last sync: 2 mins ago · 1,234 records · 0 errors                       │ │
│ │ [Sync Now]  [View Logs]  [Field Mapping]  [Disconnect]                  │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ QuickBooks Online                                   ⚠ 3 errors         │ │
│ │ Last sync: 1 hour ago · 567 records · 3 errors                         │ │
│ │ [Sync Now]  [View Logs]  [Field Mapping]  [Disconnect]                  │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Tally Prime                                         ○ Not connected     │ │
│ │ [Connect]                                                               │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
9.2 Supported ERPs
ERPConnectionSync DirectionAirlockZoho BooksOAuth / API KeyPull✅ AlwaysTally PrimeHTTP / ODBCPull + Push✅ AlwaysQuickBooks OnlineOAuth 2.0Pull✅ AlwaysXeroOAuth 2.0Pull✅ AlwaysSAP Business OneREST APIPull + Push✅ AlwaysOracle NetSuiteREST APIPull + Push✅ AlwaysBusy / Marg / MunimFile importPull✅ Always
All incoming ERP data lands in the Airlock queue first. It never touches the financial data layer directly. The "Sync Now" result shows: "X records sent to Airlock queue for review" — not "X records imported." This is the governance distinction.
9.3 Sync Detail Screen
Shows per-sync: records received, records passed airlock, records quarantined, records posted. Timeline graph of sync activity. Error log with row-level detail and suggested actions.

10. Dynamic Module System
10.1 What It Is
Platform owners and admins can register new modules in the Module Registry. Once registered, the module appears as a new item in the left nav and a new tab in the module tab bar for assigned tenants — without any code deployment.
10.2 Add Module Flow
Entry: Settings → Modules → + Add Module (admin) or Platform Control Panel → Module Registry → + Register Module (platform owner)
Step 1 — Type:

Standalone module (new left nav item + tab)
Core extension (adds sub-tabs to an existing module)
Compliance module (linked to a regulatory framework)
Custom module (built with FinanceOps team)

Step 2 — Define:
Module name:    [ESG Reporting]
Module key:     [esg_reporting]  (URL-safe, auto-generated, editable)
Icon:           [📊 ▼]
Scope:          ○ Organisation   ● Entity   ○ Global
Description:    [Track and report ESG metrics]
Roles with access: [☑ CFO  ☑ Finance Manager  ☐ Accountant  ☐ Viewer]
Step 3 — Sub-tabs:
Tab NameAPI EndpointAllowed ActionsOverview/api/v1/esg/overviewviewMetrics/api/v1/esg/metricsview, exportReports/api/v1/esg/reportsview, export, approve+ Add tab
Step 4 — Assign to tenants (platform owner only):
TenantStatusRelease dateAcme Holdings● ActiveImmediateBeta Industries◑ Beta2026-05-01Gamma Pvt Ltd○ Disabled—
Step 5 — Publish:
Module appears in left nav and tab bar for assigned tenants immediately. Audit log entry created: "Module ESG Reporting registered by Ram V at 2026-04-07 10:30:00."
10.3 Module Registry Table (Platform Owner view)
ModuleVersionTypeStatusTenantsActionsFinancialsv1.0CoreActive156⚙FARv1.2CoreActive120⚙Consolidationv1.1Add-onActive85⚙ESG Reportingv0.5CustomBeta3⚙
Per-module settings (⚙): version history, changelog, enable/disable per tenant, deprecate.

11. Platform Control Panel
Accessible only to platform_owner and platform_admin. Completely separate UI world from the tenant workspace. Accessed via the ⚙ Settings cog in the top bar (shows "Platform settings" for these roles, "Org settings" for all others).
11.1 Platform Left Navigation
🏠  Platform overview
🏢  Tenants
🧩  Module registry
🚩  Feature flags
🔒  Intents registry
⚙   Execution / jobs
📊  System health
📋  Audit logs
💳  Billing
⚙   Platform settings
11.2 Platform Overview
Four metric cards: Total tenants / Active tenants / Total users / System health %.
Recent platform events log: new tenant onboarded, module enabled/disabled, system alerts, failed jobs.
11.3 Tenant Management
Table: Tenant name, Plan, Status, Entities, Users, Modules, Created, Actions.
Row actions: Open workspace (impersonate with audit log entry), Settings, Suspend, Archive.
Tenant detail page: Profile, Entities, Users + roles, Modules (toggle each), Billing, Audit log filtered to this tenant.
11.4 Feature Flags
FlagDescriptionScopeStatusai_cfo_panelAI CFO assistant in content areaPer-tenantOn for 12audit_mode_v2Enhanced audit mode with replayGlobalOffesg_moduleESG reporting modulePer-tenantBeta
Toggle per flag per tenant. Phased rollout: set percentage of tenants to receive a flag (e.g. 10% → 50% → 100%).
11.5 System Health
Panels: API response time (24h/7d/30d graph), Error rate, Celery queue depth per queue, Redis memory, Supabase connection pool, Recent errors with Sentry links.
Worker status table: Worker ID, Status (Idle/Busy), Current job, CPU%, Memory.
11.6 Platform Audit Logs
Immutable log of all platform-level actions: tenant creation, module changes, feature flag changes, admin logins, impersonation events, system configuration changes. Searchable, filterable, exportable.

12. Intent Layer
12.1 What Is an Intent
An intent is a user's declared desired state change before it is validated and executed. Every state-changing action in the product creates an intent record first.
Lifecycle:
DRAFT → SUBMITTED → VALIDATED → APPROVED → EXECUTED → RECORDED
                              ↓
                          REJECTED
12.2 Intent Panel (Right sidebar, collapsible)
Appears when a user performs any state-changing action (create journal, post entry, run depreciation, file return). Slides in from the right — does not push content. Persists until dismissed or until the intent reaches EXECUTED or REJECTED state, then auto-collapses after 5 seconds.
┌─────────────────────────────────────────────────────────────────────────────┐
│ Journal Entry JE-1024                                               [×]     │
├─────────────────────────────────────────────────────────────────────────────┤
│ ₹5,00,000  ·  Bank A/c → Sales Revenue  ·  Q4 consulting revenue            │
├──────────────┬─────────────────┬────────────────────────────────────────────┤
│ INTENT       │ EXECUTION       │ AUDIT                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ Intent ID: INT-78F2A       Status: ● APPROVED                               │
│                                                                             │
│ DRAFT ──→ SUBMITTED ──→ VALIDATED ──→ APPROVED ──→ EXECUTED                 │
│   ✓            ✓              ✓             ✓           ⏳                  │
│                                                                             │
│ Validation rules passed:                                                    │
│ ✓ Period open  ✓ Dr = Cr  ✓ Accounts exist  ✓ Role authorised              │
│                                                                             │
│ Approval chain:                                                             │
│ Ram (Creator) ✓ → Finance Manager ⏳ → CFO                                  │
│                                                                             │
│ [View full intent]  [View execution log]                                    │
└─────────────────────────────────────────────────────────────────────────────┘
12.3 Intent Registry (Platform Control Panel)
Full searchable table of all intents across all tenants. Filterable by type, status, entity, date range, user. Each row: Intent ID, Type, Entity, User, Status, Created, Actions (View, Retry if FAILED).

13. Execution / Job Visibility
13.1 Job Panel
Accessible via "Jobs" button in top bar. Slide-in panel (same mechanism as Intent Panel).
┌─────────────────────────────────────────────────────────────────────────────┐
│ Jobs                                                             [×]        │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ JOB-1024  Depreciation Run                     ● RUNNING               │ │
│ │ ████████░░░░░░░░░░ 40%  (120/300 assets)                                │ │
│ │ Started: 10:32:15 · Duration: 4s · ETA: 6s                              │ │
│ │ Entity: Acme India · Period: Mar 2026                                   │ │
│ │ Triggered by: Ram → Intent: INT-78F2B                                   │ │
│ │ [View logs]  [Cancel]                                                   │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ JOB-1023  ERP Sync — Zoho Books                ✓ COMPLETED              │ │
│ │ Duration: 3.2s · Records: 127 → Airlock · Errors: 0                     │ │
│ │ [View logs]  [View airlock queue]                                       │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ JOB-1022  Consolidation Run                    ✗ FAILED                 │ │
│ │ Error: Intercompany mismatch — Acme India vs Acme US (₹12,34,567)       │ │
│ │ [View logs]  [Retry]  [View details]                                    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
13.2 Job Queue View (Platform Admin — System Health screen)
QueuePendingRunningCompletedFailedConsolidation311272ERP Sync1238455Depreciation00340Airlock714120
Worker table: Worker ID, Status, Current job, CPU%, Memory.

14. Determinism / Evidence Hash
14.1 Audit Mode Toggle
Available on every financial report. Toggle in the report header. When active, a blue banner appears: "🔍 Audit Mode Active."
Every line item in the report expands to show:

Source journals that make up this number (linked, clickable)
User who posted each journal
Approval chain for each journal
Timestamp of each state change

Revenue          ₹12,40,00,000
  └── Source: JE-1024 (₹5,00,000 · Ram · 10:30) · JE-1098 (₹3,20,000 · Ram · 11:00) · LE-22 · PA-11
14.2 Determinism Proof Panel
Shown below Audit Mode content for any completed report:
┌─────────────────────────────────────────────────────────────────────────────┐
│ DETERMINISM PROOF                                                           │
│ Root hash: SHA256: 8a7f3e2d1c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b        │
│ Artifact version: v3.1.2   Replayable: ✅                                   │
│                                                                             │
│ Derived from:                                                               │
│ • Journal entries snapshot (3 records): JE-1024, JE-1098, JE-1102          │
│ • FX rates snapshot: 2026-03-31 (ID: FX-202603)                            │
│ • Ownership structure: Org chart v2 (ID: ORG-2026-Q1)                      │
│                                                                             │
│ [Download determinism pack]  [Verify hash]  [Replay computation]            │
└─────────────────────────────────────────────────────────────────────────────┘
14.3 Determinism Registry (Platform Control Panel)
ReportEntityPeriodHashStatusP&LAcme IndiaMar 20268a7f3e2d…✅ VerifiedBalance SheetAcme IndiaMar 20269b8c7d6e…✅ VerifiedP&L ConsolidatedAcme HoldingsMar 20261a2b3c4d…⚠ Mismatch

15. Airlock / Input Governance UI
15.1 Airlock Queue
Location: Settings → Airlock
┌─────────────────────────────────────────────────────────────────────────────┐
│ Airlock Queue — Acme India                              [Process all]       │
│ Pending: 12 · Quarantined: 3 · Processed today: 47                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ File / Source         │ Type        │ Status         │ Received  │ Action  │
│───────────────────────┼─────────────┼────────────────┼───────────┼─────────│
│ zoho_export_mar.csv   │ ERP Sync    │ ● Pending      │ 10:32 AM  │ Review  │
│ manual_journal.xlsx   │ User upload │ ● Pending      │ 10:15 AM  │ Review  │
│ gstr_3b_feb.json      │ GST Portal  │ 🔴 Quarantined │ 09:00 AM  │ Inspect │
└─────────────────────────────────────────────────────────────────────────────┘
15.2 Airlock Review Screen
┌─────────────────────────────────────────────────────────────────────────────┐
│ Review: zoho_export_mar.csv                                                 │
│ Validation: ✓ 1,227 rows pass   ⚠ 7 rows quarantined                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Row │ Issue                  │ Suggested action                             │
│─────┼────────────────────────┼──────────────────────────────────────────────│
│ 45  │ Invalid account code   │ [Skip] [Map to: ______] [Correct]            │
│ 67  │ Duplicate journal ID   │ [Skip] [Overwrite] [Keep both]               │
│ 89  │ Date outside FY        │ [Skip] [Post to adj. period]                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                 [Approve all valid]  [Review quarantined]  [Reject file]    │
└─────────────────────────────────────────────────────────────────────────────┘
15.3 Hygiene Rules Configuration
RuleConditionActionEnabledDuplicate JE checkJournal ID existsQuarantine☑Date range validationDate outside FYQuarantine☑Account existenceAccount code invalidQuarantine☑Amount thresholdAmount > ₹50LRequire manager approval☑ClamAV scanFile type: xlsx/pdf/csvReject if infected☑

16. High-Value Differentiators
16.1 Period Lock Visualisation
Clicking a closed period in the period selector:
Period: March 2026                        Status: 🔒 Closed
Closed by: Ram (CFO) on 2026-04-05 18:30
Close checklist: 14/14 tasks completed
Override requires: CFO approval + mandatory business reason
[Request override]
16.2 Approval Graph
Visual tree showing the live approval chain for any pending record:
                     [CFO — ⏳ Pending]
                           │
          ┌────────────────┴────────────────┐
  [Finance Manager — ✅ 10:00]    [Tax Director — ✅ 09:45]
                           │
                  [Ram — ✅ Submitted 09:15]
Approval chains are dynamic — configured in Accounting Layer → Approval Policies. The graph always reflects the actual configured chain, not a fixed structure.
16.3 Cross-Module Traceability
Click any number in any report:
Revenue ₹12,40,00,000
──────────────────────────────────────────────────
JE-1024   ₹5,00,000   Financials    ✅ Posted
JE-1098   ₹3,20,000   Financials    ✅ Posted
LE-22     ₹1,80,000   Lease Acctg   ✅ Posted
PA-11     ₹1,20,000   Prepaids      ✅ Posted
──────────────────────────────────────────────────
[View all source records]  [Audit trail]  [Recompute]
16.4 Close Cockpit
Accessible from Financials → Period Close or from the Overview quick actions.
March 2026 Close — Acme India                    Progress: 11/14 tasks
──────────────────────────────────────────────────────────────────────
Task                         Owner     Due      Status
────────────────────────────────────────────────────────
Post all accruals            Ram       Mar 31   ✅ Done
Complete bank recon          Priya     Apr 1    ✅ Done
Finalise depreciation        System    Apr 1    ✅ Done
GST reconciliation           Priya     Apr 3    ⏳ In progress
Director signoff             Director  Apr 5    ○ Pending
──────────────────────────────────────────────────────────────────────
Blockers: 2 journals pending CFO approval (JE-1089, JE-1091)
[Notify approver]  [Complete close]
16.5 Global Search with Scope
🔍 [Search journals, entities, tasks, reports...           ] ⌘K

Search in:
● Current entity (Acme India)
○ All entities
○ Entire organisation
○ All tenants  (platform admin only)
16.6 Notifications Panel
🔴 Approvals (2)    JE-2090 requires your approval
🟡 Errors (1)       ERP Sync failed: Zoho rate limit
🔵 Info (3)         Consolidation completed: Mar 2026
⚫ System (1)       Scheduled maintenance: Apr 10 02:00
16.7 AI CFO Assistant
Collapsible panel on the right side of the content area. Context-aware (knows current entity, module, period). Read + navigate — never write.
🤖 AI CFO                                          [Collapse]
──────────────────────────────────────────────────────────────
You: "Why is cash down this month?"

AI: Cash decreased ₹2.1 Cr (12%) vs February.

    Drivers:
    1. Vendor payments — ₹1.8 Cr  (JE-2045, JE-2089)
    2. Prepaid insurance — ₹0.5 Cr  (PA-15)
    3. Lease payment — ₹0.3 Cr  (LE-08)

    [View source journals]  [Explain variance]
──────────────────────────────────────────────────────────────
[Ask about this entity and period...]

17. Governance Rules (Non-Negotiable)
These rules are enforced at every screen in the product. No exceptions.
RuleImplementationUI never grants authorityEvery button sends {intent, entityId, userId, data} to the backend. Backend validates authority.Every action is attributedAll create, edit, approve, post, export actions permanently show user name + timestamp.Approval states are visibleAny pending-approval record shows: what approval is needed, who can approve, waiting duration.Periods are explicitEvery data entry screen shows the current period. Closed period override requires CFO approval + reason.No deletesNo delete button exists anywhere in the financial data layer. Only reversal and void.Audit modeEvery financial report has an Audit Mode toggle showing source journals, users, approval chain.Context always visibleUser always sees current org, entity, module, period in the context bar. Never hidden.Intent before executionEvery state-changing action creates an intent record before any execution begins.Airlock before ingestionEvery external input (ERP, file upload, API) passes through quarantine before touching financial data.Determinism provableEvery committed report output has a hash and a snapshot reference set enabling replay.

18. Role Permission Matrix
This matrix governs what the UI renders. If a user does not have permission for an action, that action's button or control is absent — not disabled.
18.1 Roles Defined
RoleScopeDescriptionplatform_ownerPlatformFull access to everything including platform panelplatform_adminPlatformPlatform panel access, can manage tenants and modulesorg_adminOrganisationFull org access, user management, settingscfoOrganisationAll financial modules, final approverfinance_managerEntityMost financial actions, intermediate approveraccountantEntityCreate and submit journals, upload datatax_managerEntityGST/Tax module full accessdirectorOrganisationView all, approve board pack and period close signoffauditorOrganisationRead-only access to all data + audit modeviewerEntityRead-only, no approvals, no exports
18.2 Permission Matrix
Actionplatform_ownerorg_admincfofinance_manageraccountantdirectorauditorviewerView all modules✅✅✅✅✅✅✅✅Create journal✅✅✅✅✅❌❌❌Submit journal✅✅✅✅✅❌❌❌Approve journal✅✅✅✅❌❌❌❌Post journal✅✅✅❌❌❌❌❌Reverse journal✅✅✅❌❌❌❌❌Close period✅✅✅❌❌❌❌❌Override closed period✅❌✅❌❌❌❌❌Run depreciation✅✅✅✅❌❌❌❌Run consolidation✅✅✅❌❌❌❌❌File GST return✅✅✅✅ tax_mgr❌❌❌❌Approve board pack✅✅✅❌❌✅❌❌Invite users✅✅❌❌❌❌❌❌Manage modules✅✅❌❌❌❌❌❌Add/edit entities✅✅❌❌❌❌❌❌Export reports✅✅✅✅❌✅✅❌View audit trail✅✅✅✅❌✅✅❌Access platform panel✅✅ platform_admin❌❌❌❌❌❌Register modules✅❌❌❌❌❌❌❌Enable module per tenant✅✅❌❌❌❌❌❌

19. Chart of Accounts Setup Screen
Inserted between Step 5 (Launch) and the workspace. The user reviews and optionally customises the auto-seeded COA before any journal can be created.
19.1 COA Review Screen
┌─────────────────────────────────────────────────────────────────────────────┐
│ Chart of Accounts — Review before launching                                 │
│ Seeded for: IND-AS · Manufacturing · India · INR                            │
│ 214 accounts generated  [Search accounts...]      [Import custom COA]       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Group        │ Code  │ Name                  │ Type    │ Tax │ Actions      │
│──────────────┼───────┼───────────────────────┼─────────┼─────┼──────────── │
│ Assets       │ 1001  │ Cash in hand          │ Current │ N   │ Edit  Hide  │
│ Assets       │ 1002  │ Cash at bank          │ Current │ N   │ Edit  Hide  │
│ Assets       │ 1100  │ Accounts receivable   │ Current │ N   │ Edit  Hide  │
│ Liabilities  │ 2001  │ Accounts payable      │ Current │ N   │ Edit  Hide  │
│ ...          │ ...   │ ...                   │ ...     │ ... │ ...         │
├─────────────────────────────────────────────────────────────────────────────┤
│ [+ Add account]                                                             │
│                                                       [Confirm and Launch]  │
└─────────────────────────────────────────────────────────────────────────────┘
19.2 Rules

All 214 accounts are shown, paginated, grouped by category
User can: edit account name, hide an account (hidden accounts are not deleted, never shown in dropdowns but preserved for audit)
User can add custom accounts
User can import a custom COA (Excel template provided)
"Confirm and launch" button — finalises the COA, marks the org as setup_complete, redirects to workspace
COA can be modified after launch in Accounting Layer → Chart of Accounts, but account codes are immutable once a journal is posted against them


20. UX Principles
PrincipleDescriptionMinimal but powerfulNo decorative elements. No empty-state illustrations. Every pixel conveys information or enables an action.PredictableSame layout everywhere: left nav → module tabs → sub-tabs → context bar → content. A user who learns Financials already knows how to navigate every other module.TraceableEvery number links to its source. Every source links to its approval chain. Every approval links to the policy that governs it.FastOptimistic UI for read operations. Spinner only for write operations exceeding 200ms. Financial writes show explicit confirmation state.Role-awareAbsent is cleaner than disabled. If a user cannot perform an action, its control does not exist in the rendered UI. Nothing is greyed out.Context-lockedOrg, entity, module, period are always visible. A user can never lose track of where they are or what period they are operating in.Intent-firstNo button directly mutates financial state. Every action creates an intent. The user sees the intent lifecycle, not a spinner.

21. Responsive Behaviour
BreakpointLeft NavModule TabsSub-tabsContentDesktop 1280px+240px, always visibleAll tabs visibleAll sub-tabs visibleFull layoutTablet 768–1279px56px icon-only, hover to expandHorizontally scrollableHorizontally scrollableAdapts to remaining widthMobile < 768pxHidden, hamburger overlayCollapse to dropdown selectorCollapse to dropdown selectorSingle column, card-list view for tables
Mobile capability: View and approve only on initial release. No journal creation or data entry on mobile. A persistent banner on mobile: "For data entry and posting, use the desktop version."

22. Frontend Stack
LayerChoiceNotesFrameworkNext.js 15 (App Router)Already in useStylingTailwind CSS + shadcn/uiAlready in useStateZustand + React QueryZustand for entity/period context, React Query for server stateTablesTanStack TableVirtual scrolling for large datasetsChartsRechartsDynamic imports only — avoid static import to prevent 265kB chunkModule tabsCustom componentDriven by Module Registry API responseLeft navCustom componentDriven by same Module Registry response, synchronised with tabsEntity contextZustand storePersists across module navigation, rehydrated on page load

23. Implementation Notes
Route Structure
/[orgSlug]/[entitySlug]/[moduleKey]/[subTab]

Examples:
/acme-holdings/acme-india/financials/journals
/acme-holdings/acme-india/far/asset-register
/acme-holdings/all/consolidation/run
/platform/tenants
/platform/module-registry
Module Rendering
New modules registered in the Module Registry resolve to the same page shell with different config. The shell fetches the module config at load time and renders the correct sub-tabs, permissions, and data endpoints. No code deployment needed to add a new module tab.
Left Nav + Tab Synchronisation
Both the left nav module list and the horizontal module tab bar are rendered from the same data source: the tenant's enabled module list fetched at session start. Clicking either one updates a single activeModule value in the Zustand store, which both components subscribe to.
Entity Context
Current entity stored in Zustand. Persists across module navigation. On URL change to a different entity slug, the store updates and all data queries refetch with the new entity scope.
Role-Driven Rendering
Every UI component that involves an action receives a permissions prop derived from the decoded JWT claims. The component renders the action control or returns null based on permissions. Permission checks happen at render time in the component, not at the route level alone.
Intent Creation
Every form submission and action button calls createIntent(type, payload) before any API mutation. The intent API returns an intent ID and initial status. The Intent Panel subscribes to this intent ID via polling or websocket and updates the lifecycle display in real time.
Determinism
Every report generation endpoint returns a determinismHash and snapshotRefs alongside the report data. The UI stores these and displays them in the Determinism Proof Panel. The hash is computed server-side from the exact input snapshot and is verifiable independently.

24. Requirements Traceability
RequirementSectionStatusLeft nav with org + entity structure3, 4.2✅Module tabs (horizontal) in content area3.2✅Left nav and tabs synchronised3.3, 23✅Zoho-style onboarding wizard5✅Governance Impact panel during onboarding5✅Entity tree builder with ownership %5 Step 3✅Org launcher tile grid6✅Entity isolation rule7.3✅All entity consolidated view7.3✅Module sub-tab structure8✅ERP connection with airlock routing9✅Dynamic module add by platform owner10✅Module on/off per tenant10.3✅Platform Control Panel (separate world)11✅Module Registry with version + tenant toggle10.3, 11✅Intent lifecycle visualisation12✅Job / execution visibility13✅Determinism proof with hash14✅Airlock queue with quarantine15✅Hygiene rules configuration15.3✅Period lock visualisation16.1✅Approval graph (dynamic chain)16.2✅Cross-module traceability (click-through)16.3✅Close Cockpit16.4✅Global search with scope filter16.5✅Categorised notifications16.6✅AI CFO (read + navigate, never write)16.7✅Governance rules (non-negotiable)17✅Role permission matrix18✅Absent not disabled for unauthorised actions18, 20✅Chart of Accounts review before launch19✅No left nav conflict (resolved from v1/v2)3✅Mobile: view and approve only21✅Route structure23✅Recharts dynamic import (bundle fix)22✅
Unified state indicator (COMMITTED/DERIVED/PENDING)	25.1	✅
Snapshot navigation / time travel	25.2	✅
Guard failure UI with actionable messages	25.3	✅
Guided failure recovery for jobs	25.4	✅
Unified object timeline with authentication context	25.5	✅
Bulk operations with intent batching	25.6	✅
Report lineage graph (forward + reverse)	25.7	✅
Timeline hash (tamper-proof lifecycle)	25.5	✅ Add
Lineage impact warning before edits	25.6.5	✅ Add
Batch preview mode	25.6.4	✅ Add




Section 25 — System Completeness Layer
These five additions complete the governance UX. Together they form the signature experience that separates FinanceOps from every other financial platform.

25.1 Unified State Indicator
Every financial record in the system carries an explicit state badge. This badge is visible on every row in every table, on every detail panel, and in every report line. It is never hidden.
Three states, always one of these three, never ambiguous:
● COMMITTED   — Immutable. Posted to ledger. Cannot be changed, only reversed.
◑ DERIVED     — Computed from committed records. Recalculates if sources change.
○ PENDING     — Not yet committed. In draft, submitted, or approval workflow.
Colour encoding:

COMMITTED → green dot + green text
DERIVED → blue dot + blue text
PENDING → amber dot + amber text

Where it appears:
Every journal entry row:
JE-1024  Salary accrual  ₹42L  Ram  ● COMMITTED
JE-1025  FX revaluation  ₹8L   Sys  ● COMMITTED
JE-1026  Provision       ₹5L   Ram  ○ PENDING
Every report header:
P&L Statement — Acme India — March 2026
State: ◑ DERIVED  (computed from 847 committed records as of 2026-04-07 10:30)
Every balance on a report line:
Revenue   ₹12,40,00,000   ◑ DERIVED
  └── From 4 committed journals: JE-1024, JE-1098, LE-22, PA-11
The state indicator is the first thing an auditor sees on any screen. It answers immediately: "Is this number final or is it still moving?"

25.2 Snapshot Navigation — Time Travel
Every report and every financial object has a snapshot history. The user can navigate between snapshots to see the state of any number at any point in time.
Snapshot Navigator — Report header:
P&L Statement — Acme India — March 2026
┌─────────────────────────────────────────────────────────────────────────────┐
│ SNAPSHOT                                                                    │
│ ● v3.1.2  (Current — 2026-04-07 10:30)                                     │
│   v3.1.1  (2026-04-06 18:00 — before FX revaluation)                       │
│   v3.1.0  (2026-04-05 09:00 — at period close)                              │
│   v3.0.8  (2026-03-31 23:59 — end of period)                                │
│                                                                             │
│ [Compare two snapshots]  [View as-of date...]  [Download snapshot pack]     │
└─────────────────────────────────────────────────────────────────────────────┘
Compare two snapshots view:
P&L Comparison — Acme India — March 2026
──────────────────────────────────────────────────────────────────────────────
                   v3.1.0 (Close date)    v3.1.2 (Current)    Δ Change
──────────────────────────────────────────────────────────────────────────────
Revenue            ₹12,20,00,000          ₹12,40,00,000        +₹20L
Cost of goods      ₹7,10,00,000           ₹7,10,00,000         —
Gross profit       ₹5,10,00,000           ₹5,30,00,000         +₹20L
──────────────────────────────────────────────────────────────────────────────
Change drivers: JE-1098 posted after close (FX adj). [View journal]
View as-of date: Date picker. Selecting any date reconstructs the exact state of the report as it existed at that moment — using the immutable journal record chain. No estimation. Deterministically replayable.
Where snapshots are created:

Automatically at every period close
Automatically when a consolidation run completes
Automatically when a report is downloaded or exported
Manually by any user with CFO or above role (with a mandatory label)

This is the time travel capability. An auditor can say "show me the balance sheet as it looked the day the CFO signed off" and the system produces it exactly, with a verifiable hash.

25.3 Guard Failure UI
Every validation gate in the system has an explicit failure state. Failures are never silent, never vague, and always actionable.
Guard failure in the Intent Panel:
When validation fails during intent submission:
Journal Entry JE-1026                                         [×]
──────────────────────────────────────────────────────────────────
₹5,00,000  ·  Bank A/c → Sales Revenue  ·  Q4 adj

INTENT       EXECUTION      AUDIT
──────────────────────────────────────────────────────────────────
Intent ID: INT-78F3A        Status: ✗ VALIDATION FAILED

DRAFT ──→ SUBMITTED ──→ VALIDATED ──→ ...
  ✓            ✓              ✗

Guard failures (2):

❌ Period is closed
   March 2026 was closed by Ram (CFO) on 2026-04-05.
   Required to proceed: CFO approval + business reason override.
   [Request period override]

❌ Missing CFO approval
   This journal exceeds ₹50L threshold. CFO approval required.
   CFO: Ram Valicharla — not yet in approval chain.
   [Add CFO to approval chain]  [View approval policy]
──────────────────────────────────────────────────────────────────
[View guard details]  [Fix and resubmit]
Guard failure in a form field (inline):
Posting date: [2026-03-15  ▼]
              ⚠ March 2026 is closed. [Override]  [Change date]
Guard failure categories and their standard messages:
GuardFailure messageAction offeredPeriod closedPeriod {month} closed by {user} on {date}Request overridePeriod not openPeriod {month} not yet openedOpen periodDebit ≠ CreditJournal does not balance (Δ ₹{amount})Auto-balance optionAccount invalidAccount code {code} does not existMap to existingRole insufficientAction requires {role}. Your role: {role}Request accessApproval pendingAwaiting {role} approval since {duration}Notify approverDuplicate detectedRecord with same ID exists: {id}View existingThreshold exceededAmount ₹{X} exceeds policy limit ₹{Y}EscalateEntity mismatchAccount belongs to {entity}, not {entity}View account
Rule: Every guard failure shows exactly three things — what failed, why it failed, and what the user can do about it. Generic error messages are never acceptable.

25.4 Guided Failure Recovery (Jobs)
When a job fails, the system does not just offer a retry button. It diagnoses the failure, suggests a resolution path, and links directly to the tools needed to resolve it.
Failed job card in the Job Panel:
┌─────────────────────────────────────────────────────────────────────────────┐
│ JOB-1022  Consolidation Run                             ✗ FAILED            │
│ Entity: Acme Holdings · Period: Mar 2026 · Duration: 8.2s                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Failure reason:                                                             │
│ Intercompany mismatch between Acme India and Acme US                        │
│ Acme India records: ₹12,34,567 receivable from Acme US                     │
│ Acme US records:    ₹11,98,000 payable to Acme India                        │
│ Difference:         ₹36,567 (unreconciled)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Suggested resolution path:                                                  │
│                                                                             │
│ Step 1 → Reconcile the intercompany balance                                 │
│          [Open Consolidation → Intercompany module]                         │
│                                                                             │
│ Step 2 → Identify the discrepancy source                                    │
│          Possible cause: JE-2045 (Acme India, ₹36,567, posted 2026-04-01)  │
│          [View JE-2045]                                                     │
│                                                                             │
│ Step 3 → Post correcting entry or agree elimination                         │
│          [New intercompany journal]  [Auto-elimination suggestion]          │
│                                                                             │
│ Step 4 → Retry consolidation run                                            │
│          [Retry job]  (available after Step 1–3 are resolved)               │
├─────────────────────────────────────────────────────────────────────────────┤
│ [View full logs]  [Dismiss]                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
Resolution path rules:

Always numbered steps in sequence
Each step links directly to the tool needed (never just text)
Where the system can auto-suggest a fix (e.g. auto-elimination), it offers it with a preview before applying
Retry is only enabled after the root cause condition is resolved — the system checks before allowing retry
Auto-fix suggestions always show a preview and require explicit confirmation before executing

Failure types and their resolution paths:
Job typeFailureResolution pathConsolidationIntercompany mismatchOpen IC module → reconcile → post → retryConsolidationFX rate missingOpen FX rates → add rate → retryDepreciationAsset with no methodOpen asset register → set method → retryERP SyncRate limitWait (auto-retry in {n} mins) or reduce sync frequencyERP SyncAuth expiredReconnect ERP → retryPeriod closeChecklist incompleteOpen close checklist → complete items → retryGST FilingPortal rejectionView portal error → correct return → re-file

25.5 Unified Object Timeline
Every financial object in the system — a journal entry, an asset, a lease contract, a consolidation run, a filed return — has a single unified timeline that traces it from authentication context through intent creation to inclusion in a hashed report. This is the signature UX of the platform.

Timeline panel — accessible from any object's detail view:

text
┌─────────────────────────────────────────────────────────────────────────────┐
│ JE-1024 — Salary Accrual — ₹42,00,000                                      │
│ Entity: Acme India · Period: Mar 2026                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ TIMELINE                                                                   │
│                                                                            │
│   0. Authentication context                              2026-04-01 09:15 │
│      🔐 User: Ram Valicharla (user_id: usr-7f2a)                          │
│         Session ID: ses-9d3c · IP: 203.0.113.45 · Device: Chrome/Windows  │
│         MFA verified: Yes (TOTP, 09:14:32)                                │
│         Role at time: Accountant (Acme India)                              │
│         [View session details] [View auth log]                             │
│                                                                            │
│   1. Intent created                                        2026-04-01 09:15│
│      ○ INT-78F2A created by Ram Valicharla                                │
│         Type: CREATE_JOURNAL · Entity: Acme India                         │
│         [View intent payload]                                              │
│                                                                            │
│   2. Validated                                             2026-04-01 09:15│
│      ✓ 4/4 guards passed                                                  │
│         Period open · Dr=Cr · Accounts exist · Role authorised            │
│         [View guard results]                                               │
│                                                                            │
│   3. Approved                                              2026-04-01 10:00│
│      ✓ Finance Manager: Priya Sharma                                      │
│         Comment: "Monthly salary accrual confirmed"                        │
│         [View approval record]                                             │
│                                                                            │
│   4. Executed (Job)                                        2026-04-01 10:00│
│      ✓ JOB-1024 · Duration: 0.3s · No errors                              │
│         [View execution log]                                               │
│                                                                            │
│   5. Recorded (Committed state)                            2026-04-01 10:00│
│      ● COMMITTED to ledger · Immutable from this point                    │
│         Ledger hash: 8a7f3e2d… (chain entry #1,024)                       │
│         [View ledger entry]                                                │
│                                                                            │
│   6. Airlock (if external source)                             N/A         │
│      — Direct entry, not from external source                             │
│                                                                            │
│   7. Included in report                                    2026-04-07 10:30│
│      ◑ P&L Statement · March 2026 · v3.1.2                               │
│         Report hash: 1a2b3c4d…                                            │
│         Snapshot: v3.1.2 · Position in hash chain: #847                   │
│         [View report] [View determinism proof]                             │
│                                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ [Download full timeline as PDF]  [Copy timeline hash]                      │
└─────────────────────────────────────────────────────────────────────────────┘
Key design rules for the timeline:

Rule	Description
Authentication first	Step 0 is always present. Records who, from where, with what MFA status, at the moment of intent creation. Immutable.
Every step visible	All steps shown. Not applicable steps show "—" with reason. Prevents ambiguity — auditor sees intentional skip, not accidental omission.
Immutable steps	No editing, no deletion. If reversal posted, appears as new step (e.g., "8. Reversed by JE-1089") — original timeline unchanged.
Access points	Any journal row → "View timeline". Report line source drill-down → "View timeline for JE-xxxx". Intent Panel → "View full timeline". Audit Trail screen.
Audit pack ready	Complete chain of custody from authentication → intent → approval → execution → ledger → report inclusion with hash proof.
Authentication context data model:

json
{
  "step": 0,
  "type": "AUTHENTICATION_CONTEXT",
  "timestamp": "2026-04-01T09:15:00Z",
  "userId": "usr-7f2a",
  "userName": "Ram Valicharla",
  "sessionId": "ses-9d3c",
  "ipAddress": "203.0.113.45",
  "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
  "mfaVerified": true,
  "mfaMethod": "TOTP",
  "mfaTimestamp": "2026-04-01T09:14:32Z",
  "roleAtTime": "accountant",
  "roleScope": "Acme India"
}



25.6 Bulk Operations with Intent Batching
When a user performs an action on multiple objects simultaneously (e.g., "approve 10 journals", "post all depreciation for entity"), the system creates a batch intent that contains individual child intents for each object.

Batch Intent Panel — appears when bulk operation is initiated:

text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Bulk Approve — 10 Journals                                     [×]         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ Batch ID: BULK-78F4A                                                       │
│ Status: ● PROCESSING (3/10 complete)                                       │
│ Created by: Ram Valicharla · 2026-04-07 11:30:00                           │
│                                                                            │
│ Parent Intent: INT-78F4A (bulk approve)                                    │
│                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Child Intent │ Target        │ Status    │ Message                      │ │
│ │──────────────┼───────────────┼───────────┼──────────────────────────────│ │
│ │ INT-78F4B    │ JE-1024       │ ✅        │ Approved                      │ │
│ │ INT-78F4C    │ JE-1025       │ ✅        │ Approved                      │ │
│ │ INT-78F4D    │ JE-1026       │ ✅        │ Approved                      │ │
│ │ INT-78F4E    │ JE-1027       │ ❌        │ Period closed                 │ │
│ │ INT-78F4F    │ JE-1028       │ ⏳        │ Pending                       │ │
│ │ INT-78F4G    │ JE-1029       │ ⏳        │ Pending                       │ │
│ │ ...          │ ...           │ ...       │ ...                          │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│ Summary: 3 complete · 2 failed · 5 pending                                 │
│                                                                            │
│ Failed items:                                                              │
│ • JE-1027 — Period closed (March 2026)                                     │
│   [Override period] [Skip] [Retry]                                         │
│                                                                            │
│ [Continue batch]  [Abort batch]  [Download batch report]                   │
└─────────────────────────────────────────────────────────────────────────────┘
Batch intent rules:

Rule	Description
Atomic by default	Batch fails entirely if any item fails, unless user chooses "continue on error"
Continue on error option	Checkbox before batch submission: "Continue processing remaining items if some fail"
Partial success handling	When continue on error enabled, successful items commit, failed items reported with resolution actions
Batch report	Downloadable CSV of all items with status, error messages, and timestamps
Retry failed	User can retry only failed items without resubmitting successful ones
Bulk operation types that require batching:

Operation	Batch Intent Required
Bulk approve (multiple journals)	✅ Yes
Bulk post (multiple journals)	✅ Yes
Run depreciation for all assets	✅ Yes (single job, but assets batched internally)
Bulk import (Excel/CSV)	✅ Yes (each row = child intent)
Bulk entity close	✅ Yes
Bulk reversal	✅ Yes

25.6.4 Batch Preview Mode (Add to Section 25.6)
Before executing any batch operation, the system shows a preview of expected outcomes.

Batch Preview Screen:

text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Batch Preview — Bulk Approve (10 journals)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ Preview analysis complete:                                                  │
│                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ ✅ Will succeed: 8 journals                                            │ │
│ │ ❌ Will fail:     2 journals                                           │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│ Failed items preview:                                                      │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Journal     │ Reason                    │ Suggested fix                 │ │
│ │─────────────┼───────────────────────────┼───────────────────────────────│ │
│ │ JE-1027     │ Period closed (Mar 2026)  │ [Override period] [Skip]      │ │
│ │ JE-1029     │ Insufficient role         │ [Request approval] [Skip]     │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│ Options:                                                                   │
│ ○ Abort batch (fix issues first)                                           │
│ ● Continue with 8 items (skip failing 2)                                   │
│ ○ Attempt all 10 (continue on error)                                       │
│                                                                            │
│ [Execute]  [Cancel]                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
Integration with existing Section 25.6:

The current Section 25.6 shows failed items during execution. Add preview before execution as step 0 of batch processing. The "Continue with 8 items" option maps to the existing "continue on error" checkbox.





25.6.5 Lineage Impact Warning (Add before 25.7)
When a user attempts to modify or reverse any financial object that appears in a published report, the system displays an impact warning before confirming the action.

Warning modal — Edit/Reverse action:

text
┌─────────────────────────────────────────────────────────────────────────────┐
│ ⚠️ Lineage Impact Warning                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ You are about to REVERSE Journal Entry JE-1024                              │
│                                                                            │
│ This journal appears in the following reports:                             │
│                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Report                    │ Version │ Status      │ Impact              │ │
│ │───────────────────────────┼─────────┼─────────────┼─────────────────────│ │
│ │ P&L — March 2026          │ v3.1.2  │ ● Final     │ Will be outdated    │ │
│ │ Board Pack — Q1 2026      │ v2.1    │ ● Final     │ Will be outdated    │ │
│ │ Annual Report 2026 (draft)│ v0.9    │ ◑ Draft     │ Will be updated     │ │
│ │ Investor Presentation     │ v1.0    │ ● Final     │ Will be outdated    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│ Recommended actions:                                                       │
│ 1. Create a correcting journal instead of reversing (preserves history)    │
│ 2. Notify report consumers of pending changes                              │
│ 3. Regenerate affected reports after change                                │
│                                                                            │
│ [Proceed with reversal]  [Create correcting journal instead]  [Cancel]     │
└─────────────────────────────────────────────────────────────────────────────┘
Where this appears:

Action	When Warning Shows
Reverse a committed journal	✅ Always (if journal appears in any final report)
Edit a submitted (not yet approved) journal	❌ No (not yet in any report)
Delete a draft journal	❌ No
Edit a posted journal	⚠️ Warning (but reversal is the only allowed action — edit not possible)
Modify COA account	✅ Warning (affects all reports using that account)
Change FX rate after period close	✅ Warning (affects all reports using that rate)
Rule: If the object appears in any report with status "Final" or "Filed", the warning is mandatory with "Proceed anyway" requiring CFO approval.


25.7 Report Lineage Graph
Auditors need to see not only which journals produced a report (forward lineage) but also which reports consumed which journals (reverse lineage). The Report Lineage Graph provides both views.

Access: Any report → "View Lineage" button in report header.

Forward Lineage View (this report came from these sources):

text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Report Lineage — P&L Statement — March 2026 (v3.1.2)                       │
│ Entity: Acme India                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ FORWARD LINEAGE — What produced this report                                │
│                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 847 COMMITTED JOURNAL ENTRIES                                           │ │
│ │   ├── 623 from Financials module                                        │ │
│ │   ├── 124 from Lease Accounting module                                  │ │
│ │   ├── 72 from Prepaids module                                           │ │
│ │   └── 28 from ERP sync (Airlock)                                        │ │
│ │                                                                         │ │
│ │ [View all journals] [Download journal list]                             │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 2 FX RATE SNAPSHOTS                                                     │ │
│ │   • FX-202603 (2026-03-31) — closing rates                              │ │
│ │   • FX-202603A (2026-03-31) — average rates                             │ │
│ │ [View FX snapshots]                                                     │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 1 OWNERSHIP STRUCTURE SNAPSHOT                                          │ │
│ │   • ORG-2026-Q1 (2026-03-31) — group structure for consolidation        │ │
│ │ [View structure]                                                        │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ REVERSE LINEAGE — Which reports depend on this report                      │
│                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Report                    │ Version │ Generated    │ Status             │ │
│ │───────────────────────────┼─────────┼──────────────┼────────────────────│ │
│ │ Board Pack Q1 2026        │ v2.1    │ 2026-04-08   │ ● Final            │ │
│ │ Annual Report 2026 (draft)│ v0.9    │ 2026-04-10   │ ◑ Draft            │ │
│ │ Investor Presentation     │ v1.0    │ 2026-04-15   │ ● Final            │ │
│ │ Regulatory Filing — ROC   │ v1.0    │ 2026-04-20   │ ● Filed            │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│ [View full lineage graph]  [Export lineage as JSON]  [Verify hash chain]   │
│                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
Visual Graph View (toggle from table view):

text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Lineage Graph — P&L March 2026                                     [Table] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                              ┌─────────────────────┐                       │
│                              │   P&L March 2026    │                       │
│                              │      (v3.1.2)       │                       │
│                              └──────────┬──────────┘                       │
│                                         │                                   │
│              ┌──────────────────────────┼──────────────────────────┐        │
│              │                          │                          │        │
│     ┌────────┴────────┐        ┌────────┴────────┐        ┌────────┴────────┐
│     │  847 Journals   │        │  FX Snapshots   │        │  Org Structure  │
│     │   (committed)   │        │   (2 snapshots) │        │   (Q1 2026)     │
│     └────────┬────────┘        └─────────────────┘        └─────────────────┘
│              │                                                  │
│     ┌────────┴────────┐                                       │
│     │ 623 Financials  │                                       │
│     │ 124 Lease       │                                       │
│     │ 72 Prepaids     │                                       │
│     │ 28 ERP          │                                       │
│     └─────────────────┘                                       │
│                                                                │
│     ┌─────────────────────────────────────────────────────────┴─────────────┐
│     │                         DOWNSTREAM REPORTS                            │
│     │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│     │  │ Board Pack   │  │ Annual Rpt   │  │ Investor     │  │ Regulatory │ │
│     │  │ Q1 2026      │  │ 2026 (draft) │  │ Presentation │  │ Filing     │ │
│     │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │
│     └───────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
Lineage Graph rules:

Rule	Description
Forward lineage	Shows all source objects that contributed to this report, grouped by type
Reverse lineage	Shows all reports that depend on this report (e.g., Board Pack, Annual Report)
Click through	Click any source object → open its detail view. Click any downstream report → open that report
Hash verification	"Verify hash chain" confirms that every source object's hash is included in the report's determinism proof
Exportable	Lineage can be exported as JSON for external audit tools







Key design rules for the timeline:
Every step is always shown, even if it was not applicable (shown as N/A with reason). This prevents ambiguity — an auditor can see that a step was skipped intentionally, not accidentally.
Steps are immutable once recorded. No editing, no deletion from the timeline. If a reversal is posted, it appears as a new step 8: "Reversed by JE-1089" — the original timeline is unchanged.
The timeline is accessible from: any journal row → "View timeline", any report line source drill-down → "View timeline for JE-xxxx", the Intent Panel → "View full timeline", and the Audit Trail screen.
The timeline is the audit pack. An auditor who needs to evidence a number in the financial statements can pull the timeline for any contributing journal and have the complete chain of custody in a single view — from the moment the user had the intent to post, through approval, execution, ledger commitment, and report inclusion with hash proof.


End of specification.
Save as: docs/design/finops-ui-spec-v3.0.md
