import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Prepaid")

export default function Page({ params }: { params: { id: string } }) {
  return <PageClient params={params} />
}
