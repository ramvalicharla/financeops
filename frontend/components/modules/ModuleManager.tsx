"use client"

import { useState } from "react"
import { GripVertical } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { Dialog } from "@/components/ui/Dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { queryKeys } from "@/lib/query/keys"
import { getModuleIcon, MODULE_ICON_MAP } from "@/components/layout/tabs/module-icons"
import { useModuleManagerStore } from "@/lib/store/moduleManager"
import { useModuleOrderStore } from "@/lib/store/moduleOrder"
import { useWorkspaceStore } from "@/lib/store/workspace"

// Full catalog of workspace keys — matches backend _WORKSPACE_DEFINITIONS (7 entries).
// "dashboard" is the canonical key per OQ-2 (not "overview").
const WORKSPACE_CATALOG: Array<{ workspace_key: string; workspace_name: string }> = [
  { workspace_key: "dashboard", workspace_name: "Dashboard" },
  { workspace_key: "erp", workspace_name: "ERP" },
  { workspace_key: "accounting", workspace_name: "Accounting" },
  { workspace_key: "reconciliation", workspace_name: "Reconciliation" },
  { workspace_key: "close", workspace_name: "Close" },
  { workspace_key: "reports", workspace_name: "Reports" },
  { workspace_key: "settings", workspace_name: "Settings" },
]

function AvailableTab({ enabledKeys }: { enabledKeys: Set<string> }) {
  const [saving, setSaving] = useState<string | null>(null)

  const availableTabs = WORKSPACE_CATALOG.filter(
    (w) => !enabledKeys.has(w.workspace_key),
  )

  const handleToggle = async (workspaceKey: string) => {
    setSaving(workspaceKey)
    // Stub: POST /api/v1/orgs/{orgId}/modules does not exist yet (filed as backend ticket).
    await new Promise((r) => setTimeout(r, 500))
    setSaving(null)
    toast.info("Module enable/disable will activate when backend support lands.")
  }

  if (availableTabs.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        All available modules are already active.
      </div>
    )
  }

  return (
    <ul className="space-y-1" aria-label="Available modules">
      {availableTabs.map((w) => {
        const Icon = getModuleIcon(w.workspace_key)
        const isSaving = saving === w.workspace_key
        return (
          <li
            key={w.workspace_key}
            className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm hover:bg-accent"
          >
            <Icon size={16} className="shrink-0 text-muted-foreground" aria-hidden="true" />
            <span className="flex-1 text-foreground">{w.workspace_name}</span>
            <button
              type="button"
              disabled={isSaving}
              onClick={() => handleToggle(w.workspace_key)}
              aria-label={isSaving ? "Saving…" : `Enable ${w.workspace_name}`}
              className="rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSaving ? "Saving…" : "Enable"}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export function ModuleManager() {
  const { isOpen, close } = useModuleManagerStore()
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const { order, setOrder } = useModuleOrderStore()

  // Shares the same cache entry as ModuleTabs — no extra network request.
  const contextQuery = useQuery({
    queryKey: queryKeys.workspace.tabs(activeEntityId),
    queryFn: () => getControlPlaneContext({ entity_id: activeEntityId ?? undefined }),
    staleTime: 60_000,
    enabled: isOpen,
  })

  const workspaceTabs = contextQuery.data?.workspace_tabs ?? []

  // Apply user ordering from store; fall back to backend order when store is empty.
  const orderedTabs = (() => {
    if (order.length === 0) return workspaceTabs
    const tabMap = new Map(workspaceTabs.map((t) => [t.workspace_key, t]))
    const ordered = order.flatMap((key) => {
      const tab = tabMap.get(key)
      return tab ? [tab] : []
    })
    // Append any new tabs the backend added that aren't in the stored order yet.
    const known = new Set(order)
    const novel = workspaceTabs.filter((t) => !known.has(t.workspace_key))
    return [...ordered, ...novel]
  })()

  // Seed the order store from backend tabs on first open (store empty → backend wins).
  if (isOpen && order.length === 0 && workspaceTabs.length > 0) {
    setOrder(workspaceTabs.map((t) => t.workspace_key))
  }

  const enabledKeys = new Set(workspaceTabs.map((t) => t.workspace_key))

  return (
    <Dialog
      open={isOpen}
      onClose={close}
      title="Module Manager"
      description="Configure which modules appear in your workspace tab bar."
      size="md"
      className="max-w-[640px]"
    >
      <Tabs defaultValue="active">
        <TabsList className="w-full">
          <TabsTrigger value="active" className="flex-1">
            Active
          </TabsTrigger>
          <TabsTrigger value="available" className="flex-1">
            Available
          </TabsTrigger>
          <TabsTrigger value="premium" className="flex-1">
            Premium
          </TabsTrigger>
          <TabsTrigger value="custom" className="flex-1">
            Custom
          </TabsTrigger>
        </TabsList>

        <TabsContent value="active" className="mt-4 min-h-[200px]">
          {contextQuery.isPending ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              Loading modules…
            </div>
          ) : orderedTabs.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              No active modules.
            </div>
          ) : (
            <ul className="space-y-1" aria-label="Active modules">
              {orderedTabs.map((tab) => {
                const Icon = getModuleIcon(tab.workspace_key)
                return (
                  <li
                    key={tab.workspace_key}
                    className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm hover:bg-accent"
                  >
                    {/* Drag grip — visual placeholder; SP-3B wires dnd-kit handlers here */}
                    <GripVertical
                      size={14}
                      className="shrink-0 cursor-grab text-muted-foreground/50"
                      aria-hidden="true"
                    />
                    <Icon size={16} className="shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span className="flex-1 text-foreground">{tab.workspace_name}</span>
                  </li>
                )
              })}
            </ul>
          )}
        </TabsContent>

        <TabsContent value="available" className="mt-4 min-h-[200px]">
          {contextQuery.isPending ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              Loading modules…
            </div>
          ) : (
            <AvailableTab enabledKeys={enabledKeys} />
          )}
        </TabsContent>

        <TabsContent value="premium" className="mt-4 min-h-[200px]">
          <div className="flex flex-col items-center justify-center gap-4 py-8 text-center">
            <p className="text-sm text-muted-foreground">
              Premium modules will appear here. Pricing details coming soon.
            </p>
            {/* Example locked cards — communicates future shape; no real data yet */}
            <ul className="w-full space-y-1">
              {(["Consolidation", "Tax"] as const).map((name) => (
                <li
                  key={name}
                  className="flex items-center gap-3 rounded-md border border-border/50 px-3 py-2.5 text-sm opacity-50"
                  aria-hidden="true"
                >
                  <span className="text-base">🔒</span>
                  <span className="flex-1 text-foreground">{name}</span>
                  <span className="text-xs text-muted-foreground">— credits/month</span>
                </li>
              ))}
            </ul>
          </div>
        </TabsContent>

        <TabsContent value="custom" className="mt-4 min-h-[200px]">
          <div className="text-sm text-muted-foreground">
            Custom modules coming soon — contact your admin to request a custom module.
          </div>
        </TabsContent>
      </Tabs>
    </Dialog>
  )
}
