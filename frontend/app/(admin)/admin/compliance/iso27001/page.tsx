import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("ISO 27001")

export default function Page() {
  return <PageClient />
}
