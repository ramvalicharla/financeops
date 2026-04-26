"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createCostCentre,
  getCostCentreTree,
  listCostCentres,
  updateCostCentre,
  type CostCentreTreeNode,
} from "@/lib/api/locations"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"
import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"

type ExpandedMap = Record<string, boolean>

function TreeNode({
  node,
  expanded,
  onToggle,
}: {
  node: CostCentreTreeNode
  expanded: ExpandedMap
  onToggle: (id: string) => void
}) {
  const isOpen = expanded[node.id] ?? true
  const hasChildren = node.children.length > 0

  return (
    <li className="space-y-2">
      <div className="flex items-center gap-2 rounded-md border border-border bg-muted/20 px-3 py-2 text-sm">
        {hasChildren ? (
          <button
            type="button"
            className="rounded border border-border px-1 text-xs text-muted-foreground"
            onClick={() => onToggle(node.id)}
          >
            {isOpen ? "-" : "+"}
          </button>
        ) : (
          <span className="inline-block w-5" />
        )}
        <span className="font-mono text-xs text-muted-foreground">{node.cost_centre_code}</span>
        <span className="text-foreground">{node.cost_centre_name}</span>
        <span
          className={`ml-auto rounded-full px-2 py-1 text-xs ${
            node.is_active
              ? "bg-emerald-500/15 text-emerald-300"
              : "bg-rose-500/15 text-rose-300"
          }`}
        >
          {node.is_active ? "Active" : "Inactive"}
        </span>
      </div>
      {hasChildren && isOpen ? (
        <ul className="ml-6 space-y-2 border-l border-border pl-3">
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} expanded={expanded} onToggle={onToggle} />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

export default function CostCentresSettingsPage() {
  const queryClient = useQueryClient()
  const entityId = useWorkspaceStore((s) => s.entityId)
  const entityRoles = useTenantStore((state) => state.entity_roles)

  const [expanded, setExpanded] = useState<ExpandedMap>({})
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState("")
  const [editingCode, setEditingCode] = useState("")

  const [code, setCode] = useState("")
  const [name, setName] = useState("")
  const [parentId, setParentId] = useState("")
  const [fieldErrors, setFieldErrors] = useState<{
    entity?: string
    code?: string
    name?: string
  }>({})

  const flatQuery = useQuery({
    queryKey: queryKeys.settings.costCentresFlat(entityId),
    queryFn: () =>
      listCostCentres({
        entity_id: entityId ?? "",
        skip: 0,
        limit: 500,
      }),
    enabled: Boolean(entityId),
  })

  const treeQuery = useQuery({
    queryKey: queryKeys.settings.costCentresTree(entityId),
    queryFn: () => getCostCentreTree(entityId ?? ""),
    enabled: Boolean(entityId),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      createCostCentre({
        entity_id: entityId ?? "",
        parent_id: parentId || null,
        cost_centre_code: code,
        cost_centre_name: name,
      }),
    onSuccess: () => {
      setCode("")
      setName("")
      setParentId("")
      void queryClient.invalidateQueries({ queryKey: queryKeys.settings.costCentresFlat(entityId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.settings.costCentresTree(entityId) })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      updateCostCentre(id, payload),
    onSuccess: () => {
      setEditingId(null)
      setEditingCode("")
      setEditingName("")
      void queryClient.invalidateQueries({ queryKey: queryKeys.settings.costCentresFlat(entityId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.settings.costCentresTree(entityId) })
    },
  })

  const flatItems = useMemo(() => flatQuery.data?.items ?? [], [flatQuery.data])
  const roots = treeQuery.data ?? []

  const parentOptions = useMemo(
    () => flatItems.map((item) => ({ id: item.id, label: `${item.cost_centre_code} - ${item.cost_centre_name}` })),
    [flatItems],
  )

  const handleCreate = () => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!entityId) nextFieldErrors.entity = "Entity is required."
    if (!code.trim()) nextFieldErrors.code = "Cost centre code is required."
    if (!name.trim()) nextFieldErrors.name = "Cost centre name is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      return
    }
    setFieldErrors({})
    createMutation.mutate()
  }

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Cost Centres</h1>
        <p className="text-sm text-muted-foreground">
          Maintain department hierarchy for the selected entity.
        </p>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <FormField id="cc-entity" label="Entity" error={fieldErrors.entity} required>
            <select
              value={entityId ?? ""}
              onChange={(event) => useWorkspaceStore.getState().switchEntity(event.target.value || null)}
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
          <FormField id="cc-code" label="Cost centre code" error={fieldErrors.code} required>
            <Input value={code} onChange={(event) => setCode(event.target.value)} />
          </FormField>
          <FormField id="cc-name" label="Cost centre name" error={fieldErrors.name} required>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </FormField>
          <FormField id="cc-parent" label="Parent cost centre">
            <select
              value={parentId}
              onChange={(event) => setParentId(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="">No parent</option>
              {parentOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </FormField>
        </div>
        <div className="mt-4 flex justify-end">
          <Button onClick={handleCreate} disabled={!entityId || !code || !name || createMutation.isPending}>
            Add Cost Centre
          </Button>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium text-foreground">Flat List</h2>
        {flatQuery.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : flatQuery.error ? (
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load cost centres.</p>
        ) : (
          <div className="overflow-x-auto">
            <table aria-label="Cost centres" className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-2">Code</th>
                  <th scope="col" className="px-4 py-2">Name</th>
                  <th scope="col" className="px-4 py-2">Status</th>
                  <th scope="col" className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {flatItems.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                      {editingId === item.id ? (
                        <Input value={editingCode} onChange={(event) => setEditingCode(event.target.value)} />
                      ) : (
                        item.cost_centre_code
                      )}
                    </td>
                    <td className="px-4 py-2">
                      {editingId === item.id ? (
                        <Input value={editingName} onChange={(event) => setEditingName(event.target.value)} />
                      ) : (
                        item.cost_centre_name
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-1 text-xs ${
                          item.is_active
                            ? "bg-emerald-500/15 text-emerald-300"
                            : "bg-rose-500/15 text-rose-300"
                        }`}
                      >
                        {item.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {editingId === item.id ? (
                        <div className="inline-flex gap-2">
                          <Button
                            size="sm"
                            onClick={() =>
                              updateMutation.mutate({
                                id: item.id,
                                payload: {
                                  cost_centre_code: editingCode,
                                  cost_centre_name: editingName,
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
                              setEditingCode("")
                              setEditingName("")
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
                              setEditingId(item.id)
                              setEditingCode(item.cost_centre_code)
                              setEditingName(item.cost_centre_name)
                            }}
                          >
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              updateMutation.mutate({
                                id: item.id,
                                payload: { is_active: !item.is_active },
                              })
                            }
                          >
                            {item.is_active ? "Deactivate" : "Activate"}
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium text-foreground">Hierarchy</h2>
        {treeQuery.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-8 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : treeQuery.error ? (
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load hierarchy.</p>
        ) : !roots.length ? (
          <p className="text-sm text-muted-foreground">No cost centres yet.</p>
        ) : (
          <ul className="space-y-2">
            {roots.map((root) => (
              <TreeNode
                key={root.id}
                node={root}
                expanded={expanded}
                onToggle={(id) => setExpanded((prev) => ({ ...prev, [id]: !(prev[id] ?? true) }))}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
