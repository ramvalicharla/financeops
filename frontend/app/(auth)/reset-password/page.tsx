import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Reset Password")

export default function Page() {
  return <PageClient />
}
