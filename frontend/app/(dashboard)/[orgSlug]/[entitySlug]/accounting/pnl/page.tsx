import PageClient from "./PageClient"
import { createMetadata } from "@/lib/metadata"
export const metadata = createMetadata("Profit & Loss")
export default function Page() { return <PageClient /> }
