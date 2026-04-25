// Metadata intentionally omitted: parallel route intercept.
// Parent route's <title> remains active while this modal is open.
import { InterceptingSheet } from "@/components/layout/_components/InterceptingSheet"
import PageClient from "../../new/PageClient"

export default function CreateJournalModal() {
  return (
    <InterceptingSheet 
      title="Create Journal Entry" 
      description="Manually record a new accounting journal entry to the active ledger."
      width="max-w-4xl"
    >
      {/* 
        This is the exact same component that would render on the full page,
        now beautifully executing inline over the main table via Next.js Parallel Routes!
      */}
      <div className="pt-4">
        <PageClient />
      </div>
    </InterceptingSheet>
  )
}
