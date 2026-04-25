"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import { getTenantCoaAccounts } from "@/lib/api/coa"
import { queryKeys } from "@/lib/query/keys"
import type { CreateJournalPayload } from "@/lib/api/accounting-journals"
import { createGovernedIntent, type JournalIntentPayload } from "@/lib/api/intents"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { canPerformAction, getPermissionDeniedMessage } from "@/lib/ui-access"
import { StateBadge } from "@/components/ui/StateBadge"
import { Button } from "@/components/ui/button"
import { z } from "zod"
import { toast } from "sonner"

type DraftLine = {
  tenant_coa_account_id: string
  tenant_coa_account_search: string
  debit: string
  credit: string
  memo: string
  transaction_currency: string
  fx_rate: string
}

const today = new Date().toISOString().slice(0, 10)

const asNumber = (value: string): number => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const journalSchema = z.object({
  org_entity_id: z.string().min(1, "Select an active entity before posting a journal."),
  journal_date: z.string().min(1, "Journal date is required"),
  reference: z.string().optional(),
  narration: z.string().optional(),
  lines: z.array(z.object({
    tenant_coa_account_id: z.string().min(1, "Account is required on all lines"),
    account_code: z.string().optional(),
    debit: z.string().refine(v => asNumber(v) >= 0, "Debit must be non-negative"),
    credit: z.string().refine(v => asNumber(v) >= 0, "Credit must be non-negative"),
    memo: z.string().optional(),
    transaction_currency: z.string().optional(),
    fx_rate: z.string().optional()
  })).min(2, "Journal needs at least two lines.")
}).superRefine((data, ctx) => {
  // Validate that lines are correctly populated
  data.lines.forEach((line, index) => {
    const debit = asNumber(line.debit)
    const credit = asNumber(line.credit)
    if (debit > 0 && credit > 0) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: `Line ${index + 1} cannot have both debit and credit`, path: ["lines", index] });
    }
    if (debit <= 0 && credit <= 0) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: `Line ${index + 1} must have a debit or credit`, path: ["lines", index] });
    }
  });
})

