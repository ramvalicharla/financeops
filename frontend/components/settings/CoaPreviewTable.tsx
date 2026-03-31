"use client"

import type { CoaLedgerAccount, CoaUploadBatch } from "@/lib/api/coa"

interface CoaPreviewTableProps {
  accounts: CoaLedgerAccount[]
  batches: CoaUploadBatch[]
}

export function CoaPreviewTable({ accounts, batches }: CoaPreviewTableProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground">CoA Preview</h2>
        <p className="mt-1 text-sm text-muted-foreground">Resolved accounts (tenant override fallback applied)</p>
        <div className="mt-3 max-h-[420px] overflow-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Version</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {accounts.slice(0, 150).map((account) => (
                <tr key={account.id}>
                  <td className="px-3 py-2 font-mono text-xs">{account.code}</td>
                  <td className="px-3 py-2">{account.name}</td>
                  <td className="px-3 py-2 text-xs">{account.source_type}</td>
                  <td className="px-3 py-2 text-xs">v{account.version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground">Version History</h2>
        <p className="mt-1 text-sm text-muted-foreground">Recent upload batches</p>
        <div className="mt-3 max-h-[420px] overflow-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-3 py-2">File</th>
                <th className="px-3 py-2">Mode</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {batches.map((batch) => (
                <tr key={batch.id}>
                  <td className="px-3 py-2">{batch.file_name}</td>
                  <td className="px-3 py-2 text-xs">{batch.upload_mode}</td>
                  <td className="px-3 py-2 text-xs">{batch.upload_status}</td>
                  <td className="px-3 py-2 text-xs">{new Date(batch.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
