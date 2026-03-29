"use client"

import { useState } from "react"
import type { MADocument } from "@/lib/types/ma"

interface DocumentVaultProps {
  documents: MADocument[]
  onRegister: (payload: {
    document_name: string
    document_type: string
    file_url?: string
    file_size_bytes?: number
    is_confidential?: boolean
  }) => Promise<void>
}

export function DocumentVault({ documents, onRegister }: DocumentVaultProps) {
  const [documentName, setDocumentName] = useState("")
  const [documentType, setDocumentType] = useState("other")
  const [fileUrl, setFileUrl] = useState("")

  return (
    <section className="space-y-4">
      <article className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-base font-semibold text-foreground">Register Document</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Document name"
            value={documentName}
            onChange={(event) => setDocumentName(event.target.value)}
          />
          <select
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={documentType}
            onChange={(event) => setDocumentType(event.target.value)}
          >
            <option value="nda">nda</option>
            <option value="loi">loi</option>
            <option value="spa">spa</option>
            <option value="sha">sha</option>
            <option value="disclosure_schedule">disclosure_schedule</option>
            <option value="financial_model">financial_model</option>
            <option value="dd_report">dd_report</option>
            <option value="board_presentation">board_presentation</option>
            <option value="regulatory_filing">regulatory_filing</option>
            <option value="other">other</option>
          </select>
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="https://..."
            value={fileUrl}
            onChange={(event) => setFileUrl(event.target.value)}
          />
        </div>
        <button
          type="button"
          className="mt-3 rounded-md border border-border px-3 py-2 text-sm text-foreground"
          onClick={() => {
            if (!documentName.trim()) return
            void onRegister({
              document_name: documentName.trim(),
              document_type: documentType,
              file_url: fileUrl.trim() || undefined,
              is_confidential: true,
            })
            setDocumentName("")
            setFileUrl("")
          }}
        >
          Register
        </button>
      </article>

      <article className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h4 className="text-sm font-semibold text-foreground">Document Vault</h4>
        </div>
        <div className="divide-y divide-border/60">
          {documents.map((doc) => (
            <div key={doc.id} className="flex items-center justify-between px-4 py-3 text-sm">
              <div>
                <p className="text-foreground">{doc.document_name}</p>
                <p className="text-xs text-muted-foreground">
                  {doc.document_type} · v{doc.version}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {doc.is_confidential ? (
                  <span className="rounded-full bg-[hsl(var(--brand-danger)/0.2)] px-2 py-0.5 text-xs text-[hsl(var(--brand-danger))]">
                    Confidential
                  </span>
                ) : null}
                {doc.file_url ? (
                  <a href={doc.file_url} target="_blank" rel="noreferrer" className="text-xs text-[hsl(var(--brand-primary))]">
                    Open
                  </a>
                ) : null}
              </div>
            </div>
          ))}
          {documents.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">No documents registered yet.</p>
          ) : null}
        </div>
      </article>
    </section>
  )
}
