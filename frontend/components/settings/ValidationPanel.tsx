"use client"

import type { CoaUploadError, CoaUploadResult, CoaValidationResult } from "@/lib/api/coa"

interface ValidationPanelProps {
  result: CoaValidationResult | CoaUploadResult | null
}

const renderErrors = (errors: CoaUploadError[]) => {
  if (!errors.length) {
    return <p className="text-sm text-emerald-400">No validation errors found.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table aria-label="Validation results" className="min-w-full divide-y divide-border text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th scope="col" className="px-3 py-2">Row</th>
            <th scope="col" className="px-3 py-2">Errors</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {errors.map((error) => (
            <tr key={`${error.row_number}-${error.errors.join("|")}`}>
              <td className="px-3 py-2 font-mono text-xs">{error.row_number}</td>
              <td className="px-3 py-2 text-rose-300">{error.errors.join("; ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ValidationPanel({ result }: ValidationPanelProps) {
  if (!result) {
    return null
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground">Validation</h2>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <div className="rounded-md border border-border/70 bg-background p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Total Rows</p>
          <p className="text-xl font-semibold text-foreground">{result.total_rows}</p>
        </div>
        <div className="rounded-md border border-border/70 bg-background p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Valid</p>
          <p className="text-xl font-semibold text-emerald-400">{result.valid_rows}</p>
        </div>
        <div className="rounded-md border border-border/70 bg-background p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Invalid</p>
          <p className="text-xl font-semibold text-rose-400">{result.invalid_rows}</p>
        </div>
      </div>
      <div className="mt-4">{renderErrors(result.errors)}</div>
    </section>
  )
}
