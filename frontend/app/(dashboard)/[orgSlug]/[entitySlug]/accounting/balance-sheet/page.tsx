import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Balance Sheet")

export default function Page() {
  return <PageClient />
}
