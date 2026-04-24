"use client"

import { useEffect, useRef, useState } from "react"
import { useSession } from "next-auth/react"
import { Check, ChevronsUpDown, Loader2, Building2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { useTenantStore } from "@/lib/store/tenant"
import { adminListTenants, switchToTenant } from "@/lib/api/admin"
import type { AdminTenantListItem } from "@/lib/types/admin"
import type { UserRole } from "@/lib/auth"

const PLATFORM_OWNER_ROLES: UserRole[] = ["platform_owner", "super_admin"]

export function OrgSwitcher() {
  const { data: session } = useSession()
  const userRole = (session?.user as { role?: UserRole } | undefined)?.role

  // Only render for platform_owner / super_admin
  if (!userRole || !PLATFORM_OWNER_ROLES.includes(userRole)) {
    return null
  }

  return <OrgSwitcherInner />
}

function OrgSwitcherInner() {
  const [open, setOpen] = useState(false)
  const [tenants, setTenants] = useState<AdminTenantListItem[]>([])
  const [loadingTenants, setLoadingTenants] = useState(false)
  const [switchingId, setSwitchingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fetchedRef = useRef(false)

  const isSwitched = useTenantStore((s) => s.is_switched)
  const switchedName = useTenantStore((s) => s.switched_tenant_name)
  const realTenantId = useTenantStore((s) => s.tenant_id)
  const switchedTenantId = useTenantStore((s) => s.switched_tenant_id)
  const enterSwitchMode = useTenantStore((s) => s.enterSwitchMode)

  // Lazy-fetch tenants once on first open
  useEffect(() => {
    if (!open || fetchedRef.current) return
    fetchedRef.current = true
    setLoadingTenants(true)
    adminListTenants({ limit: 200 })
      .then((res) => setTenants(res.items))
      .catch(() => setError("Failed to load tenants"))
      .finally(() => setLoadingTenants(false))
  }, [open])

  const activeTenantId = isSwitched ? switchedTenantId : realTenantId

  const handleSelect = async (tenant: AdminTenantListItem) => {
    if (tenant.id === activeTenantId) {
      setOpen(false)
      return
    }
    setSwitchingId(tenant.id)
    setError(null)
    try {
      const result = await switchToTenant(tenant.id)
      enterSwitchMode({
        switch_token: result.switch_token,
        tenant_id: result.tenant_id,
        tenant_name: result.tenant_name,
      })
      setOpen(false)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Switch failed")
    } finally {
      setSwitchingId(null)
    }
  }

  const displayName = isSwitched ? (switchedName ?? "Switched Org") : "My Org"

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 px-2.5 font-normal max-w-[180px]"
          aria-label="Switch organisation"
          aria-expanded={open}
        >
          <Building2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="truncate text-xs">{displayName}</span>
          <ChevronsUpDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>

      <PopoverContent className="w-80 p-0" align="start" sideOffset={6}>
        <Command>
          <CommandInput placeholder="Search tenants…" />
          <CommandList>
            {loadingTenants ? (
              <div className="flex items-center justify-center py-6 text-sm text-muted-foreground gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading…
              </div>
            ) : error ? (
              <div className="py-4 px-3 text-xs text-destructive">{error}</div>
            ) : (
              <>
                <CommandEmpty>No tenants found.</CommandEmpty>
                <CommandGroup heading="Tenants">
                  {tenants.map((t) => {
                    const isActive = t.id === activeTenantId
                    const isSwitching = switchingId === t.id
                    return (
                      <CommandItem
                        key={t.id}
                        value={t.name}
                        onSelect={() => handleSelect(t)}
                        disabled={isSwitching}
                        className="gap-2"
                      >
                        <div className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-sm font-medium">{t.name}</span>
                          <span className="truncate text-[10px] text-muted-foreground">{t.slug}</span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                            t.status === "active"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : t.status === "trialing"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-muted text-muted-foreground"
                          }`}>
                            {t.status}
                          </span>
                          {isSwitching ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                          ) : isActive ? (
                            <Check className="h-3.5 w-3.5 text-primary" />
                          ) : null}
                        </div>
                      </CommandItem>
                    )
                  })}
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
