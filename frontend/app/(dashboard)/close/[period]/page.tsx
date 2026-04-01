import { redirect } from "next/navigation"

interface ClosePeriodPageProps {
  params: {
    period: string
  }
}

export default function ClosePeriodPage({ params }: ClosePeriodPageProps) {
  redirect(`/close/checklist?period=${encodeURIComponent(params.period)}`)
}
