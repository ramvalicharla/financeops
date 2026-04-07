import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Submit Expense")

export default function Page() {
  return <PageClient />
}
