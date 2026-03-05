# FinanceOps Platform — User Manual
> Version: auto-updated with platform version
> Last Updated: auto-updated on every deployment
> This document grows with the platform — add a section for every new feature

---

## How This Manual Works

This manual is auto-updated as the platform is built. Each section corresponds to a platform module. When a new module is deployed, its section is added here. When a feature changes, its section is updated.

**For users:** Read the section for the module you are using.
**For the team:** Update this manual when any user-facing feature changes.
**Auto-generated sections:** API reference, error messages, keyboard shortcuts.

---

## Quick Start Guide

### Step 1 — First Login
1. You will receive an email with your login link
2. Click the link → set your password
3. If MFA is required for your role, set up your authenticator app
4. You will see the onboarding wizard on first login

### Step 2 — Onboarding Wizard
The wizard guides you through:
1. Connect your accounting system (or skip for manual uploads)
2. Set your base currency and reporting currency
3. Upload your first MIS file (or skip)
4. Invite your team members
5. Set your first month-end deadline

### Step 3 — Understand Your Role
Your role determines what you can see and do:

| Role | What You Can Do |
|---|---|
| Finance Leader | Everything — approve, publish, manage users |
| Manager | Review data, make corrections, submit for approval |
| Reviewer | View all data, add comments, flag issues |
| Data Entry — Payroll | Upload paysheets only |
| Data Entry — GL/TB | Upload GL and TB only |
| Executive | View dashboard and reports only |

---

## Navigation Guide

### The Six Main Tabs

**Tab 1 — Chat**
Talk to the AI about your financial data. Ask anything in plain English.
Examples:
- "What is our gross margin for Customer X this month?"
- "Which entity has the largest reconciliation break?"
- "Show me consultant costs in Australia broken down by name"

**Tab 2 — MIS Manager**
Upload and manage your MIS workbooks. The platform learns your MIS structure and helps keep it consistent across months.

**Tab 3 — Source Data**
Upload your Trial Balance, GL dump, and paysheets. Connect your ERP for automatic data sync.

**Tab 4 — Reconciliation**
Review GL to TB reconciliation results, resolve breaks, track intercompany reconciliation.

**Tab 5 — Consolidation**
Set foreign exchange rates, run multi-currency consolidation, review consolidated P&L.

**Tab 6 — Reports**
Generate month-end packs, view charts, export to Excel or PDF.

---

## Module Guides

---

### MIS Manager

#### What It Does
The MIS Manager helps you maintain a consistent, comparable Management Information System across all months, even as your business and reporting structure evolves.

#### Uploading Your MIS
1. Go to Tab 2 — MIS Manager
2. Click "Upload MIS Workbook"
3. Select your Excel file (multi-sheet workbooks supported)
4. Select the period (month + year)
5. Select the entity (organisation)
6. Click Upload

The file goes through three stages:
- **Scanning:** virus and security scan (takes 5-15 seconds)
- **Parsing:** reading the structure of your workbook
- **Learning:** comparing to your saved template

#### Setting the Master Template
Your "Master MIS" is the standard all other months are compared to. Set it once when your MIS is in its most complete and final form.

1. Go to MIS Manager → Versions
2. Find the version you want to designate as master
3. Click "Set as Master Template"
4. Confirm

All future uploads are compared to this template.

#### Responding to Missing Data Prompts
When the platform detects data that is missing or different from your master template, it will ask you about it. You will see a "Prompts Pending" badge on Tab 2.

For each prompt:
- Read the question carefully
- Select your answer or type the value
- Click Confirm

The platform will never assume — it always asks you first.

#### MIS Version History
Every upload is saved as a new version. You can:
- View any previous version
- Compare two versions side by side
- Restore a previous version as the current working version (creates a new version — original is never modified)

---

### FX Rates

#### Setting Month-End Rates
1. Go to Tab 5 — Consolidation
2. Click "FX Rates" → "Set Rates for [Month]"
3. Click "Fetch Live Rates" to see rates from 4 sources:
   - European Central Bank (ECB)
   - Frankfurter API
   - Open Exchange Rates
   - ExchangeRate-API
4. Select which source to use, or enter your own rate manually
5. Click "Save Rates for [Month]"

Rates are saved permanently for that month and cannot be changed after the month is locked (post Finance Leader approval).

#### Adding a New Currency
If you need a currency not in the default list:
1. Go to FX Rates → Settings
2. Click "Add Currency"
3. Enter the ISO 4217 currency code (e.g. MYR, JPY, ZAR)
4. The currency is immediately available for all months

---

### GL/TB Reconciliation

#### Running a Reconciliation
1. Upload your TB (Tab 3 → Upload → Trial Balance)
2. Upload your GL dump (Tab 3 → Upload → GL)
3. Go to Tab 4 — Reconciliation
4. Select entity and period
5. Click "Run Reconciliation"

