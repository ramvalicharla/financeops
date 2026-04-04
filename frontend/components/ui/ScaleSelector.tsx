"use client"

import { SCALE_OPTIONS, type DisplayScale } from "@/lib/config/tokens"

interface ScaleSelectorProps {
  value: DisplayScale
  onChange: (scale: DisplayScale) => void
  size?: "sm" | "md"
  showGroups?: boolean
}

const buttonClassBySize: Record<"sm" | "md", string> = {
  sm: "px-2 py-1 text-xs",
  md: "px-3 py-1.5 text-sm",
}

const shortLabel = (scale: DisplayScale): string => {
  switch (scale) {
    case "INR":
      return "INR"
    case "LAKHS":
      return "L"
    case "CRORES":
      return "Cr"
    case "THOUSANDS":
      return "K"
    case "MILLIONS":
      return "M"
    case "BILLIONS":
      return "B"
  }
}

export function ScaleSelector({
  value,
  onChange,
  size = "sm",
  showGroups = false,
}: ScaleSelectorProps) {
  if (showGroups) {
    const indian = SCALE_OPTIONS.filter((opt) => opt.group === "Indian")
    const international = SCALE_OPTIONS.filter(
      (opt) => opt.group === "International",
    )
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">View in</span>
        <select
          value={value}
          onChange={(event) => onChange(event.target.value as DisplayScale)}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground"
        >
          <optgroup label="Indian">
            {indian.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </optgroup>
          <optgroup label="International">
            {international.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </optgroup>
        </select>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1">
      <span className="mr-1 text-xs text-muted-foreground">View in</span>
      <div className="flex overflow-hidden rounded-lg border border-border">
        {SCALE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className={[
              buttonClassBySize[size],
              "font-medium transition-colors",
              value === opt.value
                ? "bg-blue-600 text-white"
                : "bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
            ].join(" ")}
            title={opt.label}
            type="button"
          >
            {shortLabel(opt.value)}
          </button>
        ))}
      </div>
    </div>
  )
}
