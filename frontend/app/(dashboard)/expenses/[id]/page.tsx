import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Expense")

export default function Page({ params }: { params: { id: string } }) {
  return <PageClient params={params} />
}
