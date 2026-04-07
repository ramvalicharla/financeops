import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("AI Dashboard")

export default function Page() {
  return <PageClient />
}
