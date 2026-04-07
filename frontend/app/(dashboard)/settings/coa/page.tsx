import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Chart of Accounts")

export default function Page() {
  return <PageClient />
}
