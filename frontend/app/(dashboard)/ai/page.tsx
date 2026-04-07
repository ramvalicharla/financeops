import { redirect } from "next/navigation"
import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata("AI")


export default function AiRootPage() {
  redirect("/ai/dashboard")
}

