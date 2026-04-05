"use client"

import { useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import {
  getServiceDashboard,
  runServiceHealthCheck,
  toggleServiceModule,
} from "@/lib/api/service-registry"
import type { ServiceDashboard, ServiceRegistryModule } from "@/lib/types/service-registry"
import { RAGBadge } from "@/components/compliance/RAGBadge"
import { ServiceHealthCard } from "@/components/admin/ServiceHealthCard"
import { TaskRegistryTable } from "@/components/admin/TaskRegistryTable"

const toRagStatus = (status: ServiceDashboard["overall_status"]): "green" | "amber" | "red" => {
  if (status === "healthy") return "green"
  if (status === "degraded") return "amber"
  return "red"
}

export default function AdminServicesPage() {
  const { data: session } = useSession()
  const [dashboard, setDashboard] = useState<ServiceDashboard | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  const isOwner = session?.user?.role === "platform_owner" || session?.user?.role === "super_admin"

  const load = async () => {
    setError(null)
    try {
      const payload = await getServiceDashboard()
      setDashboard(payload)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load service registry")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const runChecks = async () => {
    setRunning(true)
    setError(null)
    try {
      const payload = await runServiceHealthCheck()
      setMessage(
        `Health checks complete: ${payload.healthy} healthy, ${payload.degraded} degraded, ${payload.unhealthy} unhealthy.`,
      )
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to run service health checks")
    } finally {
      setRunning(false)
    }
  }

  const modules = useMemo(() => dashboard?.modules ?? [], [dashboard])
  const tasks = useMemo(() => dashboard?.tasks ?? [], [dashboard])

  const onToggleModule = async (moduleName: string, nextValue: boolean) => {
    await toggleServiceModule(moduleName, nextValue)
    await load()
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Service Registry</h1>
          <p className="text-sm text-muted-foreground">
            Platform service and task health across all modules.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dashboard ? <RAGBadge status={toRagStatus(dashboard.overall_status)} /> : null}
          <button
            type="button"
            onClick={() => void runChecks()}
            disabled={running}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            {running ? "Running..." : "Run Health Check"}
          </button>
        </div>
      </header>

      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading service registry...</p> : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Modules</h2>
        {modules.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {modules.map((module: ServiceRegistryModule) => (
              <ServiceHealthCard
                key={module.id}
                module={module}
                isOwner={Boolean(isOwner)}
                onToggle={onToggleModule}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
            No registered services found yet.
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Tasks</h2>
        <TaskRegistryTable tasks={tasks} />
      </section>
    </div>
  )
}
