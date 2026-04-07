import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("CFO Dashboard")

export default function Page() {
  return <PageClient />
}
