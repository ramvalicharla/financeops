"use client"

import type { MADDItem, MADDTrackerSummary } from "@/lib/types/ma"

interface DDTrackerProps {
  summary: MADDTrackerSummary
  items: MADDItem[]
  onStatusChange: (itemId: string, status: string) => Promise<void>
}

export function DDTracker({ summary, items, onStatusChange }: DDTrackerProps) {
  return (
    <section className="space-y-4">
      <article className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-base font-semibold text-foreground">DD Tracker</h3>
        <p className="mt-1 text-sm text-muted-foreground">Completion: {summary.completion_pct}%</p>
        <div className="mt-3 h-2 w-full rounded-full bg-background">
          <div
            className="h-2 rounded-full bg-[hsl(var(--brand-primary))]"
            style={{ width: `${Math.max(0, Math.min(100, Number(summary.completion_pct)))}%` }}
          />
        </div>
      </article>

      <article className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h4 className="text-sm font-semibold text-foreground">Items</h4>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-background/80">
              <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                <th className="px-4 py-2">Category</th>
                <th className="px-4 py-2">Item</th>
                <th className="px-4 py-2">Priority</th>
                <th className="px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`border-t border-border/60 ${
                    item.status === "flagged" ? "bg-[hsl(var(--brand-danger)/0.10)]" : ""
                  }`}
                >
                  <td className="px-4 py-3 text-muted-foreground">{item.category}</td>
                  <td className="px-4 py-3 text-foreground">{item.item_name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{item.priority}</td>
                  <td className="px-4 py-3">
                    <select
                      value={item.status}
                      onChange={(event) => {
                        void onStatusChange(item.id, event.target.value)
                      }}
                      className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground"
                    >
                      <option value="open">open</option>
                      <option value="in_progress">in_progress</option>
                      <option value="completed">completed</option>
                      <option value="flagged">flagged</option>
                      <option value="waived">waived</option>
                    </select>
                  </td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-muted-foreground" colSpan={4}>
                    No DD items.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  )
}
