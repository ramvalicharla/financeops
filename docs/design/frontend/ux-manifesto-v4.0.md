# FinanceOps Frontend: Worldclass UX & UI Manifesto (v4.0)

This document outlines the architectural standard for the FinanceOps frontend, shifting the UI out of generic templates and into a premium, world-class standard on par with Stripe, Linear, and Zoho Books.

## Core Philosophical Shifts
1. **Never Compromise the Tech Stack**: We strictly enforce `Tailwind CSS`, `Next.js App Router`, and `shadcn/ui`. We will never implement highly-coupled third-party frameworks like Bootstrap or heavily bloated admin templates (e.g., Dasher UI) directly. We extract **Design Patterns** (glassmorphism, specific spacing, colors), not the code.
2. **State Over Navigation**: Context shouldn't be broken unless absolutely necessary. We prioritize `Slide-Over Drawers` (`shadcn <Sheet>`) and inline `HoverCards` over hard redirects to completely new pages.
3. **Data Density Toggle**: Financial applications demand high density. We will enforce visual scales that allow toggles between 'Comfortable' and 'Compact' views.

---

## The 5 Pillars of World-Class Financial UX

### 1. The Global Command Palette (`Cmd+K`)
* **Standard**: Elite modern tools (Linear, Vercel) provide global omnisearch.
* **Implementation Strategy**: Integrate `cmdk` globally. Binding custom actions ("Switch to Acme Corp", "Go to Tax Module") directly into the palette so Platform Admins can circumvent the Sidebar entirely for high-speed workflows.

### 2. In-Context Drawers (The Zoho Standard)
* **Standard**: Users hate losing their ledger view. Clicking a row should open context, not a new page.
* **Implementation Strategy**: Aggressively replace `/edit/[id]` pages with Sliding Drawers (`<Sheet>`). For example, modifying an ERP connector or auditing an Intent Payload will slide out a pristine right-panel panel over the active table.

### 3. Excel-Grade Data Grids
* **Standard**: Accountants expect software behavior to mimic Excel.
* **Implementation Strategy**: Upgrade `@tanstack/react-table` with:
  - Sticky Headers and Sticky Row 1.
  - Multi-sort matrices.
  - Floating "Bulk Action" bars for bulk approvals.

### 4. Skeleton Loaders (The QuickBooks Standard)
* **Standard**: Avoid layout jumpiness and static "Loading..." strings.
* **Implementation Strategy**: Deploy structured `Shadcn <Skeleton>` primitives inside React Suspense boundaries or `isLoading` flags for all Control Plane views, making the application feel instantaneous and premium.

### 5. Premium KPI Glassmorphism widgets
* **Standard**: Move beyond basic solid color cards (the "Bootstrap Dasher" look).
* **Implementation Strategy**: Use Tailwind's backdrop-filters, subtle `border-white/10` edges, and gradients to make statistical blocks (Activity Loads, Invoice counts) look structurally elevated on the screen.
