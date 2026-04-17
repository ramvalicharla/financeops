"use client"

import type { ReactNode } from "react"
import { useSession } from "next-auth/react"
import { useCurrentEntitlements } from "@/hooks/useBilling"
import { canPerformAction } from "@/lib/ui-access"

interface ActionGuardProps {
  action: string
  children: ReactNode
}

export function ActionGuard({ action, children }: ActionGuardProps) {
  const { data: session } = useSession()
  const entitlementsQuery = useCurrentEntitlements({
    enabled: Boolean(session?.user?.tenant_id),
  })

  if (!session?.user) {
    return null
  }

  const accessContext = {
    role: session.user.role,
    entitlements: entitlementsQuery.data,
  }

  if (!canPerformAction(action, accessContext)) {
    return null
  }

  return <>{children}</>
}
