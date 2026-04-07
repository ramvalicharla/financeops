import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Currency Translation")

export default function Page() {
  return <PageClient />
}
