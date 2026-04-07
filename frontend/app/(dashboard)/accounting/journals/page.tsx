import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Journals")

export default function Page() {
  return <PageClient />
}
