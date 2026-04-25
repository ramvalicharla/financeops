/**
 * nav-config.ts — Single source of truth for the three Phase-1 nav groups.
 *
 * Type design (Adjustment 1):
 *   NavigationLeafItem = { label: string; href: string; icon: LucideIcon }
 *   NavItem extends NavigationLeafItem, adding `id` and optional `badge`.
 *   Because NavItem is a structural superset of NavigationLeafItem it is
 *   assignable to NavigationLeafItem without casting, so items flow into
 *   SidebarNavItem (which expects NavigationLeafItem) and filterNavigationItems
 *   (which expects readonly NavigationItem[]) without type errors.
 *
 * Route placeholders (6 of 12 routes missing — FU-012 filed in 1.2):
 *   /settings/connectors    → MISSING (placeholder /dashboard)
 *   /settings/modules       → MISSING; /modules exists — rename candidate
 *   /settings/billing       → MISSING; /billing exists — rename candidate
 *   /governance/audit       → MISSING; /audit exists — rename candidate
 *   /settings/team          → MISSING; /settings/users + /settings/groups exist — consolidation candidate
 *   /governance/compliance  → MISSING (placeholder /dashboard)
 */

import type { LucideIcon } from "lucide-react"
import {
  Building2,
  CalendarCheck,
  CheckSquare,
  CreditCard,
  LayoutDashboard,
  LayoutGrid,
  Plug,
  ScrollText,
  Settings,
  ShieldCheck,
  Target,
  Users,
} from "lucide-react"
import type { NavigationLeafItem } from "@/lib/config/navigation"

export interface NavItem extends NavigationLeafItem {
  id: string
  badge?: { count: number; tone: "info" | "warning" | "danger" } | null
}

export type NavGroupId = "workspace" | "org" | "governance"

export interface NavGroup {
  id: NavGroupId
  label: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: "workspace",
    label: "Workspace",
    items: [
      { id: "overview", label: "Overview", href: "/dashboard", icon: LayoutDashboard },
      // TODO Phase 2: replace placeholder href with real /today route once endpoint ships
      { id: "today", label: "Today's focus", href: "/dashboard", icon: Target },
      // TODO Phase 2: replace placeholder href with real period-close route
      { id: "period-close", label: "Period close", href: "/dashboard", icon: CalendarCheck },
      // TODO Phase 2: wire badge.count to /api/v1/approvals?status=pending
      { id: "approvals", label: "Approvals", href: "/dashboard", icon: CheckSquare, badge: null },
    ],
  },
  {
    id: "org",
    label: "Org",
    items: [
      { id: "entities", label: "Entities", href: "/settings/entities", icon: Building2 },
      { id: "org-settings", label: "Org settings", href: "/settings", icon: Settings },
      // TODO Phase 2: route does not exist yet (/settings/connectors)
      { id: "connectors", label: "Connectors", href: "/dashboard", icon: Plug },
      // TODO Phase 2: route does not exist yet (/settings/modules — /modules exists, rename candidate)
      { id: "modules", label: "Modules", href: "/dashboard", icon: LayoutGrid },
      // TODO Phase 2: route does not exist yet (/settings/billing — /billing exists, rename candidate)
      { id: "billing", label: "Billing · Credits", href: "/dashboard", icon: CreditCard },
    ],
  },
  {
    id: "governance",
    label: "Governance",
    items: [
      // TODO Phase 2: route does not exist yet (/governance/audit — /audit exists, rename candidate)
      { id: "audit-trail", label: "Audit trail", href: "/dashboard", icon: ScrollText },
      // TODO Phase 2: route does not exist yet (/settings/team — /settings/users + /settings/groups exist, consolidation candidate)
      { id: "team-rbac", label: "Team · RBAC", href: "/dashboard", icon: Users },
      // TODO Phase 2: route does not exist yet (/governance/compliance)
      { id: "compliance", label: "Compliance", href: "/dashboard", icon: ShieldCheck },
    ],
  },
]
