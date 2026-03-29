"use client"

import { useState } from "react"

interface GroupForm {
  group_code: string
  group_name: string
  organisation_id: string
}

export default function GroupsSettingsPage() {
  const [form, setForm] = useState<GroupForm>({
    group_code: "",
    group_name: "",
    organisation_id: "",
  })
  const [items, setItems] = useState<Array<{ id: string; group_code: string; group_name: string }>>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const createGroup = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    const response = await fetch("/api/v1/platform/org/groups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    })
    const payload = (await response.json()) as { data?: { id?: string; group_code?: string }; detail?: string }
    if (!response.ok) {
      setError(payload.detail ?? "Failed to create group")
      setLoading(false)
      return
    }
    const createdId = payload.data?.id
    const createdCode = payload.data?.group_code
    if (createdId && createdCode) {
      setItems((prev) => [{ id: createdId, group_code: createdCode, group_name: form.group_name }, ...prev])
    }
    setLoading(false)
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold text-white">Groups & Entities</h1>
      <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-100">Create Group</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Group code" value={form.group_code} onChange={(e) => setForm((f) => ({ ...f, group_code: e.target.value }))} />
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Group name" value={form.group_name} onChange={(e) => setForm((f) => ({ ...f, group_name: e.target.value }))} />
          <input className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white" placeholder="Organisation ID" value={form.organisation_id} onChange={(e) => setForm((f) => ({ ...f, organisation_id: e.target.value }))} />
        </div>
        {error ? <p className="mt-2 text-sm text-red-400">{error}</p> : null}
        <button onClick={createGroup} disabled={loading} className="mt-3 rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
          {loading ? "Creating..." : "Create Group"}
        </button>
      </div>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.id} className="rounded-lg border border-gray-800 bg-gray-900/40 p-3">
            <p className="text-sm font-medium text-white">{item.group_name}</p>
            <p className="text-xs text-gray-400">{item.group_code}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
