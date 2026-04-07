import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Sign-off")

export default function Page() {
  return <PageClient />
}
