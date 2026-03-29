import Link from "next/link"

export default function AdminComplianceIndexPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-foreground">Compliance</h1>
      <p className="text-sm text-muted-foreground">Select a framework dashboard.</p>
      <div className="flex gap-3">
        <Link href="/admin/compliance/soc2" className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          SOC2
        </Link>
        <Link href="/admin/compliance/iso27001" className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          ISO 27001
        </Link>
      </div>
    </div>
  )
}

