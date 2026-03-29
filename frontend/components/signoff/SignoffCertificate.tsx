"use client"

import { Button } from "@/components/ui/button"
import { type SignoffCertificatePayload } from "@/lib/types/sprint11"

export type SignoffCertificateProps = {
  certificate: SignoffCertificatePayload
  onVerify: () => Promise<void>
}

export function SignoffCertificate({ certificate, onVerify }: SignoffCertificateProps) {
  const downloadCertificate = (): void => {
    const blob = new Blob([JSON.stringify(certificate, null, 2)], {
      type: "application/json",
    })
    const href = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = href
    link.download = `${certificate.certificate_number}.json`
    link.click()
    URL.revokeObjectURL(href)
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm font-semibold text-foreground">{certificate.certificate_number}</p>
      <p className="text-xs text-muted-foreground">
        {certificate.signatory_name} · {certificate.signatory_role}
      </p>
      <p className="text-xs text-muted-foreground">Signed at {certificate.signed_at ?? "—"}</p>
      <p className="mt-3 text-xs text-foreground">
        Content hash: {certificate.content_hash.slice(0, 16)}...
      </p>
      <p className="mt-1 text-xs text-foreground">
        Signature hash: {certificate.signature_hash.slice(0, 16)}...
      </p>
      <p
        className={`mt-3 text-xs ${certificate.is_valid ? "text-emerald-400" : "text-[hsl(var(--brand-danger))]"}`}
      >
        {certificate.is_valid ? "Valid signature" : "Invalid signature"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={() => void onVerify()}>
          Verify Integrity
        </Button>
        <Button type="button" variant="outline" onClick={downloadCertificate}>
          Download Certificate
        </Button>
      </div>
    </div>
  )
}
