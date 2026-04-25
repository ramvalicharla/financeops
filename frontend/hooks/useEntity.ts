"use client"

import { useQuery } from "@tanstack/react-query"
import { getOrgEntity, type OrgEntity } from "@/lib/api/orgSetup"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"

type UseEntityResult = {
  entity: OrgEntity | null
  isLoading: boolean
  isError: boolean
}

export function useEntity(): UseEntityResult {
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const query = useQuery({
    queryKey: queryKeys.workspace.activeEntity(activeEntityId),
    queryFn: () => getOrgEntity(activeEntityId ?? ""),
    enabled: Boolean(activeEntityId),
  })

  return {
    entity: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
  }
}
