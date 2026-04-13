"use client"

import {
  type NavigationGroupItem,
  type NavigationLeafItem,
} from "@/lib/config/navigation"
import { useUIStore } from "@/lib/store/ui"
import { cn } from "@/lib/utils"
import { ChevronDown } from "lucide-react"
import { SidebarNavItem } from "./SidebarNavItem"

interface SidebarNavGroupProps {
  closeSidebar: () => void
  items: readonly NavigationLeafItem[]
  label?: string
  pathname: string
  type?: "boxed" | "nested" | "plain"
}

interface SidebarDisclosureGroupProps {
  closeSidebar: () => void
  item: NavigationGroupItem
  open: boolean
  pathname: string
  onToggle: () => void
}

export function SidebarDisclosureGroup({
  closeSidebar,
  item,
  open,
  pathname,
  onToggle,
}: SidebarDisclosureGroupProps) {
  const Icon = item.icon
  const groupId = `nav-group-${item.label.toLowerCase().replace(/\s+/g, "-")}`
  const collapsed = useUIStore((state) => state.sidebarCollapsed)

  if (collapsed) {
    // Show all children as icon-only items — group concept collapses away.
    return (
      <div className="space-y-1">
        {item.children.map((child) => (
          <SidebarNavItem
            key={child.href}
            item={child}
            active={pathname === child.href}
            compact={false}
            onClick={closeSidebar}
            withIcon={true}
          />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <button
        type="button"
        aria-controls={groupId}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-md px-3 py-2 text-sm text-foreground hover:bg-accent"
        onClick={onToggle}
      >
        <span className="flex items-center gap-2">
          <Icon className="h-4 w-4" />
          {item.label}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform",
            open ? "rotate-180" : "rotate-0",
          )}
        />
      </button>
      {open ? (
        <div id={groupId} className="space-y-1 pl-6">
          {item.children.map((child) => (
            <SidebarNavItem
              key={child.href}
              item={child}
              active={pathname === child.href}
              compact
              withIcon={false}
              onClick={closeSidebar}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function SidebarNavGroup({
  closeSidebar,
  items,
  label,
  pathname,
  type = "boxed",
}: SidebarNavGroupProps) {
  const collapsed = useUIStore((state) => state.sidebarCollapsed)

  if (collapsed) {
    // Strip all wrappers and labels — just a flat list of icon-only items.
    return (
      <div className="space-y-1">
        {items.map((item) => (
          <SidebarNavItem
            key={item.href}
            item={item}
            active={
              pathname === item.href || pathname.startsWith(`${item.href}/`)
            }
            compact={false}
            onClick={closeSidebar}
            withIcon={true}
          />
        ))}
      </div>
    )
  }

  const wrapperClass =
    type === "boxed"
      ? "mt-3 rounded-md border border-border/60 p-2"
      : type === "nested"
        ? "space-y-1 pl-2"
        : "space-y-1"

  return (
    <div className={wrapperClass}>
      {label ? (
        <p className="px-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </p>
      ) : null}
      {items.map((item, index) => (
        <SidebarNavItem
          key={item.href}
          item={item}
          active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
          compact={type !== "plain" && index > 0}
          onClick={closeSidebar}
          withIcon={type === "plain" || index === 0}
        />
      ))}
    </div>
  )
}
