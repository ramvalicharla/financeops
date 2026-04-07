import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Onboarding")

export default function Page() {
  return <PageClient />
}
