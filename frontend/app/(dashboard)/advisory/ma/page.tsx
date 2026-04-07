import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("M&A")

export default function Page() {
  return <PageClient />
}
