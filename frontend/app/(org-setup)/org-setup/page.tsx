import { Suspense } from "react"
import OrgSetupPageClient from "./OrgSetupPageClient"

function OrgSetupLoadingFallback() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="h-14 animate-pulse rounded-xl bg-muted" />
      ))}
    </div>
  )
}

export default function OrgSetupPage() {
  return (
    <Suspense fallback={<OrgSetupLoadingFallback />}>
      <OrgSetupPageClient />
    </Suspense>
  )
}
