import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Create Account", "Create your FinanceOps account")

export default function Page() {
  return <PageClient />
}
