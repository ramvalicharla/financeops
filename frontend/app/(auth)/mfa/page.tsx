import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("MFA Verification")

export default function Page() {
  return <PageClient />
}
