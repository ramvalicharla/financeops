"use client"

import type { ReactNode } from "react"
import { PageScaffold } from "@/components/control-plane/PageScaffold"

interface LimitedControlPlanePageProps {
  title: string
  description: string
  body?: ReactNode
}

export function LimitedControlPlanePage({
  title,
  description,
  body,
}: LimitedControlPlanePageProps) {
  return (
    <PageScaffold title={title} description={description}>
      <section className="rounded-2xl border border-dashed border-border bg-card p-6">
        <p className="text-sm text-muted-foreground">
          {body ?? "This control-plane surface is limited by the current backend contract."}
        </p>
      </section>
    </PageScaffold>
  )
}
