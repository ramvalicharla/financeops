"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"
import { GAAPComparisonTable } from "@/components/gaap/GAAPComparisonTable"
import { GAAPToggle } from "@/components/gaap/GAAPToggle"
import { computeGAAP, getGAAPComparison, getGAAPConfig } from "@/lib/api/sprint11"
import { useDisplayScale } from "@/lib/store/displayScale"
import { type GAAPComparison, type GAAPConfig } from "@/lib/types/sprint11"

const frameworks = ["INDAS", "IFRS", "USGAAP", "MANAGEMENT"] as const

export default function GaapPage() {
  const [active, setActive] = useState<string>("INDAS")
  const [period, setPeriod] = useState(
    `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`,
  )
  const [config, setConfig] = useState<GAAPConfig | null>(null)
  const [comparison, setComparison] = useState<GAAPComparison | null>(null)
  const [loadingFramework, setLoadingFramework] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const scale = useDisplayScale((state) => state.scale)
  const setScale = useDisplayScale((state) => state.setScale)

  const load = useCallback(async (): Promise<void> => {
    setError(null)
    try {
      const [configPayload, comparisonPayload] = await Promise.all([
        getGAAPConfig(),
        getGAAPComparison(period),
      ])
      setConfig(configPayload)
      setComparison(comparisonPayload)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load GAAP data")
    }
  }, [period])

  useEffect(() => {
    void load()
  }, [period, load])

  const availableFrameworks = useMemo(
    () => (comparison ? comparison.frameworks.map((row) => row.gaap_framework.toUpperCase()) : []),
    [comparison],
  )

  const handleCompute = async (framework: string): Promise<void> => {
    setLoadingFramework(framework)
    setError(null)
    try {
      await computeGAAP(period, framework)
      await load()
    } catch (computeError) {
      setError(computeError instanceof Error ? computeError.message : "Failed to compute GAAP view")
    } finally {
      setLoadingFramework(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold text-foreground">Multi-GAAP Reporting</h1>
        <ScaleSelector value={scale} onChange={setScale} />
      </div>
      <div className="max-w-xs">
        <FormField id="gaap-period" label="Reporting period">
          <Input value={period} onChange={(event) => setPeriod(event.target.value)} />
        </FormField>
      </div>
      <GAAPToggle
        frameworks={[...frameworks]}
        active={active}
        onSelect={setActive}
        available={availableFrameworks}
        onCompute={handleCompute}
        loadingFramework={loadingFramework}
      />
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {config ? (
        <p className="text-sm text-muted-foreground">Primary GAAP: {config.primary_gaap}</p>
      ) : null}
      {comparison ? (
        <GAAPComparisonTable comparison={comparison} frameworks={[...frameworks]} />
      ) : (
        <p className="text-sm text-muted-foreground">No GAAP runs available for this period.</p>
      )}
    </div>
  )
}
