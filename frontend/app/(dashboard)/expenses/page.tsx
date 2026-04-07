import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Expenses")

export default function Page() {
  return <PageClient />
}
