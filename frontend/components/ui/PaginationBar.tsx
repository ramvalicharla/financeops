import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight } from "lucide-react"

export interface PaginationBarProps {
  total: number
  skip: number
  limit: number
  onPageChange: (newSkip: number) => void
  hasMore?: boolean
}

export function PaginationBar({
  total,
  skip,
  limit,
  onPageChange,
  hasMore,
}: PaginationBarProps) {
  const currentPage = Math.floor(skip / limit) + 1
  const totalPages = Math.max(1, Math.ceil(total / limit))
  
  // If the backend returns hasMore directly and total is 0 or unavailable, rely on hasMore.
  const canGoNext = hasMore !== undefined ? hasMore : currentPage < totalPages
  const canGoPrev = skip > 0
  
  // Start and end item index
  const startItem = total === 0 ? 0 : skip + 1
  const endItem = Math.min(skip + limit, total || skip + limit)

  return (
    <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted-foreground w-full">
      <div>
        Showing {startItem} to {endItem}{" "}
        {total > 0 ? `of ${total}` : ""}
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.max(0, skip - limit))}
          disabled={!canGoPrev}
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Previous
        </Button>
        <span className="mx-2 tabular-nums">
          Page {currentPage} {total > 0 ? `of ${totalPages}` : ""}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(skip + limit)}
          disabled={!canGoNext}
        >
          Next
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
