import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Budget")

export default function Page() {
  return <PageClient />
}
