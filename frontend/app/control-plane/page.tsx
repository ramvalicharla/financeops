import type { Metadata } from "next"
import { redirect } from "next/navigation"

export const metadata: Metadata = {
  title: "Control Plane · Finqor",
  description: "Platform owner control plane.",
}

export default function Page() {
  redirect("/control-plane/overview")
}
