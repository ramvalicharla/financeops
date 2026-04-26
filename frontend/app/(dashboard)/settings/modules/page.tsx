import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Module Manager")

export default function Page() {
  return <PageClient />
}
