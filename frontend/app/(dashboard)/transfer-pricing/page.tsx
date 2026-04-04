import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Transfer Pricing', 'Intercompany transfer pricing management')

export default function Page() {
  return <PageClient />
}
