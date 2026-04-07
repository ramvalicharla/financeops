import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Close Checklist")

export default function Page() {
  return <PageClient />
}
