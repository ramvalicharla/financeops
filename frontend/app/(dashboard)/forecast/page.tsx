import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Forecast', 'Financial forecasting and scenario planning')

export default function Page() {
  return <PageClient />
}
