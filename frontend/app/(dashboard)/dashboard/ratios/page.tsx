import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Financial Ratios")

export default function Page() {
  return <PageClient />
}