The reconciliation runs automatically (typically 30-120 seconds). You will be notified when complete.

#### Understanding Results

**Green:** No breaks — GL balances match TB exactly
**Amber:** Timing difference detected — likely one entity posted, the other hasn't yet
**Red:** Unexplained break — requires investigation and resolution

#### Resolving a Break
1. Click on the red break item
2. Review the detail (which accounts, what amount)
3. Click "Investigate" to see the GL entries
4. Add a note explaining the break
5. Assign to yourself or a team member
6. When resolved: click "Mark as Resolved" and add resolution note
7. Resolution requires Finance Leader sign-off

#### Intercompany Reconciliation
The platform automatically matches intercompany transactions across all entities.

- **Matched:** IC transaction in Entity A matches Entity B — shown in green
- **FX Difference (explained):** Difference is within expected FX variance — shown in amber with explanation
- **Unexplained Break:** Difference exceeds FX variance — shown in red, must be resolved before consolidation

---

### Multi-Currency Consolidation

#### Running Consolidation
1. Ensure FX rates are set for the period (see FX Rates section)
2. Ensure all entity TB/GL uploads are complete
3. Go to Tab 5 — Consolidation
4. Select the period
5. Click "Run Consolidation"

The platform:
- Converts all entity P&Ls to parent currency using your confirmed FX rates
- Eliminates intercompany transactions (confirmed IC matches only)
- Sums all entities to produce consolidated P&L

#### Reviewing Consolidated P&L
The consolidated view shows:
- Each entity in local currency (expandable)
- Each entity converted to parent currency
- Consolidated total
- FX impact column (how much of the movement is FX vs actual)
- Budget vs actual (if budget is loaded)
- Prior month vs current month

#### Exporting
Click "Export" → choose Excel or PDF.
The export includes source file references in the header of every sheet.

---

### AI Chat

#### How to Use
Type your question in plain English. The AI understands financial terminology and knows your data.

Good questions:
- "What is the total contractor cost in Australia for Q1?"
- "Which customers have a gross margin below 20%?"
- "Explain the variance in SG&A between January and February"
- "Under IFRS 15, how should we treat the variable consideration in Contract X?"

#### Understanding the Response
Every AI response shows:
- **Confidence score:** How certain the AI is (shown as a percentage and colour)
- **Model chain:** Which AI models were used to generate and validate the answer
- **Assumptions:** Any assumptions made to generate the answer
- **Sources:** Standards citations if the question was about accounting treatment

#### Giving Feedback
Every response has 👍 and 👎 buttons.
- 👍 if the answer was correct and helpful
- 👎 if the answer was wrong or unhelpful (you can explain what was wrong)

Your feedback directly improves the platform's accuracy over time.

#### Important: AI Output Is Not Final
All AI-generated outputs are suggestions only. No AI output is ever actioned automatically. You must review and approve.

---

### Revenue Recognition

#### Setting Up a Contract
1. Go to Source Data → Contracts → Add Contract
2. Enter or upload contract details
3. Select the revenue recognition method:
   - **Percentage of Completion (Cost-to-Cost):** Revenue recognised proportional to costs incurred
   - **Milestone Basis:** Revenue recognised when specific milestones are completed
   - **Straight-Line:** Revenue recognised evenly over the contract period
   - **Completed Contract:** Revenue recognised only when fully delivered
   - (other methods available — see full list in Settings)
4. For milestone contracts: add each milestone with value and expected date
5. Save

#### Recognising Revenue
Each month, go to Reports → Revenue Recognition → Run for [Period].
The platform will:
- Compute revenue for each method
- Flag any contracts where recognition cannot proceed (missing inputs)
- Show deferred revenue balance
- Generate IFRS 15 disclosure notes

For milestone contracts: mark milestones as complete to trigger recognition.

---

### Fixed Asset Register

#### Adding an Asset
1. Go to Source Data → Fixed Assets → Add Asset
2. Enter: asset name, category, acquisition date, cost, useful life, residual value
3. Select depreciation method (SLM, WDV, Double Declining, Units of Production)
4. Select entity and location
5. Save

#### Running Monthly Depreciation
Go to Source Data → Fixed Assets → Run Depreciation → Select period → Confirm.
Depreciation entries are computed and a journal entry is prepared for ERP posting.

#### Disposal
1. Find the asset in the register
2. Click "Dispose"
3. Enter: disposal date, disposal proceeds
4. The platform computes the gain/loss on disposal
5. Journal entry prepared for approval and ERP posting

---

### Headcount & People

#### Recording a Joiner
1. Go to Source Data → Headcount → Add Event → Joiner
2. Enter: name, role, designation, location, entity, start date
3. Save

