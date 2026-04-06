"use client"

import Link from "next/link"
import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createPrepaidSchedule,
  listPrepaidSchedules,
  runPrepaidPeriod,
  type PrepaidSchedule,
} from "@/lib/api/prepaid"
import { listCostCentres, listLocations } from "@/lib/api/locations"
import { useLocationStore } from "@/lib/store/location"
import { useTenantStore } from "@/lib/store/tenant"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { Button } from "@/components/ui/button"
import { ModuleAccessNotice } from "@/components/common/ModuleAccessNotice"
import { Dialog } from "@/components/ui/Dialog"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"
import { getAccessErrorMessage } from "@/lib/ui-access"

export default function PrepaidExpensesPage() {
  const queryClient = useQueryClient()
  const { fmt } = useFormattedAmount()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const entityRoles = useTenantStore((state) => state.entity_roles)
  const activeLocationId = useLocationStore((state) => state.active_location_id)

  const [statusFilter, setStatusFilter] = useState("ALL")
  const [typeFilter, setTypeFilter] = useState("ALL")
  const [locationFilter, setLocationFilter] = useState("ALL")
  const [costCentreFilter, setCostCentreFilter] = useState("ALL")
  const [skip, setSkip] = useState(0)
  const [limit, setLimit] = useState(20)

  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [runModalOpen, setRunModalOpen] = useState(false)

  const [referenceNumber, setReferenceNumber] = useState("")
  const [description, setDescription] = useState("")
  const [prepaidType, setPrepaidType] = useState("INSURANCE")
  const [vendorName, setVendorName] = useState("")
  const [invoiceNumber, setInvoiceNumber] = useState("")
  const [totalAmount, setTotalAmount] = useState("")
  const [coverageStart, setCoverageStart] = useState("")
  const [coverageEnd, setCoverageEnd] = useState("")
  const [createLocationId, setCreateLocationId] = useState("")
  const [createCostCentreId, setCreateCostCentreId] = useState("")

  const [periodStart, setPeriodStart] = useState("")
  const [periodEnd, setPeriodEnd] = useState("")
  const [fieldErrors, setFieldErrors] = useState<{
    activeEntityId?: string
    referenceNumber?: string
    description?: string
    prepaidType?: string
    vendorName?: string
    totalAmount?: string
    coverageStart?: string
    coverageEnd?: string
    periodStart?: string
    periodEnd?: string
  }>({})

  const locationsQuery = useQuery({
    queryKey: ["prepaid-locations", activeEntityId],
    queryFn: () => listLocations({ entity_id: activeEntityId ?? "", is_active: true, limit: 200 }),
    enabled: Boolean(activeEntityId),
  })

  const costCentresQuery = useQuery({
    queryKey: ["prepaid-cost-centres", activeEntityId],
    queryFn: () => listCostCentres({ entity_id: activeEntityId ?? "", limit: 300 }),
    enabled: Boolean(activeEntityId),
  })

  const schedulesQuery = useQuery({
    queryKey: ["prepaid-schedules", activeEntityId, statusFilter, typeFilter, locationFilter, costCentreFilter, skip, limit],
    queryFn: () =>
      listPrepaidSchedules({
        entity_id: activeEntityId ?? "",
        status: statusFilter === "ALL" ? undefined : statusFilter,
        prepaid_type: typeFilter === "ALL" ? undefined : typeFilter,
        location_id: locationFilter === "ALL" ? undefined : locationFilter,
        cost_centre_id: costCentreFilter === "ALL" ? undefined : costCentreFilter,
        skip,
        limit,
      }),
    enabled: Boolean(activeEntityId),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      createPrepaidSchedule({
        entity_id: activeEntityId ?? "",
        reference_number: referenceNumber,
        description,
        prepaid_type: prepaidType as "INSURANCE" | "SUBSCRIPTION" | "MAINTENANCE" | "RENT_ADVANCE" | "OTHER",
        vendor_name: vendorName || null,
        invoice_number: invoiceNumber || null,
        total_amount: totalAmount,
        coverage_start: coverageStart,
        coverage_end: coverageEnd,
        location_id: createLocationId || null,
        cost_centre_id: createCostCentreId || null,
      }),
    onSuccess: () => {
      setCreateModalOpen(false)
      setReferenceNumber("")
      setDescription("")
      setPrepaidType("INSURANCE")
      setVendorName("")
      setInvoiceNumber("")
      setTotalAmount("")
      setCoverageStart("")
      setCoverageEnd("")
      setCreateLocationId("")
      setCreateCostCentreId("")
      void queryClient.invalidateQueries({ queryKey: ["prepaid-schedules", activeEntityId] })
    },
  })

  const runPeriodMutation = useMutation({
    mutationFn: () =>
      runPrepaidPeriod({
        entity_id: activeEntityId ?? "",
        period_start: periodStart,
        period_end: periodEnd,
      }),
    onSuccess: () => {
      setRunModalOpen(false)
      setPeriodStart("")
      setPeriodEnd("")
      void queryClient.invalidateQueries({ queryKey: ["prepaid-schedules", activeEntityId] })
    },
  })

  const rows = schedulesQuery.data?.items ?? []
  const locationRows = locationsQuery.data?.items ?? []
  const costCentreRows = costCentresQuery.data?.items ?? []
  const accessErrorMessage = getAccessErrorMessage(
    locationsQuery.error ??
      costCentresQuery.error ??
      schedulesQuery.error ??
      createMutation.error ??
      runPeriodMutation.error ??
      null,
    "Prepaid Expenses",
  )

  if (accessErrorMessage) {
    return <ModuleAccessNotice message={accessErrorMessage} title="Module access" />
  }

  const handleCreate = () => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!activeEntityId) nextFieldErrors.activeEntityId = "Entity is required."
    if (!referenceNumber.trim()) nextFieldErrors.referenceNumber = "Reference number is required."
    if (!description.trim()) nextFieldErrors.description = "Description is required."
    if (!prepaidType) nextFieldErrors.prepaidType = "Prepaid type is required."
    if (!vendorName.trim()) nextFieldErrors.vendorName = "Vendor is required."
    if (!totalAmount.trim()) nextFieldErrors.totalAmount = "Total amount is required."
    if (!coverageStart) nextFieldErrors.coverageStart = "Amortisation start date is required."
    if (!coverageEnd) nextFieldErrors.coverageEnd = "Amortisation end date is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      return
    }
    setFieldErrors({})
    createMutation.mutate()
  }

  const handleRunPeriod = () => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!periodStart) nextFieldErrors.periodStart = "Amortisation period start is required."
    if (!periodEnd) nextFieldErrors.periodEnd = "Amortisation period end is required."
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
          <h1 className="text-2xl font-semibold text-foreground">Prepaid Expenses</h1>
          <p className="text-sm text-muted-foreground">
            Manage prepaid schedules, run monthly amortisation, and monitor remaining balances.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setRunModalOpen(true)} disabled={!activeEntityId}>
            Run Period
          </Button>
          <Button onClick={() => setCreateModalOpen(true)} disabled={!activeEntityId}>
            Add Prepaid
          </Button>
        </div>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-7">
          <FormField id="prepaid-entity" label="Entity" error={fieldErrors.activeEntityId} required>
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
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="ALL">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="FULLY_AMORTISED">Fully amortised</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
          <select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="ALL">All types</option>
            <option value="INSURANCE">Insurance</option>
            <option value="SUBSCRIPTION">Subscription</option>
            <option value="MAINTENANCE">Maintenance</option>
            <option value="RENT_ADVANCE">Rent Advance</option>
            <option value="OTHER">Other</option>
          </select>
          <select
            value={String(limit)}
            onChange={(event) => {
              const nextLimit = Number(event.target.value)
              setLimit(nextLimit)
              setSkip(0)
            }}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="10">10 / page</option>
            <option value="20">20 / page</option>
            <option value="50">50 / page</option>
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
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {schedulesQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, idx) => (
              <div key={idx} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : schedulesQuery.error ? (
          <div className="p-4 text-sm text-[hsl(var(--brand-danger))]">Failed to load prepaid schedules.</div>
        ) : (
          <div className="overflow-x-auto">
            <table aria-label="Prepaid schedules" className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-2">Reference</th>
                  <th scope="col" className="px-4 py-2">Description</th>
                  <th scope="col" className="px-4 py-2">Type</th>
                  <th scope="col" className="px-4 py-2">Vendor</th>
                  <th scope="col" className="px-4 py-2">Total</th>
                  <th scope="col" className="px-4 py-2">Amortised</th>
                  <th scope="col" className="px-4 py-2">Remaining</th>
                  <th scope="col" className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((row: PrepaidSchedule) => (
                  <tr key={row.id}>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{row.reference_number}</td>
                    <td className="px-4 py-2">
                      <Link href={`/prepaid/${row.id}`} className="text-foreground underline-offset-2 hover:underline">
                        {row.description}
                      </Link>
                    </td>
                    <td className="px-4 py-2">{row.prepaid_type}</td>
                    <td className="px-4 py-2">{row.vendor_name ?? "-"}</td>
                    <td className="px-4 py-2">{fmt(row.total_amount)}</td>
                    <td className="px-4 py-2">{fmt(row.amortised_amount)}</td>
                    <td className="px-4 py-2">{fmt(row.remaining_amount)}</td>
                    <td className="px-4 py-2">{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted-foreground">
          <p>
            Showing {rows.length} of {schedulesQuery.data?.total ?? 0}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSkip(Math.max(0, skip - limit))}
              disabled={skip === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSkip(skip + limit)}
              disabled={!(schedulesQuery.data?.has_more ?? false)}
            >
              Next
            </Button>
          </div>
        </div>
      </section>

      {createModalOpen ? (
        <Dialog open={createModalOpen} onClose={() => setCreateModalOpen(false)} title="Add prepaid schedule" size="md">
          <div className="grid gap-3 md:grid-cols-2">
              <FormField id="prepaid-reference-number" label="Reference number" error={fieldErrors.referenceNumber} required>
                <Input
                  value={referenceNumber}
                  onChange={(event) => setReferenceNumber(event.target.value)}
                />
              </FormField>
              <FormField id="prepaid-method" label="Amortisation method" error={fieldErrors.prepaidType} required>
                <select
                  value={prepaidType}
                  onChange={(event) => setPrepaidType(event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="INSURANCE">Insurance</option>
                  <option value="SUBSCRIPTION">Subscription</option>
                  <option value="MAINTENANCE">Maintenance</option>
                  <option value="RENT_ADVANCE">Rent Advance</option>
                  <option value="OTHER">Other</option>
                </select>
              </FormField>
              <div className="md:col-span-2">
                <FormField id="prepaid-description" label="Description" error={fieldErrors.description} required>
                  <Input
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                  />
                </FormField>
              </div>
              <FormField id="prepaid-vendor" label="Vendor" error={fieldErrors.vendorName} required>
                <Input value={vendorName} onChange={(event) => setVendorName(event.target.value)} />
              </FormField>
              <FormField id="prepaid-invoice-number" label="Invoice number">
                <Input
                  value={invoiceNumber}
                  onChange={(event) => setInvoiceNumber(event.target.value)}
                />
              </FormField>
              <FormField
                id="prepaid-amount"
                label="Total amount"
                hint="Enter the total prepaid amount in functional currency"
                error={fieldErrors.totalAmount}
                required
              >
                <Input value={totalAmount} onChange={(event) => setTotalAmount(event.target.value)} inputMode="decimal" />
              </FormField>
              <FormField id="prepaid-start-date" label="Amortisation start date" error={fieldErrors.coverageStart} required>
                <Input
                  type="date"
                  value={coverageStart}
                  onChange={(event) => setCoverageStart(event.target.value)}
                />
              </FormField>
              <FormField id="prepaid-end-date" label="Amortisation end date" error={fieldErrors.coverageEnd} required>
                <Input type="date" value={coverageEnd} onChange={(event) => setCoverageEnd(event.target.value)} />
              </FormField>
              <FormField id="prepaid-location" label="Location">
                <select
                  value={createLocationId || activeLocationId || ""}
                  onChange={(event) => setCreateLocationId(event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">Location (optional)</option>
                  {locationRows.map((locationRow) => (
                    <option key={locationRow.id} value={locationRow.id}>
                      {locationRow.location_name}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField id="prepaid-cost-centre" label="Cost centre">
                <select
                  value={createCostCentreId}
                  onChange={(event) => setCreateCostCentreId(event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">Cost centre (optional)</option>
                  {costCentreRows.map((costCentreRow) => (
                    <option key={costCentreRow.id} value={costCentreRow.id}>
                      {costCentreRow.cost_centre_code} - {costCentreRow.cost_centre_name}
                    </option>
                  ))}
                </select>
              </FormField>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={
                !activeEntityId ||
                !referenceNumber ||
                !description ||
                !totalAmount ||
                !coverageStart ||
                !coverageEnd ||
                createMutation.isPending
              }
            >
              Create
            </Button>
          </div>
        </Dialog>
      ) : null}

      {runModalOpen ? (
        <Dialog open={runModalOpen} onClose={() => setRunModalOpen(false)} title="Run amortisation" size="sm">
          <div className="grid gap-3">
              <FormField id="prepaid-period-start" label="Amortisation period start" error={fieldErrors.periodStart} required>
                <Input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
              </FormField>
              <FormField id="prepaid-period-end" label="Amortisation period end" error={fieldErrors.periodEnd} required>
                <Input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
              </FormField>
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
