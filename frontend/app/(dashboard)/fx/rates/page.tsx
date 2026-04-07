import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("FX Rates")

export default function Page() {
  return <PageClient />
}
