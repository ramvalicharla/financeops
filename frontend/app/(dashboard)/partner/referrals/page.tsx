import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Referrals")

export default function Page() {
  return <PageClient />
}
