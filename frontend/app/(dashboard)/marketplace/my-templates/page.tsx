import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("My Templates")

export default function Page() {
  return <PageClient />
}
