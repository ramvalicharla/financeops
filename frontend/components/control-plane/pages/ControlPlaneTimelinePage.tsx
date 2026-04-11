"use client"

import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { TimelineBody } from "@/components/control-plane/bodies/TimelineBody"

export function ControlPlaneTimelinePage() {
  return (
    <PageScaffold
      title="Timeline"
      description="Chronological control-plane activity from the backend timeline API and its declared semantics."
    >
      <section className="rounded-2xl border border-border bg-card p-4">
        <TimelineBody />
      </section>
    </PageScaffold>
  )
}
