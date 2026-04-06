"use client"

import { cn } from "@/lib/utils"

export function ToggleSwitch({
  checked,
  onChange,
  disabled = false,
  onLabel = "On",
  offLabel = "Off",
  title,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  onLabel?: string
  offLabel?: string
  title?: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      title={title}
      onClick={() => onChange(!checked)}
      className={cn(
        "inline-flex min-w-16 items-center justify-center rounded-full border px-2 py-1 text-xs transition",
        checked
          ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-200"
          : "border-border bg-background text-muted-foreground",
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
      )}
    >
      {checked ? onLabel : offLabel}
    </button>
  )
}
