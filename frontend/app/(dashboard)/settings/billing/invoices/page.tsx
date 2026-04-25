import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Invoices")

export default function Page() {
  return <PageClient />
}
