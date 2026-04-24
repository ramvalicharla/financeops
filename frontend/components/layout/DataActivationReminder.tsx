"use client"

import { useQuery } from "@tanstack/react-query"
import { usePathname } from "next/navigation"
import type { CoaStatus } from "@/types/api"
import { getCurrentTenantProfile } from "@/lib/api/tenant"
import { queryKeys } from "@/lib/query/keys"

const DATA_DEPENDENT_PREFIXES = [
  "/dashboard",
  "/erp",
  "/sync",
  "/mis",
  "/reconciliation",
  "/board-pack",
  "/fixed-assets",
  "/prepaid",
  "/working-capital",
  "/revenue",
  "/lease",
  "/gst",
  "/accounting",
  "/consolidation",
  "/settings/chart-of-accounts",
  "/settings/erp-mapping",
]

const isDataDependentPath = (pathname: string): boolean =>
  DATA_DEPENDENT_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))

export function DataActivationReminder({
  initialCoaStatus,
  initialOnboardingScore,
}: {
  initialCoaStatus: CoaStatus
  initialOnboardingScore: number
}) {
  const pathname = usePathname() ?? ""
  const isRelevantPage = isDataDependentPath(pathname)
  const tenantQuery = useQuery({
    queryKey: queryKeys.tenantProfile.dataActivationReminder(),
    queryFn: getCurrentTenantProfile,
    enabled: isRelevantPage,
    staleTime: 30_000,
  })

  const coaStatus = tenantQuery.data?.coa_status ?? initialCoaStatus
  const onboardingScore = tenantQuery.data?.onboarding_score ?? initialOnboardingScore

  if (coaStatus !== "skipped" || !isRelevantPage) {
    return null
  }

  return (
    <div className="mb-4 rounded-xl border border-amber-300/40 bg-amber-50/80 px-4 py-3 text-sm text-amber-950">
      <p className="font-medium">Upload trial balance or connect ERP to unlock full features</p>
      <p className="mt-1 text-amber-900/80">
        Your onboarding completeness is {onboardingScore}/100. You can keep working and finish data
        activation later from settings.
      </p>
    </div>
  )
}
