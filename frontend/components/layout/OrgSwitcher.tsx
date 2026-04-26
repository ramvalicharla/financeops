"use client"

import { useEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
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
import { useWorkspaceStore } from "@/lib/store/workspace"
import { listUserSwitchableOrgs, switchUserOrg } from "@/lib/api/orgs"
import type { UserOrgItem } from "@/lib/api/orgs"

export function OrgSwitcher() {
  const [open, setOpen] = useState(false)
  const [orgs, setOrgs] = useState<UserOrgItem[]>([])
  const [loadingOrgs, setLoadingOrgs] = useState(false)
  const [switchingId, setSwitchingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fetchedRef = useRef(false)

  const isSwitched = useTenantStore((s) => s.is_switched)
  const switchedName = useTenantStore((s) => s.switched_tenant_name)
  const realTenantId = useTenantStore((s) => s.tenant_id)
  const switchedTenantId = useTenantStore((s) => s.switched_tenant_id)
  const enterSwitchMode = useTenantStore((s) => s.enterSwitchMode)
  const workspaceStore = useWorkspaceStore()
  const queryClient = useQueryClient()

  // Lazy-fetch orgs once on first open
  useEffect(() => {
    if (!open || fetchedRef.current) return
    fetchedRef.current = true
    setLoadingOrgs(true)
    listUserSwitchableOrgs()
      .then((res) => setOrgs(res.items))
      .catch(() => setError("Failed to load organisations"))
      .finally(() => setLoadingOrgs(false))
  }, [open])

  const activeTenantId = isSwitched ? switchedTenantId : realTenantId

  const handleSelect = async (item: UserOrgItem) => {
    if (item.org_id === activeTenantId) {
      setOpen(false)
      return
    }
    setSwitchingId(item.org_id)
    setError(null)
    try {
      const result = await switchUserOrg(item.org_id)
      enterSwitchMode({
        switch_token: result.switch_token,
        tenant_id: result.target_org.id,
        tenant_name: result.target_org.name,
        switch_mode: "user",
      })
      workspaceStore.switchOrg(result.target_org.id)
      queryClient.clear()
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
          <CommandInput placeholder="Search organisations…" />
          <CommandList>
            {loadingOrgs ? (
              <div className="flex items-center justify-center py-6 text-sm text-muted-foreground gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading…
              </div>
            ) : error ? (
              <div className="py-4 px-3 text-xs text-destructive">{error}</div>
            ) : (
              <>
                <CommandEmpty>No organisations found.</CommandEmpty>
                <CommandGroup heading="Organisations">
                  {orgs.map((item) => {
                    const isActive = item.org_id === activeTenantId
                    const isSwitching = switchingId === item.org_id
                    return (
                      <CommandItem
                        key={item.org_id}
                        value={item.org_name}
                        onSelect={() => handleSelect(item)}
                        disabled={isSwitching}
                        className="gap-2"
                      >
                        <div className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-sm font-medium">{item.org_name}</span>
                          <span className="truncate text-[10px] text-muted-foreground">{item.org_slug}</span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                            item.org_status === "active"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : item.org_status === "trialing"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-muted text-muted-foreground"
                          }`}>
                            {item.org_status}
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
