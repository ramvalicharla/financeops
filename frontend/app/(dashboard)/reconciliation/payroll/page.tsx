import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Payroll Reconciliation")

export default function Page() {
  return <PageClient />
}
