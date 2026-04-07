import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Trial Balance")

export default function Page() {
  return <PageClient />
}
