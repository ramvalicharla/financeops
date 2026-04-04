"use client"

import {
  CONNECTORS,
  type ConnectorDefinition,
} from "@/lib/config/connectors"
import { cn } from "@/lib/utils"
import type { ConnectorType } from "@/types/sync"

interface ConnectorGridProps {
  selectedConnectorId: ConnectorType
  onSelect: (connectorId: ConnectorType) => void
}

export function ConnectorGrid({
  selectedConnectorId,
  onSelect,
}: ConnectorGridProps) {
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">Choose connector</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {CONNECTORS.map((connector: ConnectorDefinition) => {
          const Icon = connector.icon
          const selected = selectedConnectorId === connector.id

          return (
            <button
              key={connector.id}
              className={cn(
                "rounded-lg border p-4 text-left transition",
                selected
                  ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.1)]"
                  : "border-border hover:border-[hsl(var(--brand-primary)/0.5)]",
              )}
              onClick={() => onSelect(connector.id)}
              type="button"
            >
              <Icon className="mb-2 h-5 w-5 text-foreground" />
              <p className="font-medium text-foreground">{connector.name}</p>
              <p className="text-xs text-muted-foreground">{connector.description}</p>
            </button>
          )
        })}
      </div>
    </section>
  )
}
