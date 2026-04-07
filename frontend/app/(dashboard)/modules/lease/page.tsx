import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Lease Module")

export default function Page() {
  return <PageClient />
}
