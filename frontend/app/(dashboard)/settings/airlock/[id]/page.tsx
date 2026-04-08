import { AirlockReview } from "@/components/airlock/AirlockReview"

interface AirlockReviewPageProps {
  params: {
    id: string
  }
}

export default function AirlockReviewPage({ params }: AirlockReviewPageProps) {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Airlock Review</h1>
        <p className="text-sm text-muted-foreground">
          Review backend findings and use canonical admit or reject actions only.
        </p>
      </header>
      <AirlockReview itemId={params.id} />
    </div>
  )
}
