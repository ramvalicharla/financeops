# FinanceOps Platform â€” HR Module, Sales Intelligence & Enterprise OS Vision
> Version 1.0 | Status: Locked
> Expansion roadmap: Finance â†’ HR â†’ Sales â†’ Full Enterprise Operating System

---

## Table of Contents
1. [Strategic Vision](#1-strategic-vision)
2. [Sequencing & Principles](#2-sequencing--principles)
3. [HR Module â€” Complete Specification](#3-hr-module--complete-specification)
4. [Microsoft Teams & Slack Integration](#4-microsoft-teams--slack-integration)
5. [HR Manual AI Assistant](#5-hr-manual-ai-assistant)
6. [Sales Intelligence Layer](#6-sales-intelligence-layer)
7. [CRM Connector Architecture](#7-crm-connector-architecture)
8. [Employee Self-Service Portal](#8-employee-self-service-portal)
9. [Enterprise OS â€” Unified Vision](#9-enterprise-os--unified-vision)
10. [Data Architecture â€” HR & Sales](#10-data-architecture--hr--sales)
11. [Security & Compliance â€” HR Specific](#11-security--compliance--hr-specific)
12. [Integration Architecture](#12-integration-architecture)
13. [Revised Platform Positioning](#13-revised-platform-positioning)
14. [Implementation Plan â€” HR & Sales](#14-implementation-plan--hr--sales)
15. [Business Model Impact](#15-business-model-impact)

---

## 1. Strategic Vision

### What We Are Building Toward

```
TODAY (Finance Platform):
  3â€“10 users per tenant
  Finance team only
  $49â€“449/month subscription

PHASE 2 (Finance + HR):
  10â€“50 users per tenant
  Finance + HR team + all employees (self-service)
  $149â€“999/month subscription
  HR data local-only (key differentiator)

PHASE 3 (Finance + HR + Sales):
  10â€“500 users per tenant
  Every function has a workspace
  $299â€“2,499/month subscription
  Pipeline â†’ financial forecast bridge (unique in market)

PHASE 4 (Full Enterprise OS):
  Every employee logs in
  Finance + HR + Sales + Executive + Individual Contributor views
  $499â€“5,000/month subscription
  Raise Series A on this vision ($5Mâ€“15M ARR proof)
```

### The Core Insight
```
Every enterprise runs on three data streams:
  MONEY  â†’ Finance (we built this)
  PEOPLE â†’ HR (we're building this next)
  REVENUE â†’ Sales (we're building this after)

The intelligence layer that connects all three
and makes them talk to each other
does not exist at mid-market price points.

That is what we are building.
```

### What We Are NOT Building
```
âŒ NOT replacing Salesforce, Workday, or Darwinbox
   We integrate with them and add intelligence above them

âŒ NOT a generic HRMS (leave management, payroll processing)
   We connect to existing HRMS tools and surface intelligence

âŒ NOT a CRM
   We connect to existing CRMs and bridge pipeline to financials

âœ… We are the intelligence and analytics layer
   that connects Finance + HR + Sales
   in one auditable, AI-native platform
```

---

## 2. Sequencing & Principles

### Build Order (Non-Negotiable)
```
PHASE 1 (NOW):          Finance Platform complete (Phases 0â€“6)
                         First 20 paying customers
                         Generating revenue
                         â†“
PHASE 2 (MONTH 6â€“9):    HR Module
                         Once Finance is live and stable
                         â†“
PHASE 3 (MONTH 12â€“15):  Sales Intelligence Layer
                         Once HR module is stable
                         â†“
PHASE 4 (MONTH 18â€“24):  Full Enterprise OS
                         Every employee login
                         Unified dashboard
                         Series A fundraise

DO NOT start Phase 2 before Phase 1 is live and paying.
The most common startup mistake: building breadth before depth.
Finance depth is your moat. Protect it.
```

### HR Module Principles
```
1. LOCAL-ONLY by default
   All HR data processed and stored on-premise or local instance.
   No HR data to cloud without explicit, per-category opt-in.
   Reason: salary data, performance reviews, disciplinary records,
   medical information â€” employees have legal rights in all jurisdictions.

2. STRICTEST access controls on the platform
   HR data is more sensitive than financial data.
   Role-based access stricter than any other module.
   HR data NEVER bleeds into finance data views (except aggregated cost).

3. INTEGRATOR, NOT REPLACER
   We do not process payroll. We sync from payroll tools.
   We do not manage leave. We sync from HRMS tools.
   We surface intelligence and answer questions.

4. COMPLIANCE-FIRST
   GDPR right to erasure: employee requests deletion â†’ HR data deleted
   (financial data about that employee's cost: retained but anonymised)
   DPDP (India): data localisation enforced
   Local labour law calendars pre-loaded by jurisdiction

5. EMPLOYEE TRUST
   Employees must trust the platform with their data.
   Transparency: employees can see exactly what data is stored about them.
   Control: employees can request corrections.
   Privacy: managers cannot see more than they need.
```

### Sales Module Principles
```
1. BRIDGE, NOT REPLACE
   CRM stays as system of record for deals and contacts.
   We pull pipeline data and bridge it to financial forecasts.
   Sales reps continue working in Salesforce/HubSpot.

2. FINANCIAL INTELLIGENCE FIRST
   Our unique value: connecting CRM pipeline to financial outcomes.
   Customer profitability + CRM data = decisions no one else can make.

3. REAL-TIME WHERE IT MATTERS
   Pipeline sync: daily (not real-time â€” CRM data changes constantly)
   Commission calculation: real-time as deals close
   Revenue recognition trigger: real-time as deals close
```

---

## 3. HR Module â€” Complete Specification

### Module Architecture
```
HR MODULE COMPONENTS:

CORE (Phase 2A â€” build first):
â”œâ”€â”€ HR Manual AI Assistant (highest immediate value)
â”œâ”€â”€ Employee Directory & Org Chart
â”œâ”€â”€ Headcount Intelligence (extends existing Finance headcount module)
â”œâ”€â”€ HRMS Connectors (read-only sync)
â”œâ”€â”€ Payslip Distribution (employees access own payslips)
â””â”€â”€ Teams / Slack HR Bot

EXTENDED (Phase 2B â€” build after Core is stable):
â”œâ”€â”€ Leave & Attendance Analytics
â”œâ”€â”€ Onboarding Tracker
â”œâ”€â”€ Offboarding Workflow
â”œâ”€â”€ Performance Cycle Tracker
â”œâ”€â”€ Expense Submission (feeds Finance AP module)
â””â”€â”€ Employee Self-Service Portal

FUTURE (Phase 4 â€” Enterprise OS):
â”œâ”€â”€ Learning & Development Tracker
â”œâ”€â”€ Recruitment Pipeline (ATS integration)
â””â”€â”€ Compensation Benchmarking
```

### HRMS Integrations
```
INDIA (primary market):
  Darwinbox     â€” REST API, OAuth2, most enterprise India companies
  Keka          â€” REST API, OAuth2, mid-market India favourite
  greytHR       â€” REST API, widely used in SME India
  Zoho People   â€” REST API, OAuth2, used by Zoho ecosystem customers
  sumHR         â€” REST API, emerging India player
  Razorpay Payroll â€” REST API (payroll specifically)

GLOBAL:
  Workday       â€” REST API (enterprise, complex but most enterprise)
  ADP Workforce Now â€” REST API
  BambooHR      â€” REST API, OAuth2
  Rippling      â€” REST API (US mid-market)
  Gusto         â€” REST API (US SME)
  HiBob         â€” REST API (global mid-market)

PAYROLL SPECIFIC:
  ADP Payroll   â€” REST API
  Paychex       â€” REST API (US)
  Papaya Global â€” REST API (global payroll)

SYNC APPROACH (all connectors):
  Pull: daily sync of employee master, leave balances, attendance
  Frequency: configurable (daily default, hourly for large tenants)
  Direction: one-way pull (HRMS is system of record)
  Exception: payslip data (push from Finance to employee portal)
```

### Headcount Module (Extended from Finance)
```
EXISTING (already in Finance module):
  â”œâ”€â”€ Monthly HC movement (joiners, leavers)
  â”œâ”€â”€ Voluntary/involuntary classification
  â”œâ”€â”€ Utilisation (billable vs non-billable)
  â”œâ”€â”€ Seat cost by location
  â””â”€â”€ Attrition metrics

NEW IN HR MODULE:
  â”œâ”€â”€ Live org chart (from HRMS sync)
  â”œâ”€â”€ Role-level analytics (how many at each grade)
  â”œâ”€â”€ Tenure distribution (years of service histogram)
  â”œâ”€â”€ Gender diversity metrics
  â”œâ”€â”€ Department headcount budget vs actual
  â”œâ”€â”€ Open positions vs filled positions
  â”œâ”€â”€ Time-to-hire tracking
  â””â”€â”€ Succession planning flags (key roles with no backup)

SHARED DATA (Finance + HR both read):
  â”œâ”€â”€ Headcount numbers (Finance for cost, HR for people)
  â”œâ”€â”€ Salary cost (Finance sees total, HR sees individual)
  â””â”€â”€ Attrition impact (Finance sees cost, HR sees people impact)

DATA SEPARATION:
  Finance sees: headcount count, total cost, attrition rate
  HR sees: individual names, salaries, performance, personal data
  Overlap is intentional â€” architecture enforces the boundary
```

### Leave & Attendance Analytics
```
SYNCED FROM HRMS (read-only):
  â”œâ”€â”€ Leave balances per employee per leave type
  â”œâ”€â”€ Leave requests (pending, approved, rejected)
  â”œâ”€â”€ Attendance records (present, absent, WFH, travel)
  â””â”€â”€ Holiday calendar by location/entity

INTELLIGENCE LAYER WE ADD:
  â”œâ”€â”€ Team leave heatmap (who is off when â€” manager view)
  â”œâ”€â”€ Leave liability (total accrued leave cost per entity)
  â”‚     feeds Finance balance sheet provision
  â”œâ”€â”€ Absenteeism analysis (patterns, by location, by team)
  â”œâ”€â”€ Leave encashment cost (at year-end or exit)
  â””â”€â”€ Compliance: ensure minimum leave taken per jurisdiction

ALERTS:
  â”œâ”€â”€ Employee has >30 days leave accumulated (lapse risk)
  â”œâ”€â”€ Team has >40% on leave same week (delivery risk)
  â”œâ”€â”€ New joiner hasn't taken onboarding leave (process flag)
  â””â”€â”€ Leave liability >$X per entity (Finance alert)
```

### Onboarding & Offboarding Workflows
```
ONBOARDING TRACKER:
  â”œâ”€â”€ Pre-joining checklist (offer acceptance, document collection)
  â”œâ”€â”€ Day 1 checklist (IT setup, access provisioning, orientation)
  â”œâ”€â”€ Week 1 checklist (team introductions, system access)
  â”œâ”€â”€ 30/60/90 day milestones
  â”œâ”€â”€ Document collection: contracts, ID proof, tax forms, bank details
  â””â”€â”€ Status visible to: HR, Manager, New Employee (their own)

OFFBOARDING WORKFLOW:
  â”œâ”€â”€ Exit initiation (by HR or employee)
  â”œâ”€â”€ Notice period tracking (start date â†’ last working day)
  â”œâ”€â”€ Knowledge transfer tasks (assigned by manager)
  â”œâ”€â”€ Asset return checklist
  â”œâ”€â”€ System access revocation tracker
  â”œâ”€â”€ Full & Final settlement trigger (feeds Finance for F&F payment)
  â”œâ”€â”€ Exit interview recording
  â””â”€â”€ Alumni network opt-in

INTEGRATION:
  Platform revokes user access on last working day (automated)
  F&F amount â†’ Finance paysheet engine for final payment
  Exit classification â†’ updates headcount attrition type
```

### Performance Cycle Tracker
```
NOT a performance management system (don't replace).
A tracker of cycle completion and outcomes.

â”œâ”€â”€ Annual review cycle status (% complete by department)
â”œâ”€â”€ Mid-year check-in tracking
â”œâ”€â”€ Goal setting completion rates
â”œâ”€â”€ Ratings distribution (are managers rating on a curve?)
â”œâ”€â”€ Compensation review trigger (after ratings finalised)
â”‚     â†’ feeds salary revision into paysheet engine
â””â”€â”€ Promotion tracking (grade changes flagged in headcount)

INTEGRATION:
  If tenant uses Darwinbox/Workday performance: sync cycle status
  If no performance tool: manual entry of outcomes
```

---

## 4. Microsoft Teams & Slack Integration

### Architecture
```
TEAMS BOT (FinanceOps HR Assistant):
  Registered in Azure Bot Service
  Deployed as Teams app (installable by tenant admin)
  Auth: Azure AD SSO (user identity verified via Teams)
  Data: reads from HR module (tenant's own data only)
  Privacy: bot only returns data the user is authorised to see

SLACK BOT (FinanceOps HR Assistant):
  Deployed as Slack app (OAuth2 install flow)
  Auth: Slack user identity â†’ mapped to FinanceOps user
  Slash commands + natural language in channels/DMs
```

### What the Bot Can Answer
```
EMPLOYEE SELF-SERVICE (any employee):
  "How many days of annual leave do I have?"
  "What is the policy on work from home?"
  "When is the next public holiday in Bangalore?"
  "What documents do I need to submit for joining?"
  "What is the notice period for my grade?"
  "How do I submit an expense claim?"
  "What is the maternity leave policy?"
  "How do I apply for leave?"

MANAGER QUERIES (managers only, about their team):
  "Who from my team is on leave this week?"
  "What is the attrition in my team this quarter?"
  "How many open positions do I have approved?"
  "What is the utilisation of my team this month?"

HR TEAM QUERIES (HR Manager/CHRO):
  "How many employees joined this month?"
  "What is the total leave liability for India?"
  "Which departments have the highest attrition?"
  "How many employees complete onboarding on time?"

FINANCE QUERIES (redirected to Finance module â€” already built):
  "What is the headcount cost for Q3?" â†’ Finance module
  "Show me contractor vs permanent ratio" â†’ Finance module

WHAT THE BOT CANNOT DO:
  âŒ Change leave records (read-only, HRMS is system of record)
  âŒ Approve anything (approvals happen in HRMS/email)
  âŒ Access another employee's personal data
  âŒ Answer questions not covered by HR manual or HR data
```

### Teams Bot Technical Implementation
```python
# backend/integrations/teams/hr_bot.py

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import Activity

class HRAssistantBot(ActivityHandler):

    async def on_message_activity(self, turn_context: TurnContext):
        user_query = turn_context.activity.text
        teams_user_id = turn_context.activity.from_property.id

        # Resolve Teams user â†’ FinanceOps user â†’ tenant
        user = await resolve_teams_user(teams_user_id)
        if not user:
            await turn_context.send_activity(
                "Please contact your HR team to link your Teams account."
            )
            return

        # Route query through AI Gateway
        # HR queries: use local model only (data never leaves platform)
        response = await ai_gateway.query(
            query=user_query,
            context_type="hr",
            user_id=user.id,
            tenant_id=user.tenant_id,
            force_local=True,  # HR data: local model only
            retrieve_from=["hr_manual", "hr_data"]
        )

        # Format for Teams (adaptive cards for structured data)
        if response.data_type == "table":
            card = build_adaptive_card_table(response.data)
            await turn_context.send_activity(Activity(attachments=[card]))
        else:
            await turn_context.send_activity(response.text)

        # Log query (anonymised) for HR analytics
        await log_hr_bot_query(user.id, user_query, response.intent)
```

### Slack Bot Implementation
```python
# backend/integrations/slack/hr_bot.py

from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

slack_app = App(token=settings.SLACK_BOT_TOKEN)

@slack_app.message("leave balance")
@slack_app.message("annual leave")
async def handle_leave_query(message, say, client):
    slack_user_id = message["user"]
    user = await resolve_slack_user(slack_user_id)

    leave_data = await get_employee_leave_balance(user.employee_id)

    await say(
        blocks=[{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Your Leave Balance:*\n"
                        f"â€¢ Annual Leave: {leave_data.annual} days\n"
                        f"â€¢ Casual Leave: {leave_data.casual} days\n"
                        f"â€¢ Sick Leave: {leave_data.sick} days"
            }
        }]
    )

@slack_app.event("app_mention")
async def handle_mention(event, say):
    # Natural language handler â€” routes to AI Gateway (local model)
    query = event["text"]
    user_id = event["user"]
    response = await process_hr_query(query, user_id)
    await say(response)
```

---

## 5. HR Manual AI Assistant

### Architecture
```
DOCUMENT INGESTION:
  HR team uploads HR Manual (PDF or Word)
  Platform: extracts text â†’ chunks â†’ generates embeddings â†’ stores in pgvector
  Processing: fully local (sentence-transformers, no cloud call)
  Storage: tenant's own vector store (isolated, local)

QUERY PROCESSING:
  Employee asks question (Teams / Slack / Web)
  Platform: embed query â†’ vector similarity search â†’ retrieve top-5 chunks
  Platform: inject chunks into prompt â†’ local LLM answers
  Answer: includes section citation (e.g. "Section 4.2, HR Policy 2025")
  Verification: answer validated against retrieved chunks (hallucination check)

KEY DESIGN DECISIONS:
  â”œâ”€â”€ Local model ONLY for HR manual queries (data sensitivity)
  â”œâ”€â”€ Every answer cites the exact section of the manual
  â”œâ”€â”€ If answer not found in manual: "This is not covered in the current
  â”‚    HR Manual. Please contact your HR team." (never hallucinate policy)
  â”œâ”€â”€ Multi-version support: HR Manual v2025 supersedes v2024
  â”‚    Old version preserved but not used for new queries
  â””â”€â”€ Multi-language: query in Hindi, answer in Hindi (same embeddings)
```

### HR Manual Ingestion
```python
# backend/modules/hr/manual_processor.py

class HRManualProcessor:

    async def ingest(self, file: UploadFile, tenant_id: str) -> HRManual:
        # 1. Extract text preserving section structure
        text_blocks = await extract_pdf_with_sections(file)
        # text_blocks: [{section: "4.2", title: "Notice Period", text: "..."}]

        # 2. Chunk intelligently (by section, not fixed tokens)
        chunks = []
        for block in text_blocks:
            sub_chunks = chunk_by_section(block, max_tokens=500)
            for chunk in sub_chunks:
                chunks.append(HRManualChunk(
                    section=block.section,
                    title=block.title,
                    text=chunk,
                    tenant_id=tenant_id,
                    manual_version=extract_version(file.filename),
                    effective_date=extract_effective_date(text_blocks)
                ))

        # 3. Generate embeddings (local â€” sentence-transformers)
        embeddings = await generate_embeddings_local(
            [c.text for c in chunks]
        )

        # 4. Store in pgvector (tenant-isolated)
        await store_hr_manual_vectors(chunks, embeddings, tenant_id)

        # 5. Mark as current version (supersede previous)
        await mark_previous_versions_superseded(tenant_id)

        return HRManual(
            tenant_id=tenant_id,
            version=chunks[0].manual_version,
            chunks_indexed=len(chunks),
            sections_found=len(set(c.section for c in chunks)),
            status="active"
        )

    async def query(self, question: str, user_id: str,
                    tenant_id: str) -> HRManualAnswer:
        # 1. Embed query (local)
        query_embedding = await embed_local(question)

        # 2. Retrieve relevant chunks
        relevant_chunks = await vector_search(
            embedding=query_embedding,
            tenant_id=tenant_id,
            table="hr_manual_vectors",
            top_k=5,
            min_similarity=0.70  # don't return low-relevance results
        )

        if not relevant_chunks:
            return HRManualAnswer(
                answer="This topic is not covered in the current HR Manual. "
                       "Please contact your HR team directly.",
                confidence=0.0,
                source_sections=[]
            )

        # 3. Build prompt with retrieved context
        context = "\n\n".join([
            f"[Section {c.section}: {c.title}]\n{c.text}"
            for c in relevant_chunks
        ])

        prompt = f"""You are an HR assistant. Answer the employee's question
        based ONLY on the HR Manual sections provided below.
        If the answer is not in the provided sections, say so clearly.
        Always cite the section number in your answer.
        Never make up policies or procedures.

        HR Manual Sections:
        {context}

        Employee Question: {question}

        Answer (cite section numbers):"""

        # 4. Local LLM answers (NEVER cloud for HR manual queries)
        answer = await ollama.generate(
            model="mistral:7b",
            prompt=prompt,
            options={"temperature": 0.1}  # low temp = consistent, factual
        )

        # 5. Extract cited sections from answer
        cited_sections = extract_section_citations(answer)

        return HRManualAnswer(
            answer=answer,
            confidence=relevant_chunks[0].similarity_score,
            source_sections=cited_sections,
            manual_version=relevant_chunks[0].manual_version
        )
```

### Multi-Language Support
```
Supported query languages (auto-detected):
  English, Hindi, Tamil, Telugu, Kannada, Malayalam,
  Arabic, French, German, Spanish, Mandarin

How it works:
  1. Detect query language
  2. Translate query to English (local model)
  3. Perform vector search (English embeddings work cross-language)
  4. Retrieve relevant sections (in English)
  5. Translate answer to original query language (local model)
  6. Preserve section citations verbatim (not translated)

Result:
  Employee asks in Hindi â†’ receives answer in Hindi
  with English section reference ("Section 4.2 / à¤§à¤¾à¤°à¤¾ 4.2")
```

---

## 6. Sales Intelligence Layer

### Philosophy
```
We do NOT replace Salesforce or HubSpot.
We connect to them and surface financial intelligence
that the CRM alone cannot provide.

Our three unique contributions:

1. PIPELINE â†’ FORECAST BRIDGE
   CRM pipeline (deals Ã— probability) feeds the Finance forecast engine.
   No other tool does this automatically at mid-market price.

2. CUSTOMER PROFITABILITY
   CRM shows revenue. Finance shows cost and margin.
   Combined: which customers are actually profitable?
   Sales team finally knows which deals to chase and which to let go.

3. CONTRACT â†” DEAL LIFECYCLE
   CRM deal won â†’ auto-creates contract in Contract module
   Contract delivered â†’ updates CRM deal status
   Invoice issued â†’ updates CRM with billing status
   One source of truth, two systems synced automatically.
```

### CRM Data Synced (Daily Pull)
```
FROM CRM TO PLATFORM:
  â”œâ”€â”€ Accounts (customers and prospects)
  â”œâ”€â”€ Deals/Opportunities (pipeline)
  â”‚     Fields: name, stage, amount, probability, close date,
  â”‚             owner, account, created date, last activity
  â”œâ”€â”€ Activities (calls, emails, meetings â€” summary only)
  â”œâ”€â”€ Contacts (name, role â€” no personal data stored)
  â””â”€â”€ Products/Line Items (what is being sold)

NOT SYNCED (stays in CRM):
  â”œâ”€â”€ Email content
  â”œâ”€â”€ Personal contact details (phone, personal email)
  â”œâ”€â”€ Notes and call recordings
  â””â”€â”€ Anything not needed for financial intelligence
```

### Pipeline â†’ Financial Forecast Bridge
```python
# backend/modules/sales/pipeline_bridge.py

class PipelineForecastBridge:

    async def compute_pipeline_contribution(
        self, tenant_id: str, period: ForecastPeriod
    ) -> PipelineContribution:
        """
        Converts CRM pipeline into probability-weighted revenue forecast.
        This feeds directly into the Finance forecasting engine (Layer 3).
        """

        deals = await get_active_pipeline(tenant_id, period)

        by_stage = {}
        total_weighted = 0

        for deal in deals:
            # Use CRM probability OR override with historical close rate per stage
            historical_close_rate = await get_historical_close_rate(
                tenant_id, deal.stage, deal.owner_id
            )
            effective_probability = (
                historical_close_rate
                if historical_close_rate
                else deal.crm_probability / 100
            )

            weighted_value = deal.amount * effective_probability

            by_stage.setdefault(deal.stage, []).append({
                "deal": deal.name,
                "account": deal.account_name,
                "amount": deal.amount,
                "crm_probability": deal.crm_probability,
                "effective_probability": effective_probability * 100,
                "weighted_value": weighted_value,
                "close_date": deal.close_date,
                "owner": deal.owner_name
            })

            total_weighted += weighted_value

        return PipelineContribution(
            period=period,
            total_pipeline_value=sum(d.amount for d in deals),
            total_weighted_value=total_weighted,
            deal_count=len(deals),
            by_stage=by_stage,
            # AI commentary on pipeline quality
            ai_commentary=await generate_pipeline_commentary(
                deals, historical_rates=by_stage
            )
        )

    async def get_revenue_coverage(self, tenant_id: str) -> RevenueCoverage:
        """
        The killer feature: total revenue coverage vs target.
        Contracted + Run Rate + Pipeline = Coverage
        """
        backlog = await get_contracted_backlog(tenant_id)      # Finance module
        run_rate = await get_run_rate_projection(tenant_id)    # Finance module
        pipeline = await compute_pipeline_contribution(tenant_id)  # This module

        annual_target = await get_annual_budget_revenue(tenant_id)  # Finance module

        coverage = backlog + run_rate + pipeline.total_weighted_value
        gap = annual_target - coverage
        gap_from_new_business = max(0, gap)

        return RevenueCoverage(
            contracted_backlog=backlog,
            run_rate=run_rate,
            pipeline_weighted=pipeline.total_weighted_value,
            total_coverage=coverage,
            annual_target=annual_target,
            gap=gap,
            gap_pct=gap / annual_target * 100,
            message=f"You need ${gap_from_new_business:,.0f} of additional "
                    f"new business to close the gap. "
                    f"At current pipeline close rates, you need "
                    f"${gap_from_new_business / 0.35:,.0f} of new pipeline."
        )
```

### Customer Profitability Intelligence
```
WHAT WE COMBINE:

FROM CRM:
  â”œâ”€â”€ Contract value (ACV / TCV)
  â”œâ”€â”€ Deal source (which channel)
  â””â”€â”€ Account size and segment

FROM FINANCE:
  â”œâ”€â”€ Revenue recognised (actual, from RevRec module)
  â”œâ”€â”€ Direct cost (consultant/delivery cost from paysheets)
  â”œâ”€â”€ Overhead allocation (from seat cost methodology)
  â””â”€â”€ Invoice and collection history (DSO per customer)

COMPUTED INTELLIGENCE:
  â”œâ”€â”€ Gross margin per customer (revenue - direct cost)
  â”œâ”€â”€ Net margin per customer (after overhead allocation)
  â”œâ”€â”€ LTV per customer segment
  â”œâ”€â”€ CAC payback per customer (if CAC data from marketing)
  â”œâ”€â”€ Collection quality (DSO vs terms â€” is this customer slow pay?)
  â””â”€â”€ Account growth rate (year-over-year spend)

CUSTOMER HEALTH SCORE (Finance + Sales combined):
  Factors: margin %, revenue growth, on-time payment, contract renewal,
           pipeline opportunities (expansion), support cost (if tracked)
  Score: 0â€“100 per customer
  
  High Revenue + High Margin + On-time payment = ðŸŸ¢ Grow
  High Revenue + Low Margin = ðŸŸ¡ Reprice or reduce cost
  Low Revenue + High Margin = ðŸŸ¡ Expand
  High Revenue + Negative Margin = ðŸ”´ Restructure or exit

OUTPUT IN PLATFORM:
  Customer dashboard (Finance + CRM data combined)
  "Customer X: $480K revenue, 34% gross margin, 67 days DSO (terms: 30),
   $120K open pipeline, contract renews in 45 days.
   Action: Renew and reprice â€” current rate $115/hr, market rate $130/hr."
```

### Commission Engine
```
COMMISSION RULES (configured by Finance Leader):
  â”œâ”€â”€ % of deal value on close
  â”œâ”€â”€ Tiered (0-$100K: 5%, $100K-$500K: 7%, >$500K: 10%)
  â”œâ”€â”€ Margin-based (higher commission for higher margin deals)
  â”œâ”€â”€ Accelerators (above quota: higher %)
  â””â”€â”€ Clawback rules (if customer churns within 6 months)

COMPUTATION FLOW:
  Deal closes in CRM
      â†“
  Platform pulls deal via webhook/daily sync
      â†“
  Commission engine computes based on rules
      â†“
  Commission accrual posted to Finance (P&L impact)
      â†“
  Commission payable added to next paysheet (paysheet engine)
      â†“
  Sales rep sees own commission in self-service portal

FINANCE INTEGRATION:
  Commission accrual â†’ P&L (selling expense)
  Commission payable â†’ Balance sheet liability
  Commission paid â†’ Paysheet (cleared from liability)
  Full cycle automated, auditable
```

---

## 7. CRM Connector Architecture

### Same Pattern as ERP Connectors
```python
# backend/modules/crm_connectors/base.py

class CRMConnector(ABC):
    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool: pass

    @abstractmethod
    async def pull_accounts(self, since: datetime) -> list[Account]: pass

    @abstractmethod
    async def pull_pipeline(self, since: datetime) -> list[Deal]: pass

    @abstractmethod
    async def pull_closed_deals(self, period: Period) -> list[Deal]: pass

    @abstractmethod
    async def update_deal_stage(self, deal_id: str, stage: str) -> bool: pass
    # Used to update CRM when contract milestone hit or invoice issued

    @abstractmethod
    async def handle_webhook(self, payload: dict) -> WebhookEvent: pass
    # Deal won, deal lost, stage changed


# Implementations
class SalesforceConnector(CRMConnector): ...     # OAuth2 + REST API
class HubSpotConnector(CRMConnector): ...        # OAuth2 + REST API
class PipedriveConnector(CRMConnector): ...      # OAuth2 + REST API
class ZohoCRMConnector(CRMConnector): ...        # OAuth2 + REST API
class FreshsalesConnector(CRMConnector): ...     # API Key + REST API
```

### CRM Webhook Handlers
```python
# Deal won in CRM â†’ auto-trigger in platform
@router.post("/webhooks/crm/deal-won")
async def handle_deal_won(payload: dict, tenant_id: str):
    deal = parse_deal_webhook(payload)

    # 1. Create contract record in Contract module (pre-populated)
    contract = await create_contract_from_deal(deal, tenant_id)

    # 2. Set up revenue recognition (prompt Finance Leader to confirm method)
    await create_rev_rec_prompt(contract, tenant_id)

    # 3. Compute commission accrual
    commission = await compute_commission(deal, tenant_id)
    await post_commission_accrual(commission, tenant_id)

    # 4. Update forecast (remove from pipeline, add to backlog)
    await update_forecast_on_close(deal, tenant_id)

    # 5. Notify Finance Leader
    await notify_finance_leader(
        f"Deal won: {deal.name} (${deal.amount:,.0f}) â€” "
        f"Contract created, rev rec setup required."
    )
```

---

## 8. Employee Self-Service Portal

### What Every Employee Sees
```
MY WORKSPACE (role: Individual Contributor):

LEFT NAV:
  My Payslips         â† current + history
  My Leave            â† balance, apply, history
  My Expenses         â† submit, track, history
  Company Policies    â† HR manual search
  My Team             â† org chart (their place in it)
  Help                â† HR bot / raise ticket

DASHBOARD:
  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  â”‚  Hello, Priya                March 2025     â”‚
  â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
  â”‚ Annual Leave â”‚ Casual Leave â”‚ Sick Leave    â”‚
  â”‚  12 days     â”‚   5 days     â”‚  4 days       â”‚
  â”‚  remaining   â”‚  remaining   â”‚  remaining    â”‚
  â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
  â”‚ Latest Payslip: February 2025  [Download]   â”‚
  â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
  â”‚ Pending Actions:                            â”‚
  â”‚  â€¢ Submit expense for Feb travel            â”‚
  â”‚  â€¢ Complete onboarding task: IT policy sign â”‚
  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

PAYSLIP ACCESS:
  Employee sees own payslips only (uploaded by HR/Finance)
  Download as PDF
  View online (masked: shows net, not gross, to non-finance employees)
  History: all payslips since joining

EXPENSE SUBMISSION:
  Submit expense with: category, amount, date, description, receipt upload
  Manager approves in platform
  Approved expense â†’ Finance AP module for payment processing
  Employee tracks status: Submitted â†’ Approved â†’ Paid
```

### Role-Specific Views
```
MANAGER (Team Lead / Project Manager):
  Additional to employee view:
  â”œâ”€â”€ Team leave calendar (who is off when)
  â”œâ”€â”€ Team expense approvals (pending approval queue)
  â”œâ”€â”€ Team headcount summary
  â”œâ”€â”€ Project utilisation (their project only)
  â””â”€â”€ Team performance cycle status

HR MANAGER / CHRO:
  Full HR module access:
  â”œâ”€â”€ All employee data (with audit trail)
  â”œâ”€â”€ Payroll overview (not individual salaries unless authorised)
  â”œâ”€â”€ Leave management analytics
  â”œâ”€â”€ Onboarding/offboarding queue
  â”œâ”€â”€ Compliance calendar (labour law, statutory filings)
  â””â”€â”€ HR manual management (upload, version, publish)

SALES REP:
  Additional to employee view:
  â”œâ”€â”€ My pipeline (from CRM, synced)
  â”œâ”€â”€ My commission tracker (real-time calculation)
  â”œâ”€â”€ My quota attainment
  â”œâ”€â”€ My customer health scores
  â””â”€â”€ My contracts (won deals â†’ contract status)

FINANCE LEADER:
  Full Finance platform + HR cost view + Sales intelligence view
  The only role that sees across all three dimensions
```

---

## 9. Enterprise OS â€” Unified Vision

### The Single Platform for Every Business Function

```
PLATFORM STRUCTURE (Phase 4 â€” Enterprise OS):

NAVIGATION (role-aware â€” shows only what you can access):

For CFO:
  Finance â† (full platform)
  People  â† (aggregated headcount + cost only)
  Revenue â† (pipeline + customer profitability)
  Reports â† (unified board pack)

For CHRO:
  People  â† (full HR module)
  Finance â† (headcount cost only, no P&L)
  Reports â† (people analytics reports)

For CRO/Sales:
  Revenue â† (full sales intelligence)
  Finance â† (customer profitability, commission)
  Reports â† (sales performance reports)

For CEO:
  Executive Dashboard â† (Finance + People + Sales unified)
  Finance â† (full)
  People  â† (full)
  Revenue â† (full)
  Reports â† (board pack â€” all three dimensions)

For Employee:
  My Workspace â† (payslip, leave, expenses, policies)
  Company     â† (org chart, announcements, policies)
  Help        â† (HR bot, IT support link)
```

### Unified Board Pack (Phase 4 Enhancement)
```
Existing 10 sections + new sections:

Section 11: People Summary
  â”œâ”€â”€ Headcount movement (already in Finance pack)
  â”œâ”€â”€ Attrition analysis with qualitative context (HR data)
  â”œâ”€â”€ Key hires and departures
  â”œâ”€â”€ Succession risk flags
  â””â”€â”€ Diversity metrics (if tracked)

Section 12: Revenue Pipeline
  â”œâ”€â”€ CRM pipeline summary (from Sales module)
  â”œâ”€â”€ Pipeline â†’ forecast bridge (coverage vs target)
  â”œâ”€â”€ Customer health summary (top 10 customers)
  â”œâ”€â”€ Win/loss analysis (last quarter)
  â””â”€â”€ Expansion revenue opportunities

Section 13: Executive Summary (Unified)
  â”œâ”€â”€ Finance: EBITDA vs budget
  â”œâ”€â”€ People: Headcount vs plan, attrition rate
  â”œâ”€â”€ Revenue: Pipeline coverage, win rate
  â””â”€â”€ Forward look: What to watch next month (AI-generated)
```

### The Three-Dimensional CEO Dashboard
```
EXECUTIVE DASHBOARD (real-time, role: CEO/Board):

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    EXECUTIVE OVERVIEW                         â”‚
â”‚                      March 2025                              â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚   REVENUE    â”‚    EBITDA     â”‚  HEADCOUNT   â”‚   PIPELINE    â”‚
â”‚   $4.2M      â”‚   $840K       â”‚    247       â”‚   $6.1M       â”‚
â”‚  vs $4.0M    â”‚  vs $800K     â”‚  vs 250 plan â”‚  78% coverage â”‚
â”‚  â†‘5% vs plan â”‚  â†‘5% vs plan  â”‚  â†“3 vs plan  â”‚  âœ… On track  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  TOP 3 THINGS THAT NEED YOUR ATTENTION:                      â”‚
â”‚  1. Customer X margin declined to 8% â€” action required       â”‚
â”‚  2. India attrition spiked to 28% annualised this quarter    â”‚
â”‚  3. Pipeline gap: need $1.2M new business to hit annual plan â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  [Finance Detail] [People Detail] [Revenue Detail]          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## 10. Data Architecture â€” HR & Sales

### Strict Data Boundaries
```
THREE DATA DOMAINS â€” NEVER MIXED:

FINANCE DATA:
  Tables:   financial_*, gl_*, mis_*, consolidation_*
  Visible:  Finance Leader, CFO, Auditor, Executive (aggregated)
  Contains: P&L, balance sheet, cash flow, contracts, forecasts

HR DATA (strictest):
  Tables:   hr_*, employee_*, leave_*, payslip_*
  Visible:  CHRO, HR Manager (all) | Manager (team only) | Employee (own only)
  Contains: names, salaries, performance, medical, disciplinary records
  Storage:  LOCAL ONLY by default (separate encrypted DB or schema)
  Encryption: field-level encryption on salary, medical, disciplinary data

SALES DATA:
  Tables:   crm_*, pipeline_*, commission_*
  Visible:  CRO, Sales Leader (all) | Sales Rep (own only) | Finance (margin)
  Contains: deals, pipeline, accounts (no personal contact data stored)

SHARED / BRIDGE TABLES:
  headcount_summary (Finance + HR aggregated â€” no individual data)
  customer_financials (Finance + Sales aggregated)
  commission_payable (Sales + Finance â€” amount only, no deal details)
  forecast_pipeline (Finance + Sales â€” weighted values only)

RLS POLICIES:
  hr_* tables: even Finance Leader cannot query directly
  Finance Leader sees hr_cost_by_department (aggregated view only)
  CEO sees executive_summary (aggregated view only)
  Cross-domain queries go through controlled views only
```

### Local-Only HR Data Architecture
```
DEPLOYMENT OPTIONS:

Option A â€” Full Cloud (Finance + Sales cloud, HR local):
  Finance data: Cloudflare R2 + PostgreSQL (cloud)
  HR data: SQLite + SQLCipher (local, encrypted, on company server)
  Sync: HR data never leaves company network
  Access: HR queries answered by local Ollama model

Option B â€” Hybrid (all cloud, HR in separate encrypted schema):
  Finance data: Cloud PostgreSQL (shared infrastructure)
  HR data: Separate PostgreSQL instance (tenant-dedicated)
  Encryption: Per-tenant encryption key (not shared with platform)
  Access: Platform cannot read HR data without tenant key

Option C â€” Full On-Premise (for large enterprise):
  Everything on company's own server
  Platform deployed as Docker containers on-premise
  No data ever leaves company network
  AI: local Ollama only
```

---

## 11. Security & Compliance â€” HR Specific

### HR Data Is Highest Classification
```
DATA CLASSIFICATION:
  Level 1 â€” Public:         Org chart (names, roles, departments)
  Level 2 â€” Internal:       Headcount numbers, attrition rates
  Level 3 â€” Confidential:   Salary ranges, performance ratings
  Level 4 â€” Restricted:     Individual salaries, disciplinary records,
                             medical data, individual performance ratings

LEVEL 4 CONTROLS (strictest):
  â”œâ”€â”€ Field-level encryption (AES-256, per-tenant key)
  â”œâ”€â”€ Access logged to immutable audit trail with full justification
  â”œâ”€â”€ Time-limited access (HR Manager can grant 24h access for specific purpose)
  â”œâ”€â”€ Two-person integrity for salary changes (HR + Finance sign-off)
  â”œâ”€â”€ Data masking in logs (salary shown as ****** in all logs)
  â””â”€â”€ No AI model ever sees Level 4 data in raw form
```

### GDPR / DPDP Right to Erasure
```python
# backend/modules/hr/gdpr.py

async def process_erasure_request(employee_id: str, tenant_id: str):
    """
    Employee requests deletion of personal data.
    Finance data retained (legally required) but anonymised.
    HR data deleted.
    """

    # HR DATA â€” DELETE (personal data, no legal retention requirement)
    await delete_hr_personal_data(employee_id, tenant_id)
    # Deletes: name, contact, salary history, performance, medical, disciplinary

    # FINANCE DATA â€” ANONYMISE (legal requirement to retain financial records)
    await anonymise_finance_records(employee_id, tenant_id)
    # Replaces name with: "Employee [hashed_id]"
    # Retains: salary cost amounts (for P&L accuracy)
    # Deletes: all personally identifiable fields

    # VECTOR MEMORY â€” DELETE (HR manual queries this employee made)
    await delete_employee_vectors(employee_id, tenant_id)

    # AUDIT TRAIL â€” RETAIN (legal requirement, anonymised)
    await anonymise_audit_trail(employee_id, tenant_id)
    # Replaces user reference with: "Deleted Employee [hashed_id]"

    # LOG THE ERASURE (itself part of audit trail)
    await log_erasure_request(employee_id, tenant_id, requested_at=datetime.utcnow())
```

---

## 12. Integration Architecture

### Full Integration Map
```
FINANCE ERPs (existing):        Tally, Zoho Books, QuickBooks, Xero,
                                 SAP, Dynamics 365, Sage, NetSuite

HR / PEOPLE TOOLS (new):        Darwinbox, Keka, greytHR, Zoho People,
                                 Workday, ADP, BambooHR, Rippling, Gusto

PAYROLL TOOLS (new):            ADP Payroll, Paychex, Razorpay Payroll,
                                 Papaya Global

CRM TOOLS (new):                Salesforce, HubSpot, Pipedrive, Zoho CRM,
                                 Freshsales

PRODUCTIVITY / COLLABORATION:   Microsoft Teams, Microsoft 365 (SSO + org chart)
                                 Google Workspace (SSO + org chart)
                                 Slack

ALL CONNECTORS SHARE:
  â”œâ”€â”€ Same base connector interface
  â”œâ”€â”€ Same OAuth2 / API key auth pattern
  â”œâ”€â”€ Same Celery worker queue (integration_sync_q)
  â”œâ”€â”€ Same sync history logging
  â”œâ”€â”€ Same error handling and retry logic
  â””â”€â”€ Same credit deduction model (10 credits per sync)
```

### Single Sign-On (SSO) â€” Mandatory for Enterprise OS
```
When every employee logs in, SSO is not optional.

SUPPORTED SSO PROVIDERS:
  Azure AD / Entra ID    â† Microsoft (most enterprise India/global)
  Google Workspace       â† Google (many India companies)
  Okta                   â† Enterprise identity provider
  SAML 2.0              â† Generic (covers most enterprise IdPs)

SSO FLOW:
  Employee visits app.yourplatform.com
  Redirected to company's IdP (Azure AD / Google)
  Employee authenticates with company credentials
  IdP sends assertion to platform
  Platform: maps IdP user to FinanceOps user (by email)
  Platform: checks role and module access
  Employee enters their role-appropriate workspace

BENEFIT:
  IT team manages access centrally
  Employee uses one password (company credentials)
  Offboarding: revoke Azure AD â†’ platform access instantly revoked
  MFA inherited from company IdP (no separate MFA setup needed)
```

---

## 13. Revised Platform Positioning

### The Name Problem
```
"FinanceOps" is too narrow for an Enterprise OS.
When every employee logs in, they won't relate to "FinanceOps."

OPTIONS:
  Option A: Keep "FinanceOps" for finance product,
            launch Enterprise OS under new brand
            (two products, same company)

  Option B: Rename platform to something broader
            Suggestions: "Intelligo", "Nexus", "Vantage", "Clarity",
            "Meridian", "Apex", "Stratum"

  Option C: Modular branding
            "FinanceOps by [CompanyName]" â€” Finance module
            "PeopleOps by [CompanyName]" â€” HR module
            "RevenueOps by [CompanyName]" â€” Sales module

RECOMMENDATION:
  Keep "FinanceOps" brand for now (Phase 1-2 is all finance).
  Decide on broader brand when starting Phase 3 (Sales module).
  No point renaming before you have a reason to.
```

### Revised Positioning Statement (Phase 4)
```
"The only platform that connects your Finance, People, and Revenue
 in one intelligent, auditable workspace.

 Finance teams get: consolidation, FDD, compliance, and AI-validated reporting.
 HR teams get: an AI assistant that knows your HR manual by heart.
 Sales teams get: the financial truth behind every pipeline deal.
 Every employee gets: their payslips, leave balance, and company policies.
 CEOs get: one dashboard that shows the real state of the business.

 At 1/50th the cost of enterprise alternatives.
 Certified. Auditable. Local-first where it matters."
```

---

## 14. Implementation Plan — HR & Sales

All implementation prompts in this section must use `FINOS_EXEC_PROMPT_TEMPLATE v1.1`
(defined in `docs/platform/02_IMPLEMENTATION_PLAN.md`), including sections 7A and 9A.

### Phase 2A â€” HR Core (Month 6â€“9 of roadmap)

```
CLAUDE CODE PROMPT â€” HR MODULE CORE:

Build the HR Module Core. Finance platform (Phases 0-6) is already built.
HR module must follow all existing platform patterns.

CRITICAL: All HR data uses local-only storage by default.
No HR data sent to cloud AI models under any circumstances.
All AI for HR queries: local Ollama (mistral:7b) only.

1. HR DATABASE SCHEMA
   - Separate schema: CREATE SCHEMA hr; (within same PostgreSQL instance)
   - Tables: hr_employees, hr_leave_balances, hr_payslips,
     hr_manual_vectors, hr_onboarding_tasks, hr_offboarding_tasks
   - All tables: tenant_id, RLS enforced
   - Field-level encryption: salary, medical, disciplinary columns
   - GDPR: erasure procedure implemented from day one

2. HRMS CONNECTORS (backend/modules/hrms_connectors/)
   - Base connector interface (same pattern as ERP connectors)
   - Implement: DarwinboxConnector, KekaConnector, greytHRConnector,
     ZohoePeopleConnector, BambooHRConnector
   - Sync: employee master, leave balances, attendance
   - Frequency: daily (Celery Beat) + manual trigger
   - Credits: 10 per sync run

3. HR MANUAL AI ASSISTANT (backend/modules/hr/manual_processor.py)
   - PDF/Word ingestion â†’ section-aware chunking â†’ local embeddings
   - pgvector storage (hr schema, tenant-isolated)
   - Query: embed â†’ retrieve â†’ local LLM (mistral:7b) â†’ answer with citation
   - Multi-language: auto-detect, translate, answer, translate back
   - NEVER use cloud model for HR manual queries

4. MICROSOFT TEAMS BOT (backend/integrations/teams/)
   - Azure Bot Service registration (tenant admin provides Azure credentials)
   - Bot answers HR manual queries + leave balance queries
   - Auth: Azure AD â†’ FinanceOps user mapping
   - Local model only for all responses

5. SLACK BOT (backend/integrations/slack/)
   - Slack app with OAuth2 install flow
   - Same capabilities as Teams bot
   - Slash commands + natural language

6. EMPLOYEE SELF-SERVICE (apps/web/app/employee/)
   - Separate portal layout (different from finance layout)
   - Pages: My Payslips, My Leave, My Expenses, Company Policies
   - Payslip: Finance team uploads â†’ employees can view/download own only
   - Expense: submit with receipt â†’ manager approves â†’ Finance processes

7. SSO INTEGRATION (backend/auth/sso/)
   - Azure AD (SAML 2.0 + OAuth2)
   - Google Workspace (OAuth2)
   - Okta (SAML 2.0)
   - Map IdP user to FinanceOps role on first login

FRONTEND:
   - HR section in navigation (visible only to HR roles + employees)
   - Employee workspace (clean, simple â€” not finance-heavy)
   - Org chart visualization (D3.js tree layout)
   - HR Manager dashboard (headcount, leave analytics, onboarding status)
```

### Phase 3 â€” Sales Intelligence (Month 12â€“15)

```
CLAUDE CODE PROMPT â€” SALES INTELLIGENCE:

Build Sales Intelligence Layer. Finance + HR modules already built.

1. CRM CONNECTORS (backend/modules/crm_connectors/)
   - Base connector interface
   - Implement: SalesforceConnector, HubSpotConnector, PipedriveConnector,
     ZohoCRMConnector, FreshsalesConnector
   - Daily sync: accounts, deals, pipeline stages
   - Webhook handlers: deal won, deal lost, stage changed
   - Credits: 10 per sync run

2. PIPELINE-FORECAST BRIDGE (backend/modules/sales/pipeline_bridge.py)
   - Probability-weighted pipeline computation
   - Historical close rate per stage per rep
   - Revenue coverage: backlog + run rate + pipeline = coverage vs target
   - Gap analysis: "need $X new business to hit plan"
   - Feeds existing Forecasting module (Layer 3 of 3-layer forecast)

3. CUSTOMER PROFITABILITY (backend/modules/sales/customer_profitability.py)
   - Join CRM accounts with Finance customer revenue and margin data
   - Compute: gross margin %, net margin %, DSO, LTV per customer
   - Customer health score (0-100)
   - Segment: Grow / Reprice / Expand / Exit

4. COMMISSION ENGINE (backend/modules/sales/commission.py)
   - Commission rules configuration (per rep, per tier, per product)
   - Real-time commission accrual on deal close
   - Finance integration: accrual â†’ P&L, payable â†’ paysheet
   - Rep self-service: see own commission tracker in real-time

5. CONTRACT â†” DEAL SYNC
   - Deal won webhook â†’ auto-create contract record (pre-populated)
   - Contract milestone hit â†’ update CRM deal stage
   - Invoice issued â†’ update CRM account activity

6. FRONTEND
   - Sales Intelligence section (CRO + Sales rep views)
   - Revenue coverage dashboard (the killer feature â€” visualized)
   - Customer profitability heatmap
   - Commission tracker (individual rep view)
   - Pipeline quality analytics
```

---

## 15. Business Model Impact

### Revenue Impact of HR & Sales Modules

```
HR MODULE â€” PRICING UPLIFT:

When HR module added to subscription:
  Starter + HR:       $49 â†’ $79/month    (+$30, +61%)
  Professional + HR:  $149 â†’ $199/month  (+$50, +34%)
  Business + HR:      $449 â†’ $549/month  (+$100, +22%)
  Enterprise + HR:    Custom + $200-500/month

HR module specific credits:
  HR Manual AI query:          2 credits ($0.20)
  HRMS sync:                   10 credits ($1.00)
  Teams/Slack bot query:       1 credit ($0.10) â€” intentionally cheap
  Onboarding tracker:          0 credits (flat fee in subscription)
  Payslip upload + distribute: 3 credits ($0.30) per payslip batch

Teams/Slack bot is priced cheap intentionally:
  If employees use it 20x/day, that's $2/day = $60/month per company
  But the stickiness created is worth far more than the credit revenue
  Every employee using the bot daily = product becomes infrastructure

SALES MODULE â€” PRICING UPLIFT:

When Sales module added:
  Professional + Sales:  $149 â†’ $249/month  (+$100, +67%)
  Business + Sales:      $449 â†’ $649/month  (+$200, +45%)
  Enterprise + Sales:    Custom + $300-800/month

Sales module credits:
  CRM sync:                10 credits
  Pipeline forecast run:   15 credits
  Customer profitability:  10 credits
  Commission computation:  5 credits

FULL PLATFORM (Finance + HR + Sales):
  Professional:  $299/month  (was $149 finance-only)
  Business:      $749/month  (was $449 finance-only)
  Enterprise:    $1,500-5,000/month (was $800-2,000)

REVISED ARPU PROJECTION:
  Phase 1 (Finance only):   $185/month blended ARPU
  Phase 2 (Finance + HR):   $265/month blended ARPU
  Phase 3 (All three):      $380/month blended ARPU

AT 1,000 TENANTS:
  Phase 1: $185K MRR = $2.2M ARR
  Phase 2: $265K MRR = $3.2M ARR
  Phase 3: $380K MRR = $4.6M ARR

AT 3,000 TENANTS:
  Phase 3: $380K MRR Ã— 3 = $1.14M MRR = $13.7M ARR
  (Series A territory â€” $10M ARR+ is fundable)
```

### The Flywheel Effect
```
More Finance customers
    â†’ More HR module adoption (same tenants, upsell)
        â†’ Every employee on platform (sticky, high retention)
            â†’ Sales module added (complete lifecycle view)
                â†’ Customer profitability data attracts CROs
                    â†’ CROs bring their teams
                        â†’ More tenants, more data, better AI
                            â†’ Platform gets smarter
                                â†’ Even more customers

THE STICKINESS METRICS:
  Finance only:        NRR ~110% (good)
  Finance + HR:        NRR ~120% (great â€” employees depend on it daily)
  Finance + HR + Sales: NRR ~130% (exceptional â€” company cannot function without it)

Once every employee is in the platform,
the switching cost is not just financial â€”
it's operational. You become infrastructure.
```

---

*End of HR, Sales & Enterprise OS Vision v1.0*
*Revisit sequencing at end of Phase 1 (Finance) build*
*Do not start Phase 2 (HR) before 20 paying Finance customers*

---

## 10. HR Module â€” API Contracts (Placeholders)

> STATUS: Placeholders. Full contracts written when HR module build starts (after Finance Phase 0-6 complete).

### Core HR Endpoints

```
BASE: /api/v1/hr/

EMPLOYEE DIRECTORY:
  GET    /employees                    List all employees (paginated, role-filtered)
  GET    /employees/{id}               Get single employee (role-filtered fields)
  GET    /employees/org-chart          Org chart tree structure
  GET    /employees/headcount-summary  Aggregated counts only (Finance Leader view)

LEAVE:
  GET    /leave/balances               Current user's leave balances
  GET    /leave/balances/{employee_id} Specific employee (manager/HR only)
  GET    /leave/team-calendar          Team leave calendar (manager view)
  POST   /leave/requests               Submit leave request
  PATCH  /leave/requests/{id}/approve  Manager approve/reject
  GET    /leave/analytics              Leave analytics (HR Manager only)

PAYSLIPS:
  GET    /payslips                     Current user's payslips
  GET    /payslips/{id}/download       Download specific payslip PDF
  POST   /payslips/upload              HR uploads payslip batch
  GET    /payslips/distribution-status Status of batch distribution

HR MANUAL:
  POST   /manual/upload                Upload new HR manual version
  GET    /manual/versions              List all versions
  POST   /manual/query                 Query HR manual (AI-powered)
  GET    /manual/status                Index status (processing/ready)

ONBOARDING:
  POST   /onboarding/initiate          Start onboarding for new employee
  GET    /onboarding/{id}/checklist    Get onboarding checklist
  PATCH  /onboarding/{id}/task/{task}  Mark task complete
  GET    /onboarding/queue             All active onboarding (HR view)

OFFBOARDING:
  POST   /offboarding/initiate         Start offboarding
  GET    /offboarding/{id}/checklist   Get offboarding checklist
  PATCH  /offboarding/{id}/task/{task} Mark task complete
  POST   /offboarding/{id}/ff-trigger  Trigger Full & Final to Finance

HRMS SYNC:
  POST   /sync/trigger                 Manual sync trigger
  GET    /sync/status                  Last sync status per connector
  GET    /sync/history                 Sync history log

TEAMS / SLACK BOT:
  POST   /bot/teams/webhook            Teams bot webhook receiver
  POST   /bot/slack/events             Slack events API endpoint
  POST   /bot/query                    Internal: process bot query

REQUEST/RESPONSE SHAPES: [TO BE DEFINED IN FULL API CONTRACT DOC]
AUTH: All endpoints require valid JWT + HR module access
DATA RESIDENCY: All HR endpoints enforce local-only data storage
CREDITS: HR manual query = 2 credits, all others = 0
```

### HR Data Models (Placeholders)

```python
# PLACEHOLDER â€” Full models defined when HR module build starts

class Employee(BaseModel):
    id: UUID
    tenant_id: UUID
    employee_code: str
    # Personal (Level 4 â€” encrypted):
    full_name: str           # encrypted at rest
    email: str
    mobile: Optional[str]   # encrypted
    date_of_birth: Optional[date]  # encrypted
    # Employment:
    department: str
    designation: str
    grade: str
    location: str
    manager_id: Optional[UUID]
    join_date: date
    employment_type: str    # permanent/contract/intern
    status: str             # active/inactive/notice
    # Cost (visible to Finance only):
    cost_centre: str
    # [Full model to be defined]

class LeaveBalance(BaseModel):
    employee_id: UUID
    leave_type: str
    entitled: Decimal
    taken: Decimal
    pending: Decimal
    available: Decimal
    period: str

class HRManualChunk(BaseModel):
    chunk_id: UUID
    tenant_id: UUID
    section: str
    title: str
    text: str
    embedding: List[float]  # pgvector
    manual_version: str
    effective_date: date
    superseded: bool

# [Additional models: Payslip, OnboardingTask, OffboardingTask,
#  HRSync, PerformanceCycle â€” to be defined]
```

---

## 11. Sales Intelligence â€” API Contracts (Placeholders)

> STATUS: Placeholders. Full contracts written when Sales module build starts (after HR module stable).

### Core Sales Endpoints

```
BASE: /api/v1/sales/

CRM SYNC:
  POST   /sync/trigger/{connector}     Manual sync trigger (salesforce/hubspot/etc)
  GET    /sync/status                  Last sync status per CRM
  GET    /sync/history                 Sync history

PIPELINE:
  GET    /pipeline                     Full pipeline view (current + forecasted)
  GET    /pipeline/summary             Summary stats (total, weighted, by stage)
  GET    /pipeline/by-owner            Pipeline grouped by sales rep
  GET    /pipeline/forecast-bridge     Pipeline â†’ financial forecast bridge
  GET    /pipeline/coverage            Revenue coverage vs annual target

DEALS:
  GET    /deals                        All deals (paginated, filterable)
  GET    /deals/{id}                   Single deal detail
  GET    /deals/{id}/profitability     Customer profitability for this deal
  PATCH  /deals/{id}/contract-status   Update linked contract status

CUSTOMERS:
  GET    /customers                    Customer list with health scores
  GET    /customers/{id}               Single customer profile
  GET    /customers/{id}/profitability Full profitability breakdown
  GET    /customers/{id}/history       Revenue + margin history

COMMISSION:
  GET    /commission/rules             Commission rules configuration
  POST   /commission/rules             Create/update commission rules
  GET    /commission/tracker           Current user's commission tracker
  GET    /commission/tracker/{rep_id}  Specific rep (manager view)
  GET    /commission/accruals          All pending commission accruals (Finance)

ANALYTICS:
  GET    /analytics/win-rate           Win rate by stage, by rep, by period
  GET    /analytics/forecast-accuracy  CRM forecast vs actual revenue
  GET    /analytics/pipeline-quality   Pipeline health score
  GET    /analytics/revenue-coverage   Coverage dashboard

REQUEST/RESPONSE SHAPES: [TO BE DEFINED IN FULL API CONTRACT DOC]
AUTH: All endpoints require valid JWT + Sales module access
CREDITS: pipeline forecast = 15, customer profitability = 10, sync = 10
```

### Sales Data Models (Placeholders)

```python
# PLACEHOLDER â€” Full models defined when Sales module build starts

class CRMDeal(BaseModel):
    id: UUID
    tenant_id: UUID
    crm_deal_id: str        # ID in source CRM
    crm_source: str         # salesforce/hubspot/pipedrive/etc
    name: str
    account_name: str
    account_id: str
    amount: Decimal
    currency: str
    stage: str
    probability: int        # 0-100
    close_date: date
    owner_name: str
    owner_id: str
    contract_id: Optional[UUID]  # linked FinanceOps contract
    synced_at: datetime

class CustomerProfitability(BaseModel):
    customer_id: str
    customer_name: str
    tenant_id: UUID
    period: str
    crm_revenue: Decimal
    finance_revenue: Decimal    # from RevRec module
    direct_cost: Decimal        # from paysheets
    overhead_allocation: Decimal
    gross_margin: Decimal
    gross_margin_pct: Decimal
    net_margin: Decimal
    net_margin_pct: Decimal
    dso_days: int
    health_score: int           # 0-100
    recommendation: str         # grow/reprice/expand/exit

class CommissionRule(BaseModel):
    rule_id: UUID
    tenant_id: UUID
    rep_id: Optional[UUID]      # None = applies to all reps
    rule_type: str              # percentage/tiered/margin_based
    tiers: List[CommissionTier]
    clawback_months: int        # months before commission confirmed
    effective_from: date

# [Additional models: PipelineForecast, RevenueCoverage,
#  CRMAccount, CommissionAccrual â€” to be defined]
```

### CRM Connector Interface (Placeholder)

```python
# PLACEHOLDER â€” Implement when Sales module starts

class CRMConnector(ABC):
    """Base interface all CRM connectors implement."""

    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        """Verify credentials and store tokens."""
        pass

    @abstractmethod
    async def pull_deals(self, since: datetime) -> List[CRMDeal]:
        """Pull deals modified since timestamp."""
        pass

    @abstractmethod
    async def pull_accounts(self, since: datetime) -> List[CRMAccount]:
        """Pull accounts/companies."""
        pass

    @abstractmethod
    async def update_deal(self, deal_id: str, updates: dict) -> bool:
        """Push updates back to CRM (stage, custom fields)."""
        pass

    @abstractmethod
    async def handle_webhook(self, payload: dict) -> WebhookEvent:
        """Handle incoming webhook from CRM."""
        pass

# Implementations (all placeholder):
class SalesforceConnector(CRMConnector): pass   # Phase 3
class HubSpotConnector(CRMConnector): pass      # Phase 3
class PipedriveConnector(CRMConnector): pass    # Phase 3
class ZohoCRMConnector(CRMConnector): pass      # Phase 3
class FreshsalesConnector(CRMConnector): pass   # Phase 3
```

---

## 12. HR Data Retention Policy

```
BEYOND RIGHT TO ERASURE â€” STANDARD RETENTION:

EMPLOYEE DATA RETENTION (after employment ends):
  Personal data (name, contact, address):   2 years after last day
  Salary and payslips:                      7 years (tax law requirement)
  Performance records:                      2 years after last day
  Disciplinary records:                     1 year after last day
  Medical/sensitive data:                   1 year after last day
  Attendance records:                       2 years
  Contract and offer letter:                7 years
  Background check results:                 6 months after employment ends
  Exit interview:                           2 years

AFTER RETENTION PERIOD:
  Automated anonymisation (not deletion â€” some records must be retained):
  â”œâ”€â”€ Name â†’ "Former Employee [hashed_id]"
  â”œâ”€â”€ Contact details â†’ deleted
  â”œâ”€â”€ Salary amounts â†’ retained (P&L accuracy)
  â”œâ”€â”€ Attendance counts â†’ retained (compliance)
  â””â”€â”€ Performance ratings â†’ deleted

IMPLEMENTATION:
  Celery Beat job (monthly â€” 1st of month):
    def hr_data_retention_cleanup():
        Find employees where employment_end_date + retention_period < today
        For each field: check retention period
        Apply anonymisation or deletion per policy above
        Log: what was anonymised/deleted, for which employee (hashed ID)
        
  Tenant-configurable: can extend retention periods (not shorten below legal minimum)

INDIA-SPECIFIC:
  PF records: 5 years after last contribution (EPFO requirement)
  ESI records: 5 years (ESIC requirement)
  TDS/Form 16: 7 years (Income Tax requirement)
  These override shorter retention periods above.
```

---

## 13. HR Analytics â€” Data Boundary Rules

```
HR DATA IN PLATFORM ANALYTICS â€” STRICT RULES:

WHAT HR DATA APPEARS IN ANALYTICS:
  âœ… Aggregated headcount numbers (no individual data)
  âœ… Attrition rate (% only, no names)
  âœ… Department-level cost totals (no individual salaries)
  âœ… Leave utilisation % by department (no individual records)
  âœ… Org chart depth and span of control metrics
  âœ… Onboarding completion rate (% only)

WHAT NEVER APPEARS IN ANALYTICS:
  âŒ Individual employee names anywhere in analytics
  âŒ Individual salaries (only department/role-level aggregates)
  âŒ Individual performance ratings
  âŒ Individual leave balances
  âŒ Anything identifying a specific person

MINIMUM AGGREGATION RULE:
  No HR metric shown for a group smaller than 5 people.
  If a department has 3 people: metrics suppressed with
  "Insufficient sample size (< 5)" message.
  Prevents reverse-engineering individual data from small groups.

ANALYTICS DB RULE:
  HR analytics queries must JOIN through aggregated views only.
  Direct access to hr_employees, hr_payslips, hr_leave tables
  is blocked at RLS level for analytics roles.
  
  Only these views are accessible for analytics:
  â”œâ”€â”€ hr_headcount_by_department    (counts only)
  â”œâ”€â”€ hr_cost_by_department         (aggregated cost only)
  â”œâ”€â”€ hr_attrition_by_department    (% only)
  â””â”€â”€ hr_leave_utilisation_summary  (% only, min 5 employees)
```

---

## 14. HR Module â€” Cross-Module Dependency Map

```
HR MODULE DEPENDENCIES:

HARD REQUIRES (cannot function without):
  â”œâ”€â”€ Core Platform: Authentication, RBAC, Audit Trail, Multi-tenancy
  â”œâ”€â”€ File Upload Service: payslip distribution, document storage
  â””â”€â”€ Encryption Service: field-level encryption for sensitive fields

REQUIRES FOR FULL FUNCTIONALITY:
  â”œâ”€â”€ Finance Module â†’ Headcount Analytics:
  â”‚     HR provides employee count/cost â†’ Finance shows in P&L
  â”œâ”€â”€ Finance Module â†’ Paysheet Integration:
  â”‚     Finance paysheet = source for HR payslip distribution
  â””â”€â”€ Finance Module â†’ Expense Management:
        Expense submissions (HR layer) â†’ GL coding (Finance layer)

OPTIONAL INTEGRATIONS:
  â”œâ”€â”€ Sales Module â†’ Commission Engine:
  â”‚     HR employee data + Sales commission rules = commission paysheet
  â””â”€â”€ Payroll Connectors (HRMS):
        Darwinbox/Keka/greytHR â†’ HR module (one-way sync, HRMS is master)

WHAT HR MODULE PROVIDES TO OTHER MODULES:
  â”œâ”€â”€ â†’ Finance: headcount count + cost by department (aggregated view)
  â”œâ”€â”€ â†’ Finance: payroll amounts for P&L posting
  â”œâ”€â”€ â†’ Sales: employee profiles for commission calculation
  â””â”€â”€ â†’ Enterprise OS: org chart, team structure, role information

WHAT HR MODULE DOES NOT DO:
  âŒ Process payroll (HRMS is the system of record)
  âŒ Approve leave (HR policy tools do this)
  âŒ Manage performance cycles (HR tools do this)
  âŒ Store medical/insurance data (HR HRMS does this)
  
  FinanceOps HR module is: finance bridge + document distribution
  + AI assistant + compliance tracking + onboarding/offboarding workflow.
  It integrates WITH HRMS â€” it does not REPLACE HRMS.
```

---

## 15. HR Manual Version Rollback

```
SCENARIO: New HR manual uploaded with errors.
  Employees queried the AI, got wrong policy information.
  Need to immediately revert to previous version.

ROLLBACK PROCEDURE:

Step 1: Deactivate current version (immediate):
  UPDATE hr_manual_versions
  SET is_active = FALSE, superseded_at = NOW()
  WHERE tenant_id = X AND is_active = TRUE;

Step 2: Reactivate previous version:
  UPDATE hr_manual_versions
  SET is_active = TRUE, superseded_at = NULL
  WHERE tenant_id = X AND version = (current_version - 1);

Step 3: Flush vector index for this tenant:
  DELETE FROM hr_manual_chunks WHERE tenant_id = X;
  Re-embed previous version chunks (background job, ~5 minutes)

Step 4: Clear bot cache:
  FLUSH Redis keys: hr_manual:{tenant_id}:*

Step 5: Notify HR team:
  "HR Manual rolled back to version [N-1]. 
   Reason: [error description]. 
   AI assistant is using previous version."

UI: Finance Leader sees "Rollback to previous version" button
    on any manual version that has a predecessor.
    One click â†’ triggers above procedure.
    Rollback completes within 10 minutes.

VERSION HISTORY:
  All versions retained permanently (never deleted).
  Even rolled-back versions visible in version history with status.
  Audit trail: who uploaded, who activated, who rolled back.
```


