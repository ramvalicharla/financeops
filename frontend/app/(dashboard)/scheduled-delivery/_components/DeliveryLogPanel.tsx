"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"

export function DeliveryLogPanel() {
  return (
    <Button type="button" variant="outline" asChild>
      <Link href="/scheduled-delivery/logs">View Logs</Link>
    </Button>
  )
}
