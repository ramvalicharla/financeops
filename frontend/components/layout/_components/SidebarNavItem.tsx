"use client"

import Link from "next/link"
import type { NavigationLeafItem } from "@/lib/config/navigation"
import { useUIStore } from "@/lib/store/ui"
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

  if (collapsed) {
    return (
      <Link
        href={item.href}
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
      key={item.href}
      href={item.href}
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
