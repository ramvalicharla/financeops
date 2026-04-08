"use client"

import Link from "next/link"
import { useSession } from "next-auth/react"
import { JournalList } from "@/components/journals/JournalList"
import { Button } from "@/components/ui/button"
import { canPerformAction, getPermissionDeniedMessage } from "@/lib/ui-access"

export default function JournalsPage() {
  const { data: session } = useSession()
  const userRole = String((session?.user as { role?: string } | undefined)?.role ?? "")
  const canCreateJournal = canPerformAction("journal.create", userRole)

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Journals</h1>
          <p className="text-sm text-muted-foreground">
            Read-only control-plane view of governed journal state, lifecycle metadata, and backend-linked actions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/accounting/trial-balance">
            <Button variant="outline">Trial Balance</Button>
          </Link>
          {canCreateJournal ? (
            <Link href="/accounting/journals/new">
              <Button>Create Journal</Button>
            </Link>
          ) : (
            <Button disabled title={getPermissionDeniedMessage("journal.create")}>
              Create Journal
            </Button>
          )}
        </div>
      </header>

      <JournalList />
    </div>
  )
}
