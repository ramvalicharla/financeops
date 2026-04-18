"use client"

import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import apiClient from "@/lib/api/client"

type ProviderSlot = {
  name: string
  provider: string
  model: string
  task_types: string[]
  priority: number
  status: "active" | "degraded" | "disabled"
}

export default function AIProvidersAdminPage() {
  const [slots, setSlots] = useState<ProviderSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get<{ providers: ProviderSlot[] }>(
        "/api/v1/admin/ai/providers",
      )
      setSlots(response.data.providers)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load provider slots")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const toggle = async (slot: ProviderSlot): Promise<void> => {
    const action = slot.status === "disabled" ? "enable" : "disable"
    await apiClient.post(`/api/v1/admin/ai/providers/${slot.name}/${action}`)
    await load()
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">AI Provider Slots</h1>
      {loading ? <p className="text-sm text-muted-foreground">Loading provider slots...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      <div className="space-y-2">
        {slots.map((slot) => (
          <div
            key={slot.name}
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card p-3"
          >
            <div>
              <p className="font-medium text-foreground">{slot.name}</p>
              <p className="text-xs text-muted-foreground">
                {slot.provider} · {slot.model} · priority {slot.priority}
              </p>
              <p className="text-xs text-muted-foreground">
                tasks: {slot.task_types.join(", ") || "all"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`rounded-full border px-2 py-0.5 text-xs ${
                  slot.status === "active"
                    ? "border-emerald-500/50 text-emerald-400"
                    : slot.status === "disabled"
                      ? "border-red-500/50 text-red-400"
                      : "border-amber-500/50 text-amber-400"
                }`}
              >
                {slot.status}
              </span>
              <Button variant="outline" size="sm" onClick={() => void toggle(slot)}>
                {slot.status === "disabled" ? "Enable" : "Disable"}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