#### Recording a Leaver
1. Go to Source Data → Headcount → Add Event → Leaver
2. Enter: name, exit date
3. The platform will ask: **Voluntary or Involuntary?**
4. Select the type and optionally add a reason
5. Save

This information feeds directly into attrition metrics and people cost analytics.

#### Changing a Classification
If you need to change a voluntary/involuntary classification:
1. Find the exit event in Headcount → Events
2. Click Edit
3. Change the classification
4. Add a reason for the change
5. Save

The original classification is preserved in the audit trail. Reports automatically show the updated classification.

---

### Compliance Calendar

#### Viewing Your Calendar
Go to Tab 6 → Compliance Calendar. You will see:
- **Today's view:** What is due today
- **This week:** All items due this week
- **This month:** Full month view
- **Overdue:** Items past their due date (shown in red)

#### Adding a Task
1. Click "Add Task"
2. Enter: task name, due date, assigned to, priority
3. Select the category (Tax, Statutory, Audit, Board, Payroll, Other)
4. Set recurrence if it repeats monthly/quarterly/annually
5. Save

#### Completing a Task
1. Find the task
2. Click "Mark Complete"
3. Add any completion notes
4. If the task requires Finance Leader sign-off, submit for approval

#### Calendar Export
Click "Export to Calendar" to download an .ics file that you can import into Outlook or Google Calendar.

---

### Month-End Reports

#### Generating the Month-End Pack
Before generating, ensure:
- All TB/GL uploads are complete ✓
- All reconciliation breaks are resolved ✓
- FX rates are set ✓
- Consolidation has been run ✓
- All assumptions have been accepted ✓

Then:
1. Go to Tab 6 — Reports
2. Click "Generate Month-End Pack"
3. Select the period
4. Click Generate (takes 2-5 minutes)

#### Reviewing Before Publishing
The pack is generated in draft mode first. You can:
- Read all 10 sections
- Edit any AI-generated commentary (Section 10)
- Add or remove charts
- Check that all numbers look correct

#### Publishing
Once satisfied:
1. Click "Publish"
2. Review the distribution list (who will receive the email)
3. Confirm: "I approve this report for distribution. I am responsible for its accuracy."
4. Click "Confirm & Publish"

The email is sent automatically to all recipients on the distribution list.

---

## Approval & Workflow Guide

### Understanding the Approval Flow
```
Data Entry uploads file
        ↓
Reviewer reviews and flags any issues
        ↓
Manager corrects issues and submits
        ↓
Finance Leader reviews and approves
        ↓
Month is locked — no further changes
```

### What Happens When a Month Is Locked
Once the Finance Leader approves:
- All data for that month is locked
- No uploads or changes can be made
- The audit trail records the lock with timestamp and approver
- If a change is needed: Finance Leader must unlock, make changes are tracked as a new version, re-approve

### Responsibility Confirmation
Certain actions require you to explicitly confirm responsibility. You will see a confirmation dialog like:

> "I confirm that this journal entry is accurate, has been reviewed, and I authorise its posting to the accounting system."

You must read and accept this to proceed. This is your digital signature.

---

## Troubleshooting

### Common Issues

**"My file upload is stuck at Scanning"**
The file is being checked for viruses. This usually takes under 30 seconds. If it's been more than 2 minutes:
1. Try uploading the file again
2. If it fails again, the file may have been flagged — check with your IT team
3. Contact support with the Correlation ID shown on the error message

**"I can't see a module that I need"**
Your role may not have access, or the module may not be enabled for your tenant.
1. Check with your Finance Leader (they manage user permissions)
2. If the module should be enabled, your Finance Leader can contact platform support

**"The AI gave me a wrong answer"**
Click 👎 on the response and explain what was wrong. The platform uses this feedback to improve. For important questions, always verify AI outputs against your source data.

**"My reconciliation shows a break that I know is correct"**
Some differences are legitimate (e.g. timing differences in intercompany transactions). You can:
1. Add a note explaining why the break exists
2. Mark it as "Explained" with your reasoning
3. The Finance Leader can approve the explanation

