import { InterceptingSheet } from "@/components/layout/_components/InterceptingSheet"
import PageClient from "../../[id]/PageClient"

export default function ViewJournalModal({ params }: { params: { id: string } }) {
  return (
    <InterceptingSheet 
      title={`Journal Entry ${params.id}`}
      description="View full audit trail and line items for this specific ledger entry."
      width="max-w-5xl"
    >
      <div className="pt-4">
        <PageClient params={params} />
      </div>
    </InterceptingSheet>
  )
}
