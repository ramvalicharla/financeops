import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("White Label")

export default function Page() {
  return <PageClient />
}
