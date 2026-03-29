"use client"

export type GAAPToggleProps = {
  frameworks: string[]
  active: string
  onSelect: (framework: string) => void
  available: string[]
  onCompute: (framework: string) => Promise<void>
  loadingFramework: string | null
}

export function GAAPToggle({
  frameworks,
  active,
  onSelect,
  available,
  onCompute,
  loadingFramework,
}: GAAPToggleProps) {
  return (
    <div className="inline-flex flex-wrap items-center gap-2 rounded-md border border-border bg-card p-1">
      {frameworks.map((framework) => (
        <div key={framework} className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onSelect(framework)}
            className={`rounded px-3 py-1.5 text-xs ${
              framework === active
                ? "bg-[hsl(var(--brand-primary)/0.2)] text-foreground"
                : "text-muted-foreground"
            }`}
          >
            {framework}
          </button>
          {available.includes(framework) ? null : (
            <button
              type="button"
              onClick={() => void onCompute(framework)}
              className="rounded border border-border px-2 py-1 text-[10px] text-foreground"
              disabled={loadingFramework === framework}
            >
              {loadingFramework === framework ? "Computing..." : "Compute"}
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
