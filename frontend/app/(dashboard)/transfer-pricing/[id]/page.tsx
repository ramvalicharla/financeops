import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Transfer Pricing")

export default function Page() {
  return <PageClient />
}
