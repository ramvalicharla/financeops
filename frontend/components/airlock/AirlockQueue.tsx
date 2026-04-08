"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { listAirlockItems } from "@/lib/api/control-plane"
import { useTenantStore } from "@/lib/store/tenant"

export function AirlockQueue() {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const airlockQuery = useQuery({
    queryKey: ["control-plane-airlock", activeEntityId],
    queryFn: async () => listAirlockItems({ entity_id: activeEntityId ?? undefined, limit: 50 }),
  })

  if (airlockQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading airlock queue...</p>
  }

  if (airlockQuery.error) {
    return <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load airlock queue.</p>
  }

  if (!(airlockQuery.data?.length ?? 0)) {
    return <p className="text-sm text-muted-foreground">No airlock items in the current scope.</p>
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-muted/30">
          <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-2">Airlock Item</th>
            <th className="px-4 py-2">Source</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Received</th>
            <th className="px-4 py-2">Entity</th>
            <th className="px-4 py-2">Review</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {(airlockQuery.data ?? []).map((item) => (
            <tr key={item.airlock_item_id}>
              <td className="px-4 py-2 font-mono text-xs text-foreground">{item.airlock_item_id}</td>
              <td className="px-4 py-2 text-foreground">{item.source_type}</td>
              <td className="px-4 py-2 text-foreground">{item.status}</td>
              <td className="px-4 py-2 text-muted-foreground">{item.submitted_at ?? "-"}</td>
              <td className="px-4 py-2 text-muted-foreground">{item.entity_id ?? "-"}</td>
              <td className="px-4 py-2">
                <Link className="text-sm text-foreground underline" href={`/settings/airlock/${item.airlock_item_id}`}>
                  Open
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
