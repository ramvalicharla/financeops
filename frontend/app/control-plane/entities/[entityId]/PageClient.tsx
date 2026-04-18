"use client"

import { useParams } from "next/navigation"
import { ArrowLeft, Construction } from "lucide-react"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function EntityDetailPage() {
  const params = useParams()
  const id = params?.entityId ?? null

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 p-6">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-card">
        <Construction className="h-7 w-7 text-muted-foreground" />
      </div>
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-semibold text-foreground">Entity Detail</h1>
        <p className="text-sm text-muted-foreground max-w-md">Platform entity details and configuration.</p>
        {id ? (
          <p className="font-mono text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded">
            ID: {Array.isArray(id) ? id[0] : id}
          </p>
        ) : null}
      </div>
      <p className="rounded-full border border-border bg-card px-4 py-1.5 text-xs text-muted-foreground">
        Full implementation in progress — wires to live API
      </p>
      <Button variant="outline" size="sm" asChild>
        <Link href=".."><ArrowLeft className="mr-2 h-3 w-3" /> Back</Link>
      </Button>
    </div>
  )
}
