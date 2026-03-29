import { useState } from "react"
import { RAGBadge } from "@/components/compliance/RAGBadge"
import type { ServiceRegistryModule } from "@/lib/types/service-registry"

type ServiceHealthCardProps = {
  module: ServiceRegistryModule
  isOwner: boolean
  onToggle?: (moduleName: string, nextValue: boolean) => Promise<void>
}

const toRagStatus = (status: ServiceRegistryModule["health_status"]): "green" | "amber" | "red" | "grey" => {
  if (status === "healthy") return "green"
  if (status === "degraded") return "amber"
  if (status === "unhealthy") return "red"
  return "grey"
}

export function ServiceHealthCard({ module, isOwner, onToggle }: ServiceHealthCardProps) {
  const [busy, setBusy] = useState(false)

  const handleToggle = async (nextValue: boolean) => {
    if (!onToggle) return
    setBusy(true)
    try {
      await onToggle(module.module_name, nextValue)
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">{module.module_name}</p>
          <p className="text-xs text-muted-foreground">v{module.module_version}</p>
        </div>
        <RAGBadge status={toRagStatus(module.health_status)} />
      </div>

      <p className="min-h-[2.25rem] text-xs text-muted-foreground">{module.description ?? "No description"}</p>
      <p className="mt-2 text-xs text-muted-foreground">
        Route: <span className="font-mono">{module.route_prefix ?? "—"}</span>
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Dependencies: {module.depends_on.length ? module.depends_on.join(", ") : "None"}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Last check: {module.last_health_check ?? "Never"}
      </p>

      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Enabled</span>
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-border bg-background"
          checked={module.is_enabled}
          disabled={!isOwner || busy}
          onChange={(event) => {
            void handleToggle(event.target.checked)
          }}
        />
      </div>
    </article>
  )
}

