import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Cash Flow")

export default function Page() {
  return <PageClient />
}
