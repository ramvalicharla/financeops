import { cn } from "@/lib/utils"

export type RAGStatus = "green" | "amber" | "red" | "grey"

export function RAGBadge({ status }: { status: RAGStatus }) {
  const label =
    status === "green"
      ? "Pass"
      : status === "amber"
        ? "Partial"
        : status === "red"
          ? "Fail"
          : "Not Evaluated"

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs",
        status === "green" && "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
        status === "amber" && "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
        status === "red" && "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
        status === "grey" && "bg-muted text-muted-foreground",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "green" && "bg-[hsl(var(--brand-success))]",
          status === "amber" && "bg-[hsl(var(--brand-warning))]",
          status === "red" && "bg-[hsl(var(--brand-danger))]",
          status === "grey" && "bg-muted-foreground",
        )}
      />
      {label}
    </span>
  )
}

