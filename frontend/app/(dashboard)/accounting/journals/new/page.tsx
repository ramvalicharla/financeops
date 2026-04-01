"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { useMutation, useQuery } from "@tanstack/react-query"
import { createJournal } from "@/lib/api/accounting-journals"
import { getTenantCoaAccounts } from "@/lib/api/coa"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

type DraftLine = {
  tenant_coa_account_id: string
  debit: string
  credit: string
  memo: string
}

const today = new Date().toISOString().slice(0, 10)

const asNumber = (value: string): number => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export default function NewJournalPage() {
  const router = useRouter()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const [journalDate, setJournalDate] = useState(today)
  const [reference, setReference] = useState("")
  const [narration, setNarration] = useState("")
  const [lines, setLines] = useState<DraftLine[]>([
    { tenant_coa_account_id: "", debit: "", credit: "", memo: "" },
    { tenant_coa_account_id: "", debit: "", credit: "", memo: "" },
  ])
  const [error, setError] = useState<string | null>(null)

  const accountsQuery = useQuery({
    queryKey: ["tenant-coa-accounts"],
    queryFn: getTenantCoaAccounts,
  })
  const accountMap = useMemo(
    () =>
      new Map((accountsQuery.data ?? []).map((account) => [account.id, account])),
    [accountsQuery.data],
  )

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
    mutationFn: createJournal,
    onSuccess: () => {
      router.push("/accounting/journals")
    },
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Failed to create journal")
    },
  })

  const addLine = (): void => {
    setLines((current) => [
      ...current,
      { tenant_coa_account_id: "", debit: "", credit: "", memo: "" },
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

  const submit = async (): Promise<void> => {
    setError(null)
    if (!activeEntityId) {
      setError("Select an active entity before posting a journal.")
      return
    }
    if (lines.length < 2) {
      setError("Journal needs at least two lines.")
      return
    }
    if (!isBalanced) {
      setError("Total debit and total credit must match.")
      return
    }

    const hasInvalidLine = lines.some((line) => {
      const debit = asNumber(line.debit)
      const credit = asNumber(line.credit)
      return (
        !line.tenant_coa_account_id ||
        (debit > 0 && credit > 0) ||
        (debit <= 0 && credit <= 0) ||
        debit < 0 ||
        credit < 0
      )
    })
    if (hasInvalidLine) {
      setError("Each line must have one account and exactly one of debit or credit.")
      return
    }

    await createMutation.mutateAsync({
      org_entity_id: activeEntityId,
      journal_date: journalDate,
      reference: reference || undefined,
      narration: narration || undefined,
      lines: lines.map((line) => {
        const account = accountMap.get(line.tenant_coa_account_id)
        return {
          tenant_coa_account_id: line.tenant_coa_account_id,
          account_code: account?.account_code,
          debit: String(asNumber(line.debit)),
          credit: String(asNumber(line.credit)),
          memo: line.memo || undefined,
        }
      }),
    })
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

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Account</th>
                <th className="px-4 py-2">Debit</th>
                <th className="px-4 py-2">Credit</th>
                <th className="px-4 py-2">Memo</th>
                <th className="px-4 py-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {lines.map((line, index) => (
                <tr key={`line-${index}`}>
                  <td className="px-4 py-2">
                    <select
                      value={line.tenant_coa_account_id}
                      onChange={(event) =>
                        updateLine(index, {
                          tenant_coa_account_id: event.target.value,
                        })
                      }
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                    >
                      <option value="">Select account</option>
                      {(accountsQuery.data ?? []).map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.account_code} - {account.display_name}
                        </option>
                      ))}
                    </select>
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
          <div className="text-sm text-muted-foreground">
            <span className="mr-4">Debit: {totalDebit.toFixed(2)}</span>
            <span className="mr-4">Credit: {totalCredit.toFixed(2)}</span>
            <span className={isBalanced ? "text-emerald-300" : "text-rose-300"}>
              {isBalanced ? "Balanced" : "Not Balanced"}
            </span>
          </div>
        </div>
      </section>

      {error ? (
        <div className="rounded-md border border-rose-400/40 bg-rose-500/10 p-3 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button
          type="button"
          onClick={() => void submit()}
          disabled={createMutation.isPending || accountsQuery.isLoading}
        >
          {createMutation.isPending ? "Creating..." : "Create Draft"}
        </Button>
      </div>
    </div>
  )
}
