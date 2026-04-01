"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  ShieldCheck,
  HardDrive,
  LayoutGrid,
  Building2,
  Users,
  KeyRound,
  Flag,
  ServerCog,
  Store,
  Palette,
  Handshake,
  Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { href: "/admin", label: "Overview", icon: LayoutGrid },
  { href: "/admin/compliance/soc2", label: "SOC2", icon: ShieldCheck },
  { href: "/admin/compliance/iso27001", label: "ISO 27001", icon: ShieldCheck },
  { href: "/admin/services", label: "Services", icon: ServerCog },
  { href: "/admin/marketplace", label: "Marketplace", icon: Store },
  { href: "/admin/white-label", label: "White Label", icon: Palette },
  { href: "/admin/partners", label: "Partners", icon: Handshake },
  { href: "/admin/ai-quality", label: "AI Quality", icon: Sparkles },
  { href: "/admin/ai-providers", label: "AI Providers", icon: Sparkles },
  { href: "/admin/backup", label: "Backup & DR", icon: HardDrive },
  { href: "/admin/tenants", label: "Tenants", icon: Building2 },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/rbac", label: "RBAC", icon: KeyRound },
  { href: "/admin/flags", label: "Flags", icon: Flag },
  { href: "/admin/modules", label: "Modules", icon: ServerCog },
] as const

export function AdminSidebar() {
  const pathname = usePathname() ?? ""

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-border bg-card md:block">
      <div className="border-b border-border px-4 py-4">
        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">FinanceOps</p>
        <span className="mt-2 inline-flex rounded-full border border-[hsl(var(--brand-danger)/0.5)] bg-[hsl(var(--brand-danger)/0.15)] px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-[hsl(var(--brand-danger))]">
          ADMIN
        </span>
      </div>
      <nav className="space-y-1 p-3">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                isActive
                  ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                  : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}

