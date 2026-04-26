"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query/keys"
import { useTenantStore } from "@/lib/store/tenant"
import { listOrgEntities, type OrgEntity } from "@/lib/api/orgSetup"

// Shape consumed by EntitySwitcher — matches EntitySwitcherOption in EntitySwitcher.tsx.
export interface UseOrgEntitiesItem {
  entity_id: string
  entity_name: string
  role?: "admin" | "accountant" | "auditor" | "viewer" | null
  functional_currency: string
  country_code: string
}

export interface UseOrgEntitiesResult {
  entities: UseOrgEntitiesItem[]
  isLoading: boolean
  isError: boolean
  error: unknown
  isFromFallback: boolean
}

function toSwitcherItem(e: OrgEntity): UseOrgEntitiesItem {
  return {
    entity_id: e.id,
    entity_name: e.display_name ?? e.legal_name,
    role: null,
    functional_currency: e.functional_currency,
    country_code: e.country_code,
  }
}

export function useOrgEntities(): UseOrgEntitiesResult {
  const legacyEntityRoles = useTenantStore((s) => s.entity_roles)

  const query = useQuery({
    queryKey: queryKeys.workspace.entities(),
    queryFn: listOrgEntities,
    staleTime: 60 * 1000,
  })

  const liveData = query.data?.map(toSwitcherItem) ?? []

  // Use session data immediately while loading (avoids layout flicker),
  // and as a fallback when the live query errors or returns empty.
  const shouldFallback =
    (query.isLoading || query.isError || (query.isSuccess && liveData.length === 0)) &&
    legacyEntityRoles.length > 0

  if (shouldFallback) {
    return {
      entities: legacyEntityRoles.map((r) => ({
        entity_id: r.entity_id,
        entity_name: r.entity_name,
        role: r.role,
        functional_currency: "",
        country_code: "",
      })),
      isLoading: false,
      isError: false,
      error: null,
      isFromFallback: true,
    }
  }

  return {
    entities: liveData,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    isFromFallback: false,
  }
}
