"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { ValuationModel } from "@/components/advisory/ma/ValuationModel"
import { createMAValuation, listMAValuations } from "@/lib/api/ma"
import type { MAValuation } from "@/lib/types/ma"

export default function MAValuationPage() {
  const params = useParams()
  const workspaceId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""
  const [valuations, setValuations] = useState<MAValuation[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const payload = await listMAValuations(workspaceId, { limit: 50, offset: 0 })
      setValuations(payload.data)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load valuations")
    }
  }, [workspaceId])

  useEffect(() => {
    if (workspaceId) {
      void load()
    }
  }, [workspaceId, load])

  const handleCreate = async (payload: {
    valuation_name: string
    valuation_method: string
    assumptions: Record<string, string>
  }) => {
    await createMAValuation(workspaceId, payload)
    await load()
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Valuation Model</h1>
          <p className="text-sm text-muted-foreground">DCF and comparable companies valuation engine</p>
        </div>
        <Link href={`/advisory/ma/${workspaceId}`} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          Back to Workspace
        </Link>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      <ValuationModel valuations={valuations} onCreate={handleCreate} />
    </div>
  )
}
