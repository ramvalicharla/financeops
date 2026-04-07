import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("M&A Valuation")

export default function Page() {
  return <PageClient />
}
