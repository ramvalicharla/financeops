import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("ERP Connectors")

export default function Page() {
  return <PageClient />
}
