import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Prepaid Expenses', 'Prepaid expense schedules and amortisation')

export default function Page() {
  return <PageClient />
}
