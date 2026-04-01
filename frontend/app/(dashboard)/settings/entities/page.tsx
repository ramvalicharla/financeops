"use client"

import { useEffect, useState } from "react"
import apiClient from "@/lib/api/client"

interface Entity {
  id: string
  entity_code: string
  entity_name: string
  organisation_id: string
}

interface EntityForm {
  entity_code: string
  entity_name: string
  organisation_id: string
  group_id: string
  base_currency: string
  country_code: string
}

export default function EntitiesSettingsPage() {
  const [entities, setEntities] = useState<Entity[]>([])
  const [form, setForm] = useState<EntityForm>({
    entity_code: "",
    entity_name: "",
    organisation_id: "",
    group_id: "",
    base_currency: "INR",
    country_code: "IN",
  })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const loadEntities = async (): Promise<void> => {
    const response = await apiClient.get<Entity[]>("/api/v1/platform/entities")
    setEntities(response.data)
  }

  useEffect(() => {
    void loadEntities()
  }, [])

  const createEntity = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      await apiClient.post("/api/v1/platform/org/entities", {
        ...form,
        group_id: form.group_id || null,
      })
      setLoading(false)
      await loadEntities()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to create entity")
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold text-white">Entities</h1>
      <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-100">Add Entity</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Entity code" value={form.entity_code} onChange={(e) => setForm((f) => ({ ...f, entity_code: e.target.value }))} />
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Entity name" value={form.entity_name} onChange={(e) => setForm((f) => ({ ...f, entity_name: e.target.value }))} />
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Organisation ID" value={form.organisation_id} onChange={(e) => setForm((f) => ({ ...f, organisation_id: e.target.value }))} />
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Group ID (optional)" value={form.group_id} onChange={(e) => setForm((f) => ({ ...f, group_id: e.target.value }))} />
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Base currency" value={form.base_currency} onChange={(e) => setForm((f) => ({ ...f, base_currency: e.target.value }))} />
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Country code" value={form.country_code} onChange={(e) => setForm((f) => ({ ...f, country_code: e.target.value }))} />
        </div>
        {error ? <p className="mt-2 text-sm text-red-400">{error}</p> : null}
        <button onClick={createEntity} disabled={loading} className="mt-3 rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
          {loading ? "Creating..." : "Add Entity"}
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {entities.map((entity) => (
          <div key={entity.id} className="rounded-lg border border-gray-800 bg-gray-900/40 p-3">
            <p className="text-sm font-medium text-white">{entity.entity_name}</p>
            <p className="text-xs text-gray-400">{entity.entity_code}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
