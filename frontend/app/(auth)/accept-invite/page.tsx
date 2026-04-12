import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Accept Invitation", "Accept your Finqor invitation")

export default function Page() {
  return <PageClient />
}