export default function NewJournalPage() {
  const router = useRouter()
  const { data: session } = useSession()
  const userRole = String((session?.user as { role?: string } | undefined)?.role ?? "")
  const canCreateJournal = canPerformAction("journal.create", userRole)
  const openIntentPanel = useControlPlaneStore((state) => state.openIntentPanel)
  const entityId = useWorkspaceStore((s) => s.entityId)
  const [journalDate, setJournalDate] = useState(today)
  const [reference, setReference] = useState("")
  const [narration, setNarration] = useState("")
  const [lines, setLines] = useState<DraftLine[]>([
    {
      tenant_coa_account_id: "",
      tenant_coa_account_search: "",
      debit: "",
      credit: "",
      memo: "",
      transaction_currency: "",
      fx_rate: "",
    },
    {
      tenant_coa_account_id: "",
      tenant_coa_account_search: "",
      debit: "",
      credit: "",
      memo: "",
      transaction_currency: "",
      fx_rate: "",
    },
  ])
  const [error, setError] = useState<string | null>(null)

  const accountsQuery = useQuery({
    queryKey: queryKeys.coa.tenantAccounts(),
    queryFn: getTenantCoaAccounts,
  })
  const accountChoices = useMemo(
    () =>
      (accountsQuery.data ?? []).map((account) => ({
        id: account.id,
        label: `${account.account_code} - ${account.display_name}`,
        code: account.account_code,
      })),
    [accountsQuery.data],
  )
  const accountById = useMemo(
    () => new Map(accountChoices.map((account) => [account.id, account])),
    [accountChoices],
  )
  const accountByLabel = useMemo(
    () => new Map(accountChoices.map((account) => [account.label, account.id])),
    [accountChoices],
  )
  const accountByCode = useMemo(
    () => new Map(accountChoices.map((account) => [account.code, account.id])),
    [accountChoices],
  )
  const hasAccounts = accountChoices.length > 0

  const totalDebit = useMemo(
    () => lines.reduce((acc, line) => acc + asNumber(line.debit), 0),
    [lines],
  )
  const totalCredit = useMemo(
    () => lines.reduce((acc, line) => acc + asNumber(line.credit), 0),
    [lines],
  )
  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.0001

  const createMutation = useMutation({
    mutationFn: createGovernedIntent,
    onSuccess: (result) => {
      toast.success("Journal draft successfully recorded!")
      openIntentPanel(result)
      router.push("/accounting/journals")
    },
    onError: (cause) => {
      toast.error(cause instanceof Error ? cause.message : "Failed to create journal")
    },
  })

  const addLine = (): void => {
    setLines((current) => [
      ...current,
      {
        tenant_coa_account_id: "",
        tenant_coa_account_search: "",
        debit: "",
        credit: "",
        memo: "",
        transaction_currency: "",
        fx_rate: "",
      },
    ])
  }

  const removeLine = (index: number): void => {
    setLines((current) => current.filter((_, rowIndex) => rowIndex !== index))
  }

  const updateLine = (index: number, patch: Partial<DraftLine>): void => {
    setLines((current) =>
      current.map((line, rowIndex) =>
        rowIndex === index ? { ...line, ...patch } : line,
      ),
    )
  }

  const resolveAccountId = (line: DraftLine): string | null => {
    const exactSearch = line.tenant_coa_account_search.trim()
    if (line.tenant_coa_account_id) {
      return line.tenant_coa_account_id
    }
    if (accountByLabel.has(exactSearch)) {
      return accountByLabel.get(exactSearch) ?? null
    }
    if (accountByCode.has(exactSearch)) {
      return accountByCode.get(exactSearch) ?? null
    }
    return null
  }

  const submit = (): void => {
    if (!entityId) {
      toast.error("Select an active entity before posting a journal.")
      return
    }
    if (!canCreateJournal) {
      toast.error(getPermissionDeniedMessage("journal.create"))
      return
    }
    if (!isBalanced) {
      toast.error("Total debit and total credit must match.")
      return
    }

    const resolvedLines = lines.map((line) => {
      const accountId = resolveAccountId(line)
      const account = accountId ? accountById.get(accountId) : null
      return {
        line,
        accountId,
        account,
      }
    })

    const rawData = {
      org_entity_id: entityId,
      journal_date: journalDate,
      reference: reference || undefined,
      narration: narration || undefined,
      lines: resolvedLines.map(({ line, accountId, account }) => ({
        tenant_coa_account_id: accountId ?? undefined,
        account_code: account?.code,
        debit: String(asNumber(line.debit)),
        credit: String(asNumber(line.credit)),
        memo: line.memo || undefined,
        transaction_currency: line.transaction_currency ? line.transaction_currency.toUpperCase() : undefined,
        fx_rate: line.fx_rate ? String(asNumber(line.fx_rate)) : undefined,
      }))
    }

    const parseResult = journalSchema.safeParse(rawData)
    
    if (!parseResult.success) {
      const errorStr = parseResult.error.issues.map(e => e.message).join(" • ")
      toast.error("Validation Failed: " + errorStr)
      return
    }

    const payload: JournalIntentPayload = {
      type: "CREATE_JOURNAL",
      data: {
        org_entity_id: entityId,
        journal_date: journalDate,
        reference: reference || undefined,
        narration: narration || undefined,
        lines: parseResult.data.lines,
      } as CreateJournalPayload,
    }

    createMutation.mutate(payload)
  }

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">New Journal</h1>
          <p className="text-sm text-muted-foreground">
            Create a balanced journal draft. Approve and post from Journals list.
          </p>
        </div>
        <Link href="/accounting/journals">
          <Button variant="outline">Back to Journals</Button>
        </Link>
      </header>

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Journal date</span>
          <input
            type="date"
            value={journalDate}
            onChange={(event) => setJournalDate(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Reference</span>
          <input
            type="text"
            value={reference}
            onChange={(event) => setReference(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            placeholder="Voucher / source ref"
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Narration</span>
          <input
            type="text"
            value={narration}
            onChange={(event) => setNarration(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            placeholder="Journal narration"
          />
        </label>
      </section>

      {accountsQuery.isError ? (
        <div className="rounded-xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm text-foreground">
          <p className="font-medium">COA accounts failed to load</p>
          <p className="mt-1 text-muted-foreground">
            {accountsQuery.error instanceof Error ? accountsQuery.error.message : "Unable to load chart of accounts."}
          </p>
        </div>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {!accountsQuery.isLoading && !accountsQuery.isError && !hasAccounts ? (
          <div className="p-6 text-sm text-muted-foreground">
            No chart of accounts is available yet. Upload or initialise it first, then return to create journals.
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-muted/30">
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2">Account</th>
                    <th className="px-4 py-2">Debit</th>
                    <th className="px-4 py-2">Credit</th>
                    <th className="px-4 py-2">Memo</th>
                    <th className="px-4 py-2">Txn Currency</th>
                    <th className="px-4 py-2">FX Rate</th>
                    <th className="px-4 py-2">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {lines.map((line, index) => (
                    <tr key={`line-${index}`}>
                      <td className="px-4 py-2">
                        <div className="space-y-2">
                          <input
                            list={`journal-account-options-${index}`}
                            value={line.tenant_coa_account_search}
                            onChange={(event) => {
                              const search = event.target.value
                              const exactMatch = accountByLabel.get(search) ?? accountByCode.get(search) ?? ""
                              updateLine(index, {
                                tenant_coa_account_search: search,
                                tenant_coa_account_id: exactMatch,
                              })
                            }}
                            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                            placeholder="Search account code or name"
                            autoComplete="off"
                          />
                          <datalist id={`journal-account-options-${index}`}>
                            {accountChoices.map((account) => (
                              <option key={account.id} value={account.label} />
                            ))}
                          </datalist>
                          <p className="text-xs text-muted-foreground">
                            Choose a COA suggestion to resolve the account automatically.
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="number"
                          step="0.0001"
                          min="0"
                          value={line.debit}
                          onChange={(event) =>
                            updateLine(index, { debit: event.target.value })
                          }
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="number"
                          step="0.0001"
                          min="0"
                          value={line.credit}
                          onChange={(event) =>
                            updateLine(index, { credit: event.target.value })
                          }
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={line.memo}
                          onChange={(event) =>
                            updateLine(index, { memo: event.target.value })
                          }
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          maxLength={3}
                          value={line.transaction_currency}
                          onChange={(event) =>
                            updateLine(index, { transaction_currency: event.target.value })
                          }
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                          placeholder="USD"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="number"
                          step="0.00000001"
                          min="0"
                          value={line.fx_rate}
                          onChange={(event) =>
                            updateLine(index, { fx_rate: event.target.value })
                          }
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                          placeholder="Spot rate"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => removeLine(index)}
                          disabled={lines.length <= 2}
                        >
                          Remove
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-4">
              <Button type="button" variant="outline" onClick={addLine}>
                Add Line
              </Button>
              <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                <span className="mr-2">Debit: {totalDebit.toFixed(2)}</span>
                <span className="mr-2">Credit: {totalCredit.toFixed(2)}</span>
                <StateBadge
                  status={isBalanced ? "success" : "failed"}
                  label={isBalanced ? "Balanced" : "Not balanced"}
                />
                {!canCreateJournal ? (
                  <StateBadge status="failed" label={getPermissionDeniedMessage("journal.create")} />
                ) : null}
              </div>
            </div>
          </>
        )}
      </section>



      <div className="flex justify-end">
        <Button
          type="button"
          onClick={submit}
          disabled={createMutation.isPending || accountsQuery.isLoading || !hasAccounts || !canCreateJournal}
          title={!canCreateJournal ? getPermissionDeniedMessage("journal.create") : undefined}
        >
          {createMutation.isPending ? "Creating..." : "Create Draft"}
        </Button>
      </div>
    </div>
  )
}
