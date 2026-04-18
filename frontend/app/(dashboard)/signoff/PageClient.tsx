"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { SignoffCertificate } from "@/components/signoff/SignoffCertificate"
import { SignoffRequest } from "@/components/signoff/SignoffRequest"
import {
  getSignoffCertificate,
  listSignoffs,
  signoffSign,
  verifySignoff,
} from "@/lib/api/sprint11"
import { type SignoffCertificatePayload, type SignoffRecord } from "@/lib/types/sprint11"

export default function SignoffPage() {
  const [rows, setRows] = useState<SignoffRecord[]>([])
  const [certificates, setCertificates] = useState<Record<string, SignoffCertificatePayload>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listSignoffs({ limit: 200, offset: 0 })
      setRows(payload.data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load signoffs")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const pending = useMemo(() => rows.filter((row) => row.status === "pending"), [rows])
  const completed = useMemo(() => rows.filter((row) => row.status === "signed"), [rows])

  const handleSign = async (row: SignoffRecord, totp: string): Promise<void> => {
    await signoffSign(row.id, totp)
    await load()
  }

  const ensureCertificate = async (signoffId: string): Promise<SignoffCertificatePayload | null> => {
    if (certificates[signoffId]) {
      return certificates[signoffId]
    }
    try {
      const cert = await getSignoffCertificate(signoffId)
      setCertificates((prev) => ({ ...prev, [signoffId]: cert }))
      return cert
    } catch {
      return null
    }
  }

  const handleVerify = async (signoffId: string): Promise<void> => {
    const cert = await ensureCertificate(signoffId)
    if (!cert) {
      return
    }
    await verifySignoff(signoffId, cert.content_hash)
    const refreshed = await getSignoffCertificate(signoffId)
    setCertificates((prev) => ({ ...prev, [signoffId]: refreshed }))
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Digital Signoff</h1>

      {loading ? <p className="text-sm text-muted-foreground">Loading signoff queue...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Pending</h2>
        {pending.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
            No pending signoffs.
          </p>
        ) : null}
        {pending.map((row) => (
          <SignoffRequest
            key={row.id}
            signoff={row}
            onSigned={(totp) => handleSign(row, totp)}
          />
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Completed</h2>
        {completed.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
            No completed signoffs yet.
          </p>
        ) : null}
        {completed.map((row) => {
          const certificate = certificates[row.id]
          return certificate ? (
            <SignoffCertificate
              key={row.id}
              certificate={certificate}
              onVerify={() => handleVerify(row.id)}
            />
          ) : (
            <button
              key={row.id}
              type="button"
              className="rounded-xl border border-border bg-card px-4 py-3 text-left text-sm text-foreground"
              onClick={() => void ensureCertificate(row.id)}
            >
              Load certificate · {row.document_reference}
            </button>
          )
        })}
      </section>
    </div>
  )
}
