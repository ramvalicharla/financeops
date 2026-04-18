"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { DocumentVault } from "@/components/advisory/ma/DocumentVault"
import { listMADocuments, registerMADocument } from "@/lib/api/ma"
import type { MADocument } from "@/lib/types/ma"

export default function MADocumentsPage() {
  const params = useParams()
  const workspaceId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""
  const [documents, setDocuments] = useState<MADocument[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const payload = await listMADocuments(workspaceId, { limit: 100, offset: 0 })
      setDocuments(payload.data)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load documents")
    }
  }, [workspaceId])

  useEffect(() => {
    if (workspaceId) {
      void load()
    }
  }, [workspaceId, load])

  const register = async (payload: {
    document_name: string
    document_type: string
    file_url?: string
    file_size_bytes?: number
    is_confidential?: boolean
  }) => {
    await registerMADocument(workspaceId, payload)
    await load()
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Document Vault</h1>
          <p className="text-sm text-muted-foreground">Deal documents and version registry</p>
        </div>
        <Link href={`/advisory/ma/${workspaceId}`} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          Back to Workspace
        </Link>
      </header>
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      <DocumentVault documents={documents} onRegister={register} />
    </div>
  )
}
