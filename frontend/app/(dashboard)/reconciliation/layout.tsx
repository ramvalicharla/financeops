import type { ReactNode } from "react"
import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata("Reconciliation", "GL and payroll reconciliation workflows")

export default function ReconciliationLayout({
  children,
}: {
  children: ReactNode
}) {
  return <>{children}</>
}
