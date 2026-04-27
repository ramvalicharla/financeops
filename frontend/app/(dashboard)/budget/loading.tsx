import { Skeleton } from "@/components/ui/skeleton"
import { TableSkeleton } from "@/components/ui/TableSkeleton"
import { Table, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export default function LoadingBoundary() {
  return (
    <div className="space-y-6 p-6">
      <div className="space-y-2">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-72" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="space-y-3 rounded-xl border border-border bg-card p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-3 w-36" />
          </div>
        ))}
      </div>
      <div className="overflow-hidden rounded-md border border-border bg-card">
        <Table>
          <TableHeader className="border-b border-border bg-muted/50">
            <TableRow>
              <TableHead><Skeleton className="h-4 w-32" /></TableHead>
              <TableHead><Skeleton className="h-4 w-24" /></TableHead>
              <TableHead><Skeleton className="h-4 w-20" /></TableHead>
              <TableHead><Skeleton className="h-4 w-24" /></TableHead>
            </TableRow>
          </TableHeader>
          <TableSkeleton rows={6} cols={4} />
        </Table>
      </div>
    </div>
  )
}