**"I need to undo an action"**
The platform never deletes or modifies data. Instead:
- Every change creates a new version
- The previous version is always preserved
- Contact your Finance Leader to create a correcting entry

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl + K` | Open global search |
| `Cmd/Ctrl + /` | Open keyboard shortcuts help |
| `Cmd/Ctrl + Enter` | Submit current form |
| `Esc` | Close modal / cancel |
| `Tab` | Move to next field |
| `?` | Open help for current screen |

---

## Glossary

**Backlog:** The total value of contracted, undelivered work (SOW/PO/WO balance)
**Chain Hash:** A security mechanism ensuring audit logs cannot be tampered with
**Consolidation:** Combining financial statements of multiple entities into one
**FX Rate:** Foreign exchange rate used to convert one currency to another
**IC / Intercompany:** Transactions between two entities within the same group
**MIS:** Management Information System — your internal management accounts
**Master Template:** The designated "most complete" MIS structure all months are aligned to
**RLS:** Row Level Security — database mechanism ensuring tenants cannot see each other's data
**ROU Asset:** Right-of-Use Asset — created under IFRS 16 lease accounting
**TB:** Trial Balance — a list of all general ledger accounts and their balances
**Version:** Every change to a document creates a new version. Old versions are never deleted.

---

## Getting Help

**In-App Help:** Click the `?` on any screen for context-specific guidance

**Global Search:** Press `Cmd/Ctrl + K` to search for anything across the platform

**Support:** Contact your tenant administrator first. For platform issues, use the Help button in the bottom left corner.

**Reference:** Error messages always include a Correlation ID. Share this with support for faster resolution.

---

*End of User Manual v1.0*
*This document is automatically updated when new features are deployed*
*Last section added: Initial platform setup*

---

## Browser & Device Compatibility

```
SUPPORTED BROWSERS (desktop):
  Chrome 100+      ✅ Recommended
  Firefox 110+     ✅ Fully supported
  Safari 16+       ✅ Fully supported (Mac/iPad)
  Edge 110+        ✅ Fully supported
  Internet Explorer ❌ Not supported

MOBILE / TABLET:
  Chrome (Android)  ✅ PWA installable
  Safari (iOS)      ✅ PWA installable (Add to Home Screen)
  Minimum screen:   360px width

PWA vs NATIVE APP:
  Currently: Progressive Web App (PWA) only
  Install: Chrome → three dots menu → "Install FinanceOps"
           Safari (iOS) → Share → "Add to Home Screen"
  
  PWA capabilities:
  ├── Works like native app when installed ✅
  ├── Offline dashboard view (cached) ✅
  ├── Push notifications ✅
  ├── File upload from device ✅
  └── Biometric login (device-supported) ✅

MINIMUM REQUIREMENTS:
  RAM: 4GB (8GB recommended for large consolidations)
  Screen resolution: 1280×720 minimum (1920×1080 recommended)
  Internet: 10 Mbps for file uploads, 1 Mbps for general use
```

---

## Keyboard Shortcuts

```
GLOBAL:
  Ctrl/Cmd + K        Open command palette (search everything)
  Ctrl/Cmd + /        Show all shortcuts
  Ctrl/Cmd + B        Toggle sidebar
  Escape              Close modal / cancel current action
  ?                   Help overlay

NAVIGATION:
  G then D            Go to Dashboard
  G then M            Go to MIS Manager
  G then R            Go to Reconciliation
  G then C            Go to Consolidation
  G then P            Go to Reports
  G then S            Go to Settings

TABLES & DATA:
  J / K               Navigate rows down / up
  Enter               Open selected row
  Ctrl/Cmd + A        Select all rows
  Ctrl/Cmd + E        Export selected
  /                   Focus search in current module

REPORTS:
  Ctrl/Cmd + P        Print / PDF current report
  Ctrl/Cmd + Shift + E Export to Excel
  Ctrl/Cmd + Shift + C Copy table data

AI CHAT:
  Ctrl/Cmd + Enter    Submit query
  Up arrow            Previous query
  Escape              Clear input
```

---

## Accessibility

```
SCREEN READER SUPPORT:
  ARIA labels on all interactive elements
  Keyboard navigation for all features
  Focus indicators visible at all times
  Screen reader tested with: NVDA (Windows), VoiceOver (Mac/iOS)

HIGH CONTRAST MODE:
  Settings → Accessibility → High Contrast
  Increases contrast ratios to WCAG AAA standard
  All charts: patterns used in addition to colour (colour-blind safe)

FONT SIZE:
  Settings → Accessibility → Text Size
  Options: Small / Medium (default) / Large / Extra Large
  Affects all text throughout the platform

COLOUR BLIND SUPPORT:
  All status indicators use icons AND colour (not colour alone)
  Charts: deuteranopia and protanopia safe palette available
  Settings → Accessibility → Colour Blind Mode

WCAG COMPLIANCE:
  Target: WCAG 2.1 AA
  Regular audits using axe-core automated testing
```

---

## Video Tutorials

```
Available at: docs.yourplatform.com/tutorials

Getting Started:
  ├── Platform overview (5 min)
  ├── First MIS upload (8 min)
  ├── Setting up reconciliation (6 min)
  └── Running your first consolidation (10 min)

Monthly Close Workflow:
  ├── Month-end close walkthrough (15 min)
  ├── Using the Closing Checklist (5 min)
  └── Generating the Board Pack (8 min)

AI Features:
  ├── Using AI Chat for analysis (7 min)
  └── Understanding AI commentary (5 min)

For CA Firms:
  ├── Managing multiple clients (10 min)
  └── Setting up auditor access (4 min)
```
