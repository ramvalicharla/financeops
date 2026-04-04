import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Reset Password", "Reset your FinanceOps password")

export default function Page() {
  return <PageClient />
}
