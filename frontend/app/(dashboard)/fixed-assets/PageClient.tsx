"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createAsset,
  getFixedAssetRegister,
  listAssetClasses,
  listAssets,
  runPeriodDepreciation,
  type FaAsset,
  type FaRegisterLine,
} from "@/lib/api/fixedAssets"
import { listCostCentres, listLocations } from "@/lib/api/locations"
import { useLocationStore } from "@/lib/store/location"
import { useTenantStore } from "@/lib/store/tenant"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { Button } from "@/components/ui/button"
import { PaginationBar } from "@/components/ui/PaginationBar"
import { ModuleAccessNotice } from "@/components/common/ModuleAccessNotice"
import { Dialog } from "@/components/ui/Dialog"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"
import { getAccessErrorMessage } from "@/lib/ui-access"

const toCsv = (rows: FaRegisterLine[]): string => {
  const header = [
    "asset_code",
    "asset_name",
    "class_name",
    "purchase_date",
    "capitalisation_date",
    "original_cost",
    "accumulated_dep",
    "nbv",
    "ytd_depreciation",
    "status",
  ]
  const data = rows.map((row) => [
    row.asset_code,
    row.asset_name,
    row.class_name,
    row.purchase_date,
    row.capitalisation_date,
    row.original_cost,
    row.accumulated_dep,
    row.nbv,
    row.ytd_depreciation,
    row.status,
  ])
  return [header, ...data]
    .map((line) => line.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
    .join("\n")
}

const downloadText = (content: string, filename: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export default function FixedAssetsPage() {
  const queryClient = useQueryClient()
  const { fmt } = useFormattedAmount()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const entityRoles = useTenantStore((state) => state.entity_roles)
  const activeLocationId = useLocationStore((state) => state.active_location_id)

  const [view, setView] = useState<"register" | "assets">("register")
  const [gaap, setGaap] = useState("INDAS")
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().slice(0, 10))
  const [statusFilter, setStatusFilter] = useState("ALL")
  const [classFilter, setClassFilter] = useState("ALL")
  const [locationFilter, setLocationFilter] = useState("ALL")
  const [costCentreFilter, setCostCentreFilter] = useState("ALL")
  const [skip, setSkip] = useState(0)
  const [limit, setLimit] = useState(20)

  const [assetModalOpen, setAssetModalOpen] = useState(false)
  const [runModalOpen, setRunModalOpen] = useState(false)
  const [periodStart, setPeriodStart] = useState("")
  const [periodEnd, setPeriodEnd] = useState("")

  const [assetCode, setAssetCode] = useState("")
  const [assetName, setAssetName] = useState("")
  const [assetClassId, setAssetClassId] = useState("")
  const [purchaseDate, setPurchaseDate] = useState("")
  const [capitalisationDate, setCapitalisationDate] = useState("")
  const [originalCost, setOriginalCost] = useState("")
  const [residualValue, setResidualValue] = useState("0")
  const [usefulLifeYears, setUsefulLifeYears] = useState("")
  const [depreciationMethod, setDepreciationMethod] = useState("SLM")
  const [assetLocationId, setAssetLocationId] = useState("")
  const [assetCostCentreId, setAssetCostCentreId] = useState("")
  const [fieldErrors, setFieldErrors] = useState<{
    activeEntityId?: string
    assetClassId?: string
    assetCode?: string
    assetName?: string
    purchaseDate?: string
    capitalisationDate?: string
    originalCost?: string
    usefulLifeYears?: string
    depreciationMethod?: string
    periodStart?: string
    periodEnd?: string
  }>({})

  const locationsQuery = useQuery({
    queryKey: ["fa-locations", activeEntityId],
    queryFn: () => listLocations({ entity_id: activeEntityId ?? "", is_active: true, limit: 200 }),
    enabled: Boolean(activeEntityId),
  })

  const costCentresQuery = useQuery({
    queryKey: ["fa-cost-centres", activeEntityId],
    queryFn: () => listCostCentres({ entity_id: activeEntityId ?? "", limit: 300 }),
    enabled: Boolean(activeEntityId),
  })

  const classQuery = useQuery({
    queryKey: ["fa-classes", activeEntityId],
    queryFn: () => listAssetClasses(activeEntityId ?? "", 0, 200),
    enabled: Boolean(activeEntityId),
  })

  const assetsQuery = useQuery({
    queryKey: ["fa-assets", activeEntityId, statusFilter, locationFilter, costCentreFilter, skip, limit],
    queryFn: () =>
      listAssets({
        entity_id: activeEntityId ?? "",
        status: statusFilter === "ALL" ? undefined : statusFilter,
        location_id: locationFilter === "ALL" ? undefined : locationFilter,
        cost_centre_id: costCentreFilter === "ALL" ? undefined : costCentreFilter,
        skip,
        limit,
      }),
    enabled: Boolean(activeEntityId),
  })

  const registerQuery = useQuery({
    queryKey: ["fa-register", activeEntityId, asOfDate, gaap],
    queryFn: () =>
      getFixedAssetRegister({
        entity_id: activeEntityId ?? "",
        as_of_date: asOfDate,
        gaap,
      }),
    enabled: Boolean(activeEntityId) && Boolean(asOfDate),
  })

  const createAssetMutation = useMutation({
    mutationFn: () =>
      createAsset({
        entity_id: activeEntityId ?? "",
        asset_class_id: assetClassId,
        asset_code: assetCode,
        asset_name: assetName,
        purchase_date: purchaseDate,
        capitalisation_date: capitalisationDate,
        original_cost: originalCost,
        residual_value: residualValue,
        useful_life_years: usefulLifeYears,
        depreciation_method: depreciationMethod as "SLM" | "WDV" | "DOUBLE_DECLINING" | "UOP",
        location_id: assetLocationId || null,
        cost_centre_id: assetCostCentreId || null,
      }),
    onSuccess: () => {
      setAssetModalOpen(false)
      setAssetCode("")
      setAssetName("")
      setAssetClassId("")
      setPurchaseDate("")
      setCapitalisationDate("")
      setOriginalCost("")
      setResidualValue("0")
      setUsefulLifeYears("")
      setDepreciationMethod("SLM")
      setAssetLocationId("")
      setAssetCostCentreId("")
      void queryClient.invalidateQueries({ queryKey: ["fa-assets", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["fa-register", activeEntityId] })
    },
  })

  const runPeriodMutation = useMutation({
    mutationFn: () =>
      runPeriodDepreciation({
        entity_id: activeEntityId ?? "",
        period_start: periodStart,
        period_end: periodEnd,
        gaap,
      }),
    onSuccess: () => {
      setRunModalOpen(false)
      setPeriodStart("")
      setPeriodEnd("")
      void queryClient.invalidateQueries({ queryKey: ["fa-assets", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["fa-register", activeEntityId] })
    },
  })

  const classNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const row of classQuery.data?.items ?? []) {
      map.set(row.id, row.name)
    }
    return map
  }, [classQuery.data])

  const filteredRegister = useMemo(() => {
    const rows = registerQuery.data ?? []
    const statusMatch = statusFilter === "ALL" ? rows : rows.filter((row) => row.status === statusFilter)
    if (classFilter === "ALL") {
      return statusMatch
    }
    return statusMatch.filter((row) => row.class_name === classFilter)
  }, [classFilter, registerQuery.data, statusFilter])

  const rowsForCsv = filteredRegister
  const assets = assetsQuery.data?.items ?? []

  const locationRows = locationsQuery.data?.items ?? []
  const costCentreRows = costCentresQuery.data?.items ?? []
  const accessErrorMessage = getAccessErrorMessage(
    locationsQuery.error ??
      costCentresQuery.error ??
      classQuery.error ??
      assetsQuery.error ??
      registerQuery.error ??
      createAssetMutation.error ??
      runPeriodMutation.error ??
      null,
    "Fixed Assets",
  )

  if (accessErrorMessage) {
    return <ModuleAccessNotice message={accessErrorMessage} title="Module access" />
  }

  const handleCreateAsset = () => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!activeEntityId) nextFieldErrors.activeEntityId = "Entity is required."
    if (!assetClassId) nextFieldErrors.assetClassId = "Asset category is required."
    if (!assetCode.trim()) nextFieldErrors.assetCode = "Asset code is required."
    if (!assetName.trim()) nextFieldErrors.assetName = "Asset name is required."
    if (!purchaseDate) nextFieldErrors.purchaseDate = "Purchase date is required."
    if (!capitalisationDate) nextFieldErrors.capitalisationDate = "Capitalisation date is required."
    if (!originalCost.trim()) nextFieldErrors.originalCost = "Cost is required."
    if (!usefulLifeYears.trim()) nextFieldErrors.usefulLifeYears = "Useful life is required."
    if (!depreciationMethod) nextFieldErrors.depreciationMethod = "Depreciation method is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      return
    }
    setFieldErrors({})
    createAssetMutation.mutate()
  }

  const handleRunPeriod = () => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!periodStart) nextFieldErrors.periodStart = "Depreciation period start is required."
    if (!periodEnd) nextFieldErrors.periodEnd = "Depreciation period end is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      return
    }
    setFieldErrors({})
    runPeriodMutation.mutate()
  }

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Fixed Assets</h1>
          <p className="text-sm text-muted-foreground">
            Maintain the fixed asset register, run depreciation, and post revaluation or impairment.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setView(view === "register" ? "assets" : "register")}>
            {view === "register" ? "Asset List View" : "Register View"}
          </Button>
          <Button variant="outline" onClick={() => setRunModalOpen(true)} disabled={!activeEntityId}>
            Run Period Depreciation
          </Button>
          <Button onClick={() => setAssetModalOpen(true)} disabled={!activeEntityId}>
            Add Asset
          </Button>
        </div>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-8">
          <FormField id="asset-entity" label="Entity" error={fieldErrors.activeEntityId} required>
            <select
              value={activeEntityId ?? ""}
              onChange={(event) => useTenantStore.getState().setActiveEntity(event.target.value || null)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="">Select entity</option>
              {entityRoles.map((role) => (
                <option key={role.entity_id} value={role.entity_id}>
                  {role.entity_name}
                </option>
              ))}
            </select>
          </FormField>
          <select
            value={gaap}
            onChange={(event) => setGaap(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="INDAS">IndAS</option>
            <option value="IFRS">IFRS</option>
            <option value="IT_ACT">IT Act</option>
            <option value="MANAGEMENT">Management</option>
          </select>
          <input
            type="date"
            value={asOfDate}
            onChange={(event) => setAsOfDate(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="ALL">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="UNDER_INSTALLATION">Under installation</option>
            <option value="IMPAIRED">Impaired</option>
            <option value="FULLY_DEPRECIATED">Fully depreciated</option>
            <option value="DISPOSED">Disposed</option>
          </select>
          <select
            value={classFilter}
            onChange={(event) => setClassFilter(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="ALL">All classes</option>
            {(classQuery.data?.items ?? []).map((assetClass) => (
              <option key={assetClass.id} value={assetClass.name}>
                {assetClass.name}
              </option>
            ))}
          </select>
          <select
            value={locationFilter}
            onChange={(event) => setLocationFilter(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="ALL">All locations</option>
            {locationRows.map((locationRow) => (
              <option key={locationRow.id} value={locationRow.id}>
                {locationRow.location_name}
              </option>
            ))}
          </select>
          <select
            value={costCentreFilter}
            onChange={(event) => setCostCentreFilter(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="ALL">All cost centres</option>
            {costCentreRows.map((costCentreRow) => (
              <option key={costCentreRow.id} value={costCentreRow.id}>
                {costCentreRow.cost_centre_code} - {costCentreRow.cost_centre_name}
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => downloadText(toCsv(rowsForCsv), "fixed_asset_register.csv", "text/csv;charset=utf-8")}
              disabled={!rowsForCsv.length}
            >
              Export CSV
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                downloadText(
                  toCsv(rowsForCsv),
                  "fixed_asset_register.xlsx",
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
              }
              disabled={!rowsForCsv.length}
            >
              Export XLSX
            </Button>
          </div>
        </div>
      </section>

      {view === "assets" ? (
        <section className="overflow-hidden rounded-xl border border-border bg-card">
          {assetsQuery.isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, idx) => (
                <div key={idx} className="h-10 animate-pulse rounded-md bg-muted" />
              ))}
            </div>
          ) : assetsQuery.error ? (
            <div className="p-4 text-sm text-[hsl(var(--brand-danger))]">Failed to load assets.</div>
          ) : (
            <div className="overflow-x-auto">
              <table aria-label="Fixed assets" className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-muted/30">
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th scope="col" className="px-4 py-2">Code</th>
                    <th scope="col" className="px-4 py-2">Name</th>
                    <th scope="col" className="px-4 py-2">Class</th>
                    <th scope="col" className="px-4 py-2">Capitalisation Date</th>
                    <th scope="col" className="px-4 py-2">Cost</th>
                    <th scope="col" className="px-4 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {assets.map((asset: FaAsset) => (
                    <tr key={asset.id}>
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{asset.asset_code}</td>
                      <td className="px-4 py-2">
                        <Link href={`/fixed-assets/${asset.id}`} className="text-foreground underline-offset-2 hover:underline">
                          {asset.asset_name}
                        </Link>
                      </td>
                      <td className="px-4 py-2">{classNameById.get(asset.asset_class_id) ?? asset.asset_class_id}</td>
                      <td className="px-4 py-2">{asset.capitalisation_date}</td>
                      <td className="px-4 py-2">{fmt(asset.original_cost)}</td>
                      <td className="px-4 py-2">{asset.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <PaginationBar
            total={assetsQuery.data?.total ?? 0}
            skip={skip}
            limit={limit}
            onPageChange={setSkip}
            hasMore={assetsQuery.data?.has_more}
          />
        </section>
      ) : (
        <section className="overflow-hidden rounded-xl border border-border bg-card">
          {registerQuery.isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, idx) => (
                <div key={idx} className="h-10 animate-pulse rounded-md bg-muted" />
              ))}
            </div>
          ) : registerQuery.error ? (
            <div className="p-4 text-sm text-[hsl(var(--brand-danger))]">Failed to load register.</div>
          ) : (
            <div className="overflow-x-auto">
              <table aria-label="Fixed assets" className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-muted/30">
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th scope="col" className="px-4 py-2">Code</th>
                    <th scope="col" className="px-4 py-2">Name</th>
                    <th scope="col" className="px-4 py-2">Class</th>
                    <th scope="col" className="px-4 py-2">Capitalisation Date</th>
                    <th scope="col" className="px-4 py-2">Cost</th>
                    <th scope="col" className="px-4 py-2">Acc.Dep</th>
                    <th scope="col" className="px-4 py-2">NBV</th>
                    <th scope="col" className="px-4 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredRegister.map((row) => (
                    <tr key={`${row.asset_code}-${row.capitalisation_date}`}>
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{row.asset_code}</td>
                      <td className="px-4 py-2">{row.asset_name}</td>
                      <td className="px-4 py-2">{row.class_name}</td>
                      <td className="px-4 py-2">{row.capitalisation_date}</td>
                      <td className="px-4 py-2">{fmt(row.original_cost)}</td>
                      <td className="px-4 py-2">{fmt(row.accumulated_dep)}</td>
                      <td className="px-4 py-2">{fmt(row.nbv)}</td>
                      <td className="px-4 py-2">{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {assetModalOpen ? (
        <Dialog open={assetModalOpen} onClose={() => setAssetModalOpen(false)} title="Add fixed asset" size="md">
          <div className="grid gap-3 md:grid-cols-2">
              <FormField id="asset-code" label="Asset code" error={fieldErrors.assetCode} required>
                <Input value={assetCode} onChange={(event) => setAssetCode(event.target.value)} />
              </FormField>
              <FormField id="asset-name" label="Asset name" error={fieldErrors.assetName} required>
                <Input value={assetName} onChange={(event) => setAssetName(event.target.value)} />
              </FormField>
              <FormField id="asset-category" label="Asset category" error={fieldErrors.assetClassId} required>
                <select
                  value={assetClassId}
                  onChange={(event) => setAssetClassId(event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">Select asset class</option>
                  {(classQuery.data?.items ?? []).map((assetClass) => (
                    <option key={assetClass.id} value={assetClass.id}>
                      {assetClass.name}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField id="asset-depreciation-method" label="Depreciation method" error={fieldErrors.depreciationMethod} required>
                <select
                  value={depreciationMethod}
                  onChange={(event) => setDepreciationMethod(event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="SLM">SLM</option>
                  <option value="WDV">WDV</option>
                  <option value="DOUBLE_DECLINING">Double Declining</option>
                  <option value="UOP">UOP</option>
                </select>
              </FormField>
              <FormField id="asset-purchase-date" label="Purchase date" error={fieldErrors.purchaseDate} required>
                <Input type="date" value={purchaseDate} onChange={(event) => setPurchaseDate(event.target.value)} />
              </FormField>
              <FormField id="asset-capitalisation-date" label="Capitalisation date" error={fieldErrors.capitalisationDate} required>
                <Input
                  type="date"
                  value={capitalisationDate}
                  onChange={(event) => setCapitalisationDate(event.target.value)}
                />
              </FormField>
              <FormField
                id="asset-cost"
                label="Cost"
                hint="Enter the asset cost in functional currency"
                error={fieldErrors.originalCost}
                required
              >
                <Input
                  value={originalCost}
                  onChange={(event) => setOriginalCost(event.target.value)}
                  inputMode="decimal"
                />
              </FormField>
              <FormField id="asset-residual-value" label="Residual value">
                <Input
                  value={residualValue}
                  onChange={(event) => setResidualValue(event.target.value)}
                  inputMode="decimal"
                />
              </FormField>
              <FormField id="asset-useful-life" label="Useful life (months)" error={fieldErrors.usefulLifeYears} required>
                <Input
                  value={usefulLifeYears}
                  onChange={(event) => setUsefulLifeYears(event.target.value)}
                  inputMode="decimal"
                />
              </FormField>
              <FormField id="asset-location" label="Location">
                <select
                  value={assetLocationId || activeLocationId || ""}
                  onChange={(event) => setAssetLocationId(event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">Select location (optional)</option>
                  {locationRows.map((locationRow) => (
                    <option key={locationRow.id} value={locationRow.id}>
                      {locationRow.location_name}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField id="asset-cost-centre" label="Cost centre">
                <select
                  value={assetCostCentreId}
                  onChange={(event) => setAssetCostCentreId(event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">Select cost centre (optional)</option>
                  {costCentreRows.map((costCentreRow) => (
                    <option key={costCentreRow.id} value={costCentreRow.id}>
                      {costCentreRow.cost_centre_code} - {costCentreRow.cost_centre_name}
                    </option>
                  ))}
                </select>
              </FormField>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setAssetModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateAsset}
              disabled={
                !activeEntityId ||
                !assetClassId ||
                !assetCode ||
                !assetName ||
                !purchaseDate ||
                !capitalisationDate ||
                !originalCost ||
                !usefulLifeYears ||
                createAssetMutation.isPending
              }
            >
              Create Asset
            </Button>
          </div>
        </Dialog>
      ) : null}

      {runModalOpen ? (
        <Dialog open={runModalOpen} onClose={() => setRunModalOpen(false)} title="Run depreciation" size="sm">
          <div className="grid gap-3">
              <FormField id="depreciation-period-start" label="Depreciation period start" error={fieldErrors.periodStart} required>
                <Input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
              </FormField>
              <FormField id="depreciation-period-end" label="Depreciation period end" error={fieldErrors.periodEnd} required>
                <Input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
              </FormField>
              <select
                value={gaap}
                onChange={(event) => setGaap(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="INDAS">IndAS</option>
                <option value="IFRS">IFRS</option>
                <option value="IT_ACT">IT Act</option>
                <option value="MANAGEMENT">Management</option>
              </select>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setRunModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleRunPeriod}
              disabled={!activeEntityId || !periodStart || !periodEnd || runPeriodMutation.isPending}
            >
              Run
            </Button>
          </div>
        </Dialog>
      ) : null}
    </div>
  )
}
