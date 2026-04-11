"use client"

import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { AirlockQueue } from "@/components/airlock/AirlockQueue"
import { AirlockReview } from "@/components/airlock/AirlockReview"

interface ControlPlaneAirlockPageProps {
  itemId?: string | null
}

export function ControlPlaneAirlockPage({ itemId }: ControlPlaneAirlockPageProps) {
  return (
    <PageScaffold
      title="Airlock"
      description="Zero-trust intake visibility for uploaded artifacts and their backend admission state."
    >
      {itemId ? <AirlockReview itemId={itemId} /> : <AirlockQueue detailHrefPrefix="/control-plane/airlock" />}
    </PageScaffold>
  )
}
