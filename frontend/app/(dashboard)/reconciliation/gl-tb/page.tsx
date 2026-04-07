import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("GL-TB Reconciliation")

export default function Page() {
  return <PageClient />
}
