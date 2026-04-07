import { redirect } from "next/navigation"
import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata("Period Close")


interface ClosePeriodPageProps {
  params: {
    period: string
  }
}

export default function ClosePeriodPage({ params }: ClosePeriodPageProps) {
  redirect(`/close/checklist?period=${encodeURIComponent(params.period)}`)
}
