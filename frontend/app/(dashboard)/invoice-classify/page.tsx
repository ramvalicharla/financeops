import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Invoice Classify")

export default function Page() {
  return <PageClient />
}
