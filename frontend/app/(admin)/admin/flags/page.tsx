import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Feature Flags")

export default function Page() {
  return <PageClient />
}
