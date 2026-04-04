import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Sign In", "Sign in to FinanceOps")

export default function Page() {
  return <PageClient />
}
