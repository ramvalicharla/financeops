import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface TableSkeletonProps {
  rows?: number
  cols?: number
  className?: string
}

export function TableSkeleton({ rows = 8, cols = 5, className }: TableSkeletonProps) {
  return (
    <tbody className={cn("divide-y divide-border", className)}>
      <tr>
        <td className="sr-only" aria-live="polite" aria-atomic={true}>Loading data, please wait.</td>
      </tr>
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <tr key={rowIdx}>
          {Array.from({ length: cols }).map((_, colIdx) => (
            <td key={colIdx} className="px-3 py-2">
              <Skeleton className={cn("h-4", colIdx === 0 ? "w-32" : "w-full")} />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  )
}
