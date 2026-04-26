"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query/keys"
import { listOrgEntities } from "@/lib/api/orgSetup"
import { useWorkspaceStore } from "@/lib/store/workspace"

export function EntityScopeBar() {
  const entityId = useWorkspaceStore((s) => s.entityId)
  const switchEntity = useWorkspaceStore((s) => s.switchEntity)
  const queryClient = useQueryClient()

  const { data: entities, isLoading } = useQuery({
    queryKey: queryKeys.workspace.entities(),
    queryFn: listOrgEntities,
    staleTime: 60_000,
    enabled: entityId !== null,
  })

  if (entityId === null) return null

  const entity = entities?.find((e) => e.id === entityId)

  function handleClearScope() {
    switchEntity(null)
    queryClient.invalidateQueries({ queryKey: ["workspace"] })
  }

  if (isLoading || !entity) {
    return <div className="w-full bg-[#E6F1FB] px-4 py-2 h-9" aria-hidden />
  }

  const entityName = entity.display_name ?? entity.legal_name

  return (
    <div className="w-full bg-[#E6F1FB] px-4 py-2 flex items-center gap-3 text-sm">
      <span className="font-medium">{entityName}</span>
      <span className="text-muted-foreground">{entity.country_code}</span>
      <span className="text-muted-foreground">{entity.functional_currency}</span>
      <button
        onClick={handleClearScope}
        className="ml-auto text-xs text-muted-foreground hover:text-foreground"
      >
        Clear scope ✕
      </button>
    </div>
  )
}
