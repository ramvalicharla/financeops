import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Sign In", "Sign in to Finqor")

export default function Page() {
  return <PageClient />
}
