"use client"

import Link from "next/link"
import type { NavigationLeafItem } from "@/lib/config/navigation"
import { useUIStore } from "@/lib/store/ui"
import { useTenantStore } from "@/lib/store/tenant"
import { cn } from "@/lib/utils"

interface SidebarNavItemProps {
  item: NavigationLeafItem
  active: boolean
  compact?: boolean
  onClick: () => void
  withIcon?: boolean
}

export function SidebarNavItem({
  item,
  active,
  compact = false,
  onClick,
  withIcon = true,
}: SidebarNavItemProps) {
  const Icon = item.icon
  const collapsed = useUIStore((state) => state.sidebarCollapsed)
  const orgSlug = useTenantStore((state) => state.tenant_slug) ?? ""
  const entitySlug = useTenantStore((state) => state.active_entity_id) ?? ""

  // Transform static hrefs for module pathways that have been migrated to the context-locked layout
  let targetHref = item.href
  if (targetHref.startsWith("/accounting") || targetHref.startsWith("/settings/integrations/erp")) {
    if (orgSlug && entitySlug) {
      targetHref = `/${orgSlug}/${entitySlug}${targetHref}`
    }
  }

  if (collapsed) {
    return (
      <Link
        href={targetHref}
        onClick={onClick}
        title={item.label}
        aria-label={item.label}
        className={cn(
          "flex h-9 w-full items-center justify-center rounded-md transition",
          active
            ? "bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
      </Link>
    )
  }

  return (
    <Link
      key={targetHref}
      href={targetHref}
      onClick={onClick}
      title={item.label}
      className={cn(
        withIcon
          ? "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition"
          : compact
            ? "block rounded-md border-l-2 px-3 py-2 text-xs transition"
            : "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
        active
          ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
          : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {withIcon ? <Icon className="h-4 w-4" /> : null}
      {item.label}
    </Link>
  )
}
