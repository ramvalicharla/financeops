import { Bolt, FilePenLine } from "lucide-react"
import type { ComplianceControl } from "@/lib/types/compliance"
import { RAGBadge } from "@/components/compliance/RAGBadge"

interface ControlCardProps {
  control: ComplianceControl
  isAdminView: boolean
  onSelect: (control: ComplianceControl) => void
}

export function ControlCard({ control, isAdminView, onSelect }: ControlCardProps) {
  return (
    <article className="rounded-lg border border-border bg-card px-3 py-3">
      <div className="mb-1 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted-foreground">{control.control_id}</p>
          <h4 className="text-sm font-medium text-foreground">{control.control_name}</h4>
        </div>
        <RAGBadge status={control.rag_status} />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {control.auto_evaluable ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5">
              <Bolt className="h-3 w-3" />
              Auto
            </span>
          ) : null}
          <span>{control.status}</span>
        </div>
        <button
          type="button"
          onClick={() => onSelect(control)}
          className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-foreground"
        >
          {isAdminView ? <FilePenLine className="h-3 w-3" /> : null}
          View
        </button>
      </div>
    </article>
  )
}

