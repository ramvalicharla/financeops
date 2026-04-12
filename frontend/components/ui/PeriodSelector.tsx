"use client"

import { type ChangeEvent, type ReactNode, useId } from "react"

import { cn } from "@/lib/utils"

export interface PeriodSelectorOption {
  value: string
  label: string
  hint?: string
  disabled?: boolean
}

export interface PeriodSelectorProps {
  value: string
  onChange: (value: string) => void
  options: PeriodSelectorOption[]
  label?: string
  hint?: string
  className?: string
  disabled?: boolean
  leading?: ReactNode
  placeholder?: string
}

/**
 * Generic accounting period selector.
 * Keep the options backend- or state-derived from the calling feature.
 */
export function PeriodSelector({
  value,
  onChange,
  options,
  label = "Period",
  hint,
  className,
  disabled = false,
  leading,
  placeholder = "Select period",
}: PeriodSelectorProps) {
  const id = useId()

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onChange(event.target.value)
  }

  return (
    <label className={cn("flex min-w-0 flex-col gap-2", className)} htmlFor={id}>
      <span className="text-sm font-medium text-foreground">{label}</span>
      <div className="flex items-center gap-2">
        {leading ? <span className="shrink-0">{leading}</span> : null}
        <select
          id={id}
          aria-label={label}
          className={cn(
            "h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50",
          )}
          disabled={disabled}
          onChange={handleChange}
          value={value}
        >
          {!value ? <option value="">{placeholder}</option> : null}
          {options.map((option) => (
            <option key={option.value} disabled={option.disabled} value={option.value}>
              {option.label}
              {option.hint ? ` - ${option.hint}` : ""}
            </option>
          ))}
        </select>
      </div>
      {hint ? <p className="text-sm text-muted-foreground">{hint}</p> : null}
    </label>
  )
}
