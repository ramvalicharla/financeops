import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Contribute Template")

export default function Page() {
  return <PageClient />
}
