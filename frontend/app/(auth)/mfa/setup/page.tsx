import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Set Up Two-Factor Authentication")

export default function Page() {
  return <PageClient />
}
