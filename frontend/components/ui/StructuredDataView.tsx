"use client"

import { cn } from "@/lib/utils"

interface StructuredDataViewProps {
  data: unknown
  emptyMessage?: string
  className?: string
  compact?: boolean
  maxDepth?: number
}

const humanizeKey = (value: string): string =>
  value
    .replace(/_/g, " ")
    .replace(/\./g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())

const summarizeValue = (value: unknown): string => {
  if (value === null) return "None"
  if (value === undefined) return "Unavailable"
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (typeof value === "string") return value || "Empty"
  if (typeof value === "number" || typeof value === "bigint") return String(value)
  if (Array.isArray(value)) return `${value.length} item${value.length === 1 ? "" : "s"}`
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>)
    return keys.length ? `${keys.length} field${keys.length === 1 ? "" : "s"}` : "Empty object"
  }
  return String(value)
}

const isPrimitive = (value: unknown): value is string | number | boolean | null | undefined =>
  value == null || ["string", "number", "boolean"].includes(typeof value)

function PrimitiveValue({ value }: { value: unknown }) {
  return <span className="break-words text-sm text-foreground">{summarizeValue(value)}</span>
}

function ArrayValue({
  value,
  depth,
  compact,
  maxDepth,
}: {
  value: unknown[]
  depth: number
  compact: boolean
  maxDepth: number
}) {
  if (!value.length) {
    return <p className="text-sm text-muted-foreground">No items</p>
  }

  if (depth >= maxDepth) {
    return <PrimitiveValue value={value} />
  }

  return (
    <div className={cn("space-y-2", compact && "space-y-1")}>
      {value.map((item, index) => (
        <div
          key={index}
          className={cn(
            "rounded-lg border border-border bg-background px-3 py-2",
            compact && "px-2 py-1.5",
          )}
        >
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Item {index + 1}</p>
          <div className="mt-1">
            <StructuredDataNode value={item} depth={depth + 1} compact={compact} maxDepth={maxDepth} />
          </div>
        </div>
      ))}
    </div>
  )
}

function ObjectValue({
  value,
  depth,
  compact,
  maxDepth,
}: {
  value: Record<string, unknown>
  depth: number
  compact: boolean
  maxDepth: number
}) {
  const entries = Object.entries(value)

  if (!entries.length) {
    return <p className="text-sm text-muted-foreground">No fields</p>
  }

  if (depth >= maxDepth) {
    return <PrimitiveValue value={value} />
  }

  return (
    <div className={cn("grid gap-2", compact ? "grid-cols-1" : "md:grid-cols-2")}>
      {entries.map(([key, nestedValue]) => (
        <div
          key={key}
          className={cn(
            "rounded-lg border border-border bg-background px-3 py-2",
            compact && "px-2 py-1.5",
          )}
        >
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{humanizeKey(key)}</p>
          <div className="mt-1">
            <StructuredDataNode
              value={nestedValue}
              depth={depth + 1}
              compact={compact}
              maxDepth={maxDepth}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function StructuredDataNode({
  value,
  depth,
  compact,
  maxDepth,
}: {
  value: unknown
  depth: number
  compact: boolean
  maxDepth: number
}) {
  if (isPrimitive(value)) {
    return <PrimitiveValue value={value} />
  }

  if (Array.isArray(value)) {
    return <ArrayValue value={value} depth={depth} compact={compact} maxDepth={maxDepth} />
  }

  return (
    <ObjectValue
      value={value as Record<string, unknown>}
      depth={depth}
      compact={compact}
      maxDepth={maxDepth}
    />
  )
}

export function StructuredDataView({
  data,
  emptyMessage = "No structured data available.",
  className,
  compact = false,
  maxDepth = 3,
}: StructuredDataViewProps) {
  const isEmptyObject =
    typeof data === "object" && data !== null && !Array.isArray(data) && !Object.keys(data as Record<string, unknown>).length
  const isEmptyArray = Array.isArray(data) && data.length === 0

  if (data == null || isEmptyObject || isEmptyArray) {
    return (
      <div
        className={cn(
          "rounded-xl border border-dashed border-border bg-muted/30 px-3 py-3 text-sm text-muted-foreground",
          compact && "rounded-lg px-2 py-2 text-xs",
          className,
        )}
      >
        {emptyMessage}
      </div>
    )
  }

  return (
    <div className={cn("space-y-2", className)}>
      <StructuredDataNode value={data} depth={0} compact={compact} maxDepth={maxDepth} />
    </div>
  )
}

export type { StructuredDataViewProps }
