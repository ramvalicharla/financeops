"use client"

import { ChecklistScreen } from "@/components/closing/ChecklistScreen"

interface ClosePeriodPageProps {
  params: {
    period: string
  }
}

export default function ClosePeriodPage({ params }: ClosePeriodPageProps) {
  return <ChecklistScreen initialPeriod={params.period} showPeriodSelector forceReadOnly={false} />
}
