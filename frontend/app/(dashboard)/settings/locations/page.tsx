"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createLocation,
  listLocations,
  listStateCodes,
  setPrimaryLocation,
  updateLocation,
  validateGstin,
  type LocationRecord,
} from "@/lib/api/locations"
import { useTenantStore } from "@/lib/store/tenant"
import { useLocationStore } from "@/lib/store/location"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type EditableLocation = {
  location_name: string
  location_code: string
  gstin: string
  state_code: string
  address_line1: string
  city: string
  state: string
  pincode: string
  is_active: boolean
}

const toEditable = (row: LocationRecord): EditableLocation => ({
  location_name: row.location_name,
  location_code: row.location_code,
  gstin: row.gstin ?? "",
  state_code: row.state_code ?? "",
  address_line1: row.address_line1 ?? "",
  city: row.city ?? "",
  state: row.state ?? "",
  pincode: row.pincode ?? "",
  is_active: row.is_active,
})

export default function LocationsSettingsPage() {
  const queryClient = useQueryClient()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const entityRoles = useTenantStore((state) => state.entity_roles)
  const activeLocationId = useLocationStore((state) => state.active_location_id)
  const setActiveLocation = useLocationStore((state) => state.setActiveLocation)

  const [skip, setSkip] = useState(0)
  const [limit, setLimit] = useState(20)
  const [createOpen, setCreateOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingDraft, setEditingDraft] = useState<EditableLocation | null>(null)

  const [locationName, setLocationName] = useState("")
  const [locationCode, setLocationCode] = useState("")
  const [gstin, setGstin] = useState("")
  const [stateCode, setStateCode] = useState("")
  const [addressLine1, setAddressLine1] = useState("")
  const [city, setCity] = useState("")
  const [stateName, setStateName] = useState("")
  const [pincode, setPincode] = useState("")
  const [gstinHint, setGstinHint] = useState<string | null>(null)
  const [gstinError, setGstinError] = useState<string | null>(null)

  const locationsQuery = useQuery({
    queryKey: ["settings-locations", activeEntityId, skip, limit],
    queryFn: () =>
      listLocations({
        entity_id: activeEntityId ?? "",
        skip,
        limit,
      }),
    enabled: Boolean(activeEntityId),
  })

  const stateCodesQuery = useQuery({
    queryKey: ["india-state-codes"],
    queryFn: listStateCodes,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      createLocation({
        entity_id: activeEntityId ?? "",
        location_name: locationName,
        location_code: locationCode,
        gstin: gstin || null,
        state_code: stateCode || null,
        address_line1: addressLine1 || null,
        city: city || null,
        state: stateName || null,
        pincode: pincode || null,
      }),
    onSuccess: (row) => {
      setCreateOpen(false)
      setLocationName("")
      setLocationCode("")
      setGstin("")
      setStateCode("")
      setAddressLine1("")
      setCity("")
      setStateName("")
      setPincode("")
      setGstinHint(null)
      setGstinError(null)
      setActiveLocation(row.id)
      void queryClient.invalidateQueries({ queryKey: ["settings-locations", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["entity-locations", activeEntityId] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      updateLocation(id, payload),
    onSuccess: () => {
      setEditingId(null)
      setEditingDraft(null)
      void queryClient.invalidateQueries({ queryKey: ["settings-locations", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["entity-locations", activeEntityId] })
    },
  })

  const setPrimaryMutation = useMutation({
    mutationFn: (locationId: string) => setPrimaryLocation(locationId),
    onSuccess: (row) => {
      setActiveLocation(row.id)
      void queryClient.invalidateQueries({ queryKey: ["settings-locations", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["entity-locations", activeEntityId] })
    },
  })

  const handleValidateGstin = async (value: string, mode: "create" | "edit") => {
    const trimmed = value.trim().toUpperCase()
    if (!trimmed) {
      if (mode === "create") {
        setGstinError(null)
        setGstinHint(null)
      }
      return
    }
    const result = await validateGstin(trimmed)
    if (!result.valid) {
      if (mode === "create") {
        setGstinError("Invalid GSTIN")
        setGstinHint(null)
      }
      return
    }
    if (mode === "create") {
      setGstinError(null)
      setGstinHint(result.state_name ? `${result.state_code} - ${result.state_name}` : result.state_code)
      if (result.state_code) {
        setStateCode(result.state_code)
      }
    }
    if (mode === "edit" && editingDraft) {
      setEditingDraft({
        ...editingDraft,
        state_code: result.state_code ?? editingDraft.state_code,
      })
    }
  }

  const rows = locationsQuery.data?.items ?? []
  const entityName = useMemo(
    () => entityRoles.find((role) => role.entity_id === activeEntityId)?.entity_name ?? "",
    [activeEntityId, entityRoles],
  )

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Locations</h1>
          <p className="text-sm text-muted-foreground">
            Manage branch and office locations for {entityName || "the active entity"}.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setCreateOpen((value) => !value)} disabled={!activeEntityId}>
            {createOpen ? "Close" : "Add Location"}
          </Button>
        </div>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <select
            value={activeEntityId ?? ""}
            onChange={(event) => {
              useTenantStore.getState().setActiveEntity(event.target.value || null)
              useLocationStore.getState().setActiveLocation(null)
              setSkip(0)
            }}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select entity</option>
            {entityRoles.map((role) => (
              <option key={role.entity_id} value={role.entity_id}>
                {role.entity_name}
              </option>
            ))}
          </select>
          <select
            value={String(limit)}
            onChange={(event) => {
              setLimit(Number(event.target.value))
              setSkip(0)
            }}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="10">10 / page</option>
            <option value="20">20 / page</option>
            <option value="50">50 / page</option>
          </select>
        </div>
      </section>

      {createOpen ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-foreground">New Location</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <Input value={locationName} onChange={(event) => setLocationName(event.target.value)} placeholder="Location name" />
            <Input value={locationCode} onChange={(event) => setLocationCode(event.target.value)} placeholder="Location code" />
            <Input
              value={gstin}
              onChange={(event) => setGstin(event.target.value.toUpperCase())}
              onBlur={() => void handleValidateGstin(gstin, "create")}
              placeholder="GSTIN"
            />
            <Input value={stateCode} onChange={(event) => setStateCode(event.target.value)} placeholder="State code" />
            <Input value={addressLine1} onChange={(event) => setAddressLine1(event.target.value)} placeholder="Address" />
            <Input value={city} onChange={(event) => setCity(event.target.value)} placeholder="City" />
            <Input value={stateName} onChange={(event) => setStateName(event.target.value)} placeholder="State" />
            <Input value={pincode} onChange={(event) => setPincode(event.target.value)} placeholder="Pincode" />
          </div>
          {gstinHint ? <p className="mt-2 text-xs text-emerald-300">GSTIN state: {gstinHint}</p> : null}
          {gstinError ? <p className="mt-2 text-xs text-[hsl(var(--brand-danger))]">{gstinError}</p> : null}
          <div className="mt-4 flex justify-end">
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!activeEntityId || !locationName || !locationCode || createMutation.isPending || Boolean(gstinError)}
            >
              Create Location
            </Button>
          </div>
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {locationsQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : locationsQuery.error ? (
          <div className="p-4 text-sm text-[hsl(var(--brand-danger))]">Failed to load locations.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Code</th>
                  <th className="px-4 py-2">GSTIN</th>
                  <th className="px-4 py-2">State</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((row) => {
                  const isEditing = editingId === row.id
                  const draft = isEditing ? editingDraft : null
                  return (
                    <tr key={row.id}>
                      <td className="px-4 py-2">
                        {isEditing && draft ? (
                          <Input
                            value={draft.location_name}
                            onChange={(event) =>
                              setEditingDraft({ ...draft, location_name: event.target.value })
                            }
                          />
                        ) : (
                          <span className="text-foreground">{row.location_name}</span>
                        )}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                        {isEditing && draft ? (
                          <Input
                            value={draft.location_code}
                            onChange={(event) =>
                              setEditingDraft({ ...draft, location_code: event.target.value })
                            }
                          />
                        ) : (
                          row.location_code
                        )}
                      </td>
                      <td className="px-4 py-2">
                        {isEditing && draft ? (
                          <Input
                            value={draft.gstin}
                            onChange={(event) => setEditingDraft({ ...draft, gstin: event.target.value.toUpperCase() })}
                            onBlur={() => void handleValidateGstin(draft.gstin, "edit")}
                          />
                        ) : (
                          row.gstin ?? "-"
                        )}
                      </td>
                      <td className="px-4 py-2">
                        {isEditing && draft ? (
                          <select
                            value={draft.state_code}
                            onChange={(event) => setEditingDraft({ ...draft, state_code: event.target.value })}
                            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                          >
                            <option value="">Select state</option>
                            {(stateCodesQuery.data ?? []).map((stateCodeRow) => (
                              <option key={stateCodeRow.code} value={stateCodeRow.code}>
                                {stateCodeRow.code} - {stateCodeRow.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          row.state_code ?? "-"
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`rounded-full px-2 py-1 text-xs ${
                            row.is_active
                              ? "bg-emerald-500/15 text-emerald-300"
                              : "bg-rose-500/15 text-rose-300"
                          }`}
                        >
                          {row.is_active ? "Active" : "Inactive"}
                        </span>
                        {row.is_primary ? (
                          <span className="ml-2 rounded-full bg-indigo-500/15 px-2 py-1 text-xs text-indigo-300">
                            Primary
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {isEditing && draft ? (
                          <div className="inline-flex gap-2">
                            <Button
                              size="sm"
                              onClick={() =>
                                updateMutation.mutate({
                                  id: row.id,
                                  payload: {
                                    location_name: draft.location_name,
                                    location_code: draft.location_code,
                                    gstin: draft.gstin || null,
                                    state_code: draft.state_code || null,
                                    is_active: draft.is_active,
                                  },
                                })
                              }
                            >
                              Save
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingId(null)
                                setEditingDraft(null)
                              }}
                            >
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <div className="inline-flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingId(row.id)
                                setEditingDraft(toEditable(row))
                              }}
                            >
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                updateMutation.mutate({
                                  id: row.id,
                                  payload: { is_active: !row.is_active },
                                })
                              }
                            >
                              {row.is_active ? "Deactivate" : "Activate"}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setPrimaryMutation.mutate(row.id)}
                              disabled={row.is_primary || setPrimaryMutation.isPending}
                            >
                              Set Primary
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted-foreground">
          <p>
            Active location: {activeLocationId ?? "None"}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setSkip(Math.max(0, skip - limit))} disabled={skip === 0}>
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSkip(skip + limit)}
              disabled={!(locationsQuery.data?.has_more ?? false)}
            >
              Next
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
