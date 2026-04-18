"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { DeferredTaxSchedule } from "@/components/tax/DeferredTaxSchedule"
import { TaxProvisionTable } from "@/components/tax/TaxProvisionTable"
import { getTaxProvision, listTaxPositions } from "@/lib/api/sprint11"
import { type TaxPosition, type TaxProvisionRun } from "@/lib/types/sprint11"

export default function TaxDetailPage() {
  const params = useParams<{ id: string }>()
  const period = params?.id ?? ""
  const [provision, setProvision] = useState<TaxProvisionRun | null>(null)
  const [positions, setPositions] = useState<TaxPosition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!period) {
      return
    }
    const load = async (): Promise<void> => {
      setLoading(true)
      setError(null)
      try {
        const [provisionPayload, positionsPayload] = await Promise.all([
          getTaxProvision(period),
          listTaxPositions({ limit: 200, offset: 0 }),
        ])
        setProvision(provisionPayload)
        setPositions(positionsPayload.data)
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load period detail")
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [period])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Tax Period Detail</h1>
      {!period ? <p className="text-sm text-red-400">Missing period.</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading period...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {provision ? <TaxProvisionTable provision={provision} /> : null}
      <DeferredTaxSchedule positions={positions} />
    </div>
  )
}
