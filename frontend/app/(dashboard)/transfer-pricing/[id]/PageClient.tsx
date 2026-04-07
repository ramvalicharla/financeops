"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { ICTransactionTable } from "@/components/transfer_pricing/ICTransactionTable"
import { TPDocumentViewer } from "@/components/transfer_pricing/TPDocumentViewer"
import { getTransferPricingDoc, listICTransactions } from "@/lib/api/sprint11"
import { type ICTransaction, type TransferPricingDoc } from "@/lib/types/sprint11"

export default function TransferPricingDetailPage() {
  const params = useParams<{ id: string }>()
  const documentId = params?.id ?? ""
  const [tpDocument, setTpDocument] = useState<TransferPricingDoc | null>(null)
  const [transactions, setTransactions] = useState<ICTransaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!documentId) {
      return
    }
    const load = async (): Promise<void> => {
      setLoading(true)
      setError(null)
      try {
        const doc = await getTransferPricingDoc(documentId)
        const txnPayload = await listICTransactions({
          fiscal_year: doc.fiscal_year,
          limit: 200,
          offset: 0,
        })
        setTpDocument(doc)
        setTransactions(txnPayload.data)
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load TP document")
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [documentId])

  const downloadReport = (): void => {
    if (!tpDocument) {
      return
    }
    const blob = new Blob([JSON.stringify(tpDocument, null, 2)], {
      type: "application/json",
    })
    const href = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = href
    link.download = `form-3ceb-${tpDocument.fiscal_year}-v${tpDocument.version}.json`
    link.click()
    URL.revokeObjectURL(href)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Form 3CEB</h1>
      {!documentId ? <p className="text-sm text-red-400">Missing document ID.</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading document...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {tpDocument ? (
        <>
          <TPDocumentViewer document={tpDocument} />
          <Button variant="outline" onClick={downloadReport}>
            Download Report
          </Button>
        </>
      ) : null}
      <ICTransactionTable rows={transactions} />
    </div>
  )
}
