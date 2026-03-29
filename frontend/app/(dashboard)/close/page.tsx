"use client"

import { ChecklistScreen } from "@/components/closing/ChecklistScreen"

export default function ClosePage() {
  const currentPeriod = new Date().toISOString().slice(0, 7)
  return <ChecklistScreen initialPeriod={currentPeriod} showPeriodSelector />
}
