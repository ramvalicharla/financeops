"use client"

import { useQuery } from "@tanstack/react-query"
import { getLocation, type LocationRecord } from "@/lib/api/locations"
import { useLocationStore } from "@/lib/store/location"

type UseLocationResult = {
  location: LocationRecord | null
  isLoading: boolean
  isError: boolean
}

export function useLocation(): UseLocationResult {
  const activeLocationId = useLocationStore((state) => state.active_location_id)
  const query = useQuery({
    queryKey: ["active-location", activeLocationId],
    queryFn: () => getLocation(activeLocationId ?? ""),
    enabled: Boolean(activeLocationId),
  })

  return {
    location: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
  }
}
