"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

// SP-3A (OQ-1 REDIRECT): The Module Manager modal is the new home for workspace
// tab configuration. This page redirects to /dashboard?modal=module-manager so
// the modal opens in context. Old /api/v1/modules/{name}/enable|disable calls
// are intentionally dropped — the new write path is POST /api/v1/orgs/{orgId}/modules
// (backend ticket pending, stubbed in ModuleManager Available tab).
export default function ModulesPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace("/dashboard?modal=module-manager")
  }, [router])

  return (
    <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
      Redirecting to Module Manager…
    </div>
  )
}
