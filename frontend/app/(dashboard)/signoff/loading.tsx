import { Skeleton } from "@/components/ui/skeleton"
import { TableSkeleton } from "@/components/ui/TableSkeleton"
import { Table, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export default function LoadingBoundary() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-9 w-28" />
      </div>
      <div className="overflow-hidden rounded-md border border-border bg-card">
        <Table>
          <TableHeader className="border-b border-border bg-muted/50">
            <TableRow>
              <TableHead><Skeleton className="h-4 w-32" /></TableHead>
              <TableHead><Skeleton className="h-4 w-28" /></TableHead>
              <TableHead><Skeleton className="h-4 w-24" /></TableHead>
              <TableHead><Skeleton className="h-4 w-20" /></TableHead>
            </TableRow>
          </TableHeader>
          <TableSkeleton rows={6} cols={4} />
        </Table>
      </div>
    </div>
  )
}
