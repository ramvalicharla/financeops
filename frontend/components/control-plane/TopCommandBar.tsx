"use client"

import Link from "next/link"
import { Search } from "lucide-react"
import { signOut } from "next-auth/react"
import { usePathname } from "next/navigation"
import { useState } from "react"
import type { UserRole } from "@/lib/auth"
import { EntityLocationSelector } from "@/components/layout/EntityLocationSelector"
import { NotificationBell } from "@/components/notifications/NotificationBell"
import { useSearch } from "@/components/search/SearchProvider"
import { Button } from "@/components/ui/button"
import { TopbarBase } from "@/components/shell/primitives/TopbarBase"

const TITLES: Record<string, string> = {
  "/control-plane/overview": "Overview",
  "/control-plane/intents": "Intents",
  "/control-plane/jobs": "Jobs",
  "/control-plane/timeline": "Timeline",
  "/control-plane/lineage": "Lineage",
  "/control-plane/snapshots": "Snapshots",
  "/control-plane/airlock": "Airlock",
  "/control-plane/entities": "Entities",
  "/control-plane/modules": "Modules",
  "/control-plane/incidents": "Incidents",
  "/control-plane/admin": "Admin",
}

const MOBILE_NAV_ITEMS = [
  { href: "/control-plane/overview", label: "Overview" },
  { href: "/control-plane/intents", label: "Intents" },
  { href: "/control-plane/jobs", label: "Jobs" },
  { href: "/control-plane/timeline", label: "Timeline" },
  { href: "/control-plane/lineage", label: "Lineage" },
  { href: "/control-plane/snapshots", label: "Snapshots" },
  { href: "/control-plane/airlock", label: "Airlock" },
] as const

interface TopCommandBarProps {
  userName: string
  userEmail: string
  userRole: UserRole
}

export function TopCommandBar({ userName, userEmail, userRole }: TopCommandBarProps) {
  const pathname = usePathname() ?? ""
  const { openPalette } = useSearch()
  const [menuOpen, setMenuOpen] = useState(false)
  const title =
    Object.entries(TITLES).find(([href]) => pathname === href || pathname.startsWith(`${href}/`))?.[1] ??
    "Control Plane"

  return (
    <TopbarBase>
      <div className="flex min-h-16 flex-wrap items-center justify-between gap-4 px-4 py-3 md:px-6">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Control Plane
          </p>
          <h1 className="text-lg font-semibold text-foreground">{title}</h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <EntityLocationSelector />
          <Button type="button" variant="outline" onClick={openPalette}>
            <Search className="mr-2 h-4 w-4" />
            Search
          </Button>
          <Button
            type="button"
            disabled
            title="Create intent is unavailable in the current backend contract."
          >
            Create intent
          </Button>
          <NotificationBell onTrigger={() => setMenuOpen(false)} />
          <div className="relative">
            <button
              type="button"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {userName.slice(0, 1).toUpperCase()}
            </button>
            {menuOpen ? (
              <div className="absolute right-0 z-50 mt-2 w-64 rounded-md border border-border bg-card p-3 shadow-lg">
                <p className="text-sm font-medium text-foreground">{userName}</p>
                <p className="text-xs text-muted-foreground">{userEmail}</p>
                <p className="mt-1 text-xs uppercase tracking-wide text-muted-foreground">
                  Role: {String(userRole).replace(/_/g, " ")}
                </p>
                <Button
                  className="mt-3 w-full"
                  size="sm"
                  variant="outline"
                  onClick={() => signOut({ callbackUrl: "/login" })}
                  type="button"
                >
                  Sign out
                </Button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <div className="border-t border-border px-4 py-3 md:hidden">
        <nav aria-label="Control plane mobile navigation" className="flex gap-2 overflow-x-auto">
          {MOBILE_NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                  isActive
                    ? "border-foreground bg-foreground text-background"
                    : "border-border bg-card text-muted-foreground"
                }`}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>
      </div>
    </TopbarBase>
  )
}
