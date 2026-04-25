import type { Metadata } from "next"
import { AirlockQueue } from "@/components/airlock/AirlockQueue"

export const metadata: Metadata = {
  title: "Airlock Queue · Finqor",
  description: "Review and approve incoming data submissions before they land in production accounting records.",
}

export default function AirlockQueuePage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Airlock Queue</h1>
        <p className="text-sm text-muted-foreground">
          First-wave external inputs awaiting governance review and admission state visibility.
        </p>
      </header>
      <AirlockQueue />
    </div>
  )
}
