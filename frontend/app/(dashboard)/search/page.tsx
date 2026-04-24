import type { Metadata } from "next"
import PageClient from "./PageClient"

export const metadata: Metadata = {
  title: "Global Search | Finqor",
}

export default function GlobalSearchPage() {
  return <PageClient />
}
