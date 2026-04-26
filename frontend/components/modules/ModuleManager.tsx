"use client"

import { GripVertical } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { Dialog } from "@/components/ui/Dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { queryKeys } from "@/lib/query/keys"
import { getModuleIcon } from "@/components/layout/tabs/module-icons"
import { useModuleManagerStore } from "@/lib/store/moduleManager"
import { useModuleOrderStore } from "@/lib/store/moduleOrder"
import { useWorkspaceStore } from "@/lib/store/workspace"

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
          <div className="text-sm text-muted-foreground">Available</div>
        </TabsContent>

        <TabsContent value="premium" className="mt-4 min-h-[200px]">
          <div className="text-sm text-muted-foreground">Premium</div>
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
