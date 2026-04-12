import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Create Account", "Create your Finqor account")

export default function Page() {
  return <PageClient />
}
