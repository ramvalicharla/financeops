"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  addTenantCustomAccount,
  getCoaTemplates,
  getTemplateHierarchy,
  getTenantCoaAccounts,
  initialiseTenantCoa,
  type CoaHierarchyResponse,
  type TenantCoaAccount,
  updateTenantAccount,
} from "@/lib/api/coa"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const DEFAULT_TEMPLATE_CODE = "SOFTWARE_SAAS"

const buildPathMap = (
  hierarchy: CoaHierarchyResponse | undefined,
  gaapFilter: string,
): Record<string, string> => {
  if (!hierarchy) {
    return {}
  }
  const map: Record<string, string> = {}
  for (const classification of hierarchy.classifications) {
    for (const schedule of classification.schedules) {
      if (gaapFilter && schedule.gaap !== gaapFilter) {
        continue
      }
      for (const lineItem of schedule.line_items) {
        for (const subline of lineItem.sublines) {
          for (const group of subline.account_groups) {
            for (const subgroup of group.account_subgroups) {
              for (const ledger of subgroup.ledger_accounts) {
                map[ledger.code] = [
                  classification.name,
                  schedule.name,
                  lineItem.name,
                  subline.name,
                ].join(" / ")
              }
            }
          }
        }
      }
    }
  }
  return map
}

const groupByClassification = (accounts: TenantCoaAccount[]): Record<string, TenantCoaAccount[]> => {
  const grouped: Record<string, TenantCoaAccount[]> = {}
  for (const account of accounts) {
    const key = account.bs_pl_flag ?? "UNCLASSIFIED"
    if (!grouped[key]) {
      grouped[key] = []
    }
    grouped[key].push(account)
  }
  return grouped
}

export default function ChartOfAccountsSettingsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [gaap, setGaap] = useState("INDAS")
  const [classificationFilter, setClassificationFilter] = useState("ALL")
  const [activeOnly, setActiveOnly] = useState(false)
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({})
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState("")
  const [customModalOpen, setCustomModalOpen] = useState(false)
  const [customCode, setCustomCode] = useState("")
  const [customName, setCustomName] = useState("")
  const [parentSubgroupId, setParentSubgroupId] = useState<string>("")

  const templatesQuery = useQuery({
    queryKey: ["coa-templates"],
    queryFn: getCoaTemplates,
  })

  const templateId = useMemo(() => {
    return (
      templatesQuery.data?.find((template) => template.code === DEFAULT_TEMPLATE_CODE)?.id ??
      templatesQuery.data?.[0]?.id ??
      null
    )
  }, [templatesQuery.data])

  const hierarchyQuery = useQuery({
    queryKey: ["coa-hierarchy", templateId, gaap],
    queryFn: () => getTemplateHierarchy(templateId ?? ""),
    enabled: Boolean(templateId),
  })

  const tenantAccountsQuery = useQuery({
    queryKey: ["tenant-coa-accounts"],
    queryFn: getTenantCoaAccounts,
  })

  const initialiseMutation = useMutation({
    mutationFn: (id: string) => initialiseTenantCoa(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tenant-coa-accounts"] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      accountId,
      payload,
    }: {
      accountId: string
      payload: { display_name?: string; is_active?: boolean }
    }) => updateTenantAccount(accountId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tenant-coa-accounts"] })
    },
  })

  const addCustomMutation = useMutation({
    mutationFn: () =>
      addTenantCustomAccount({
        parent_subgroup_id: parentSubgroupId,
        account_code: customCode,
        display_name: customName,
      }),
    onSuccess: () => {
      setCustomModalOpen(false)
      setCustomCode("")
      setCustomName("")
      void queryClient.invalidateQueries({ queryKey: ["tenant-coa-accounts"] })
    },
  })

  const hierarchyPathMap = useMemo(
    () => buildPathMap(hierarchyQuery.data, gaap),
    [hierarchyQuery.data, gaap],
  )

  const filteredAccounts = useMemo(() => {
    const source = tenantAccountsQuery.data ?? []
    return source.filter((account) => {
      if (activeOnly && !account.is_active) {
        return false
      }
      if (classificationFilter !== "ALL" && account.bs_pl_flag !== classificationFilter) {
        return false
      }
      if (!search.trim()) {
        return true
      }
      const q = search.trim().toLowerCase()
      return (
        account.account_code.toLowerCase().includes(q) ||
        account.display_name.toLowerCase().includes(q) ||
        (account.platform_account_name ?? "").toLowerCase().includes(q)
      )
    })
  }, [activeOnly, classificationFilter, search, tenantAccountsQuery.data])

  const groupedAccounts = useMemo(
    () => groupByClassification(filteredAccounts),
    [filteredAccounts],
  )

  const subgroupOptions = useMemo(() => {
    const unique = new Map<string, string>()
    for (const account of tenantAccountsQuery.data ?? []) {
      if (account.parent_subgroup_id) {
        unique.set(account.parent_subgroup_id, account.parent_subgroup_id)
      }
    }
    return Array.from(unique.entries()).map(([value]) => ({ value, label: value }))
  }, [tenantAccountsQuery.data])

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Chart of Accounts</h1>
          <p className="text-sm text-muted-foreground">
            Manage tenant-level account labels, activation, and custom accounts.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setCustomModalOpen(true)}
            disabled={!tenantAccountsQuery.data?.length}
          >
            Add Custom Account
          </Button>
          <Button
            onClick={() => templateId && initialiseMutation.mutate(templateId)}
            disabled={!templateId || initialiseMutation.isPending}
          >
            Initialise CoA
          </Button>
        </div>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-5">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by code or name"
          />
          <select
            value={classificationFilter}
            onChange={(event) => setClassificationFilter(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="ALL">All classifications</option>
            <option value="ASSET">Asset</option>
            <option value="LIABILITY">Liability</option>
            <option value="EQUITY">Equity</option>
            <option value="REVENUE">Revenue</option>
            <option value="EXPENSE">Expense</option>
            <option value="OCI">OCI</option>
            <option value="UNCLASSIFIED">Unclassified</option>
          </select>
          <select
            value={gaap}
            onChange={(event) => setGaap(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="INDAS">IndAS</option>
            <option value="IFRS">IFRS</option>
            <option value="MANAGEMENT">Management</option>
          </select>
          <label className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
            <input
              checked={activeOnly}
              onChange={(event) => setActiveOnly(event.target.checked)}
              type="checkbox"
            />
            Active only
          </label>
        </div>
      </section>

      <section className="space-y-3">
        {Object.entries(groupedAccounts).map(([classification, accounts]) => {
          const collapsed = collapsedSections[classification] ?? false
          return (
            <article key={classification} className="overflow-hidden rounded-xl border border-border bg-card">
              <button
                type="button"
                onClick={() =>
                  setCollapsedSections((prev) => ({
                    ...prev,
                    [classification]: !collapsed,
                  }))
                }
                className="flex w-full items-center justify-between bg-muted/30 px-4 py-3 text-left"
              >
                <span className="text-sm font-medium text-foreground">
                  {classification} ({accounts.length})
                </span>
                <span className="text-xs text-muted-foreground">{collapsed ? "Expand" : "Collapse"}</span>
              </button>
              {!collapsed ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-border text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="px-4 py-2">Code</th>
                        <th className="px-4 py-2">Display Name</th>
                        <th className="px-4 py-2">FS Path</th>
                        <th className="px-4 py-2">Status</th>
                        <th className="px-4 py-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {accounts.map((account) => {
                        const isEditing = editingId === account.id
                        return (
                          <tr key={account.id}>
                            <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                              {account.account_code}
                            </td>
                            <td className="px-4 py-2">
                              {isEditing ? (
                                <Input
                                  value={editingName}
                                  onChange={(event) => setEditingName(event.target.value)}
                                />
                              ) : (
                                account.display_name
                              )}
                            </td>
                            <td className="px-4 py-2 text-xs text-muted-foreground">
                              {account.platform_account_code
                                ? hierarchyPathMap[account.platform_account_code] ?? "No FS path"
                                : "Custom account"}
                            </td>
                            <td className="px-4 py-2">
                              <span
                                className={`rounded-full px-2 py-1 text-xs ${
                                  account.is_active
                                    ? "bg-emerald-500/15 text-emerald-300"
                                    : "bg-rose-500/15 text-rose-300"
                                }`}
                              >
                                {account.is_active ? "Active" : "Inactive"}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-right">
                              {isEditing ? (
                                <div className="inline-flex gap-2">
                                  <Button
                                    size="sm"
                                    onClick={() => {
                                      updateMutation.mutate({
                                        accountId: account.id,
                                        payload: { display_name: editingName },
                                      })
                                      setEditingId(null)
                                      setEditingName("")
                                    }}
                                  >
                                    Save
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      setEditingId(null)
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
                                      setEditingId(account.id)
                                      setEditingName(account.display_name)
                                    }}
                                  >
                                    Rename
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                      updateMutation.mutate({
                                        accountId: account.id,
                                        payload: { is_active: !account.is_active },
                                      })
                                    }
                                  >
                                    {account.is_active ? "Deactivate" : "Activate"}
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
              ) : null}
            </article>
          )
        })}
      </section>

      {customModalOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-lg rounded-xl border border-border bg-card p-5">
            <h2 className="text-lg font-semibold text-foreground">Add Custom Account</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Add a tenant-specific account under a subgroup.
            </p>
            <div className="mt-4 space-y-3">
              <Input
                value={customCode}
                onChange={(event) => setCustomCode(event.target.value)}
                placeholder="Account code"
              />
              <Input
                value={customName}
                onChange={(event) => setCustomName(event.target.value)}
                placeholder="Display name"
              />
              <select
                value={parentSubgroupId}
                onChange={(event) => setParentSubgroupId(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="">Select parent subgroup</option>
                {subgroupOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCustomModalOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => addCustomMutation.mutate()}
                disabled={!customCode || !customName || !parentSubgroupId || addCustomMutation.isPending}
              >
                Create Account
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
