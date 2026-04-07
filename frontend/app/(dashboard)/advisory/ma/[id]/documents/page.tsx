import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("M&A Documents")

export default function Page() {
  return <PageClient />
}
