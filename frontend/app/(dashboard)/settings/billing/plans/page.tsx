import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Billing Plans")

export default function Page() {
  return <PageClient />
}
