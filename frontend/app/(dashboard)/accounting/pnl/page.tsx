import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("P&L")

export default function Page() {
  return <PageClient />
}
