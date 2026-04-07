import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Change Password")

export default function Page() {
  return <PageClient />
}
