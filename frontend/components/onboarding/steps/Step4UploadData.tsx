"use client"

import { Button } from "@/components/ui/button"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"
import { ValidationPanel } from "@/components/settings/ValidationPanel"
import { CoaUploader } from "@/components/settings/CoaUploader"
import { StructuredDataView } from "@/components/ui"
import { Upload } from "lucide-react"
import type { ReviewRow } from "@/lib/api/orgSetup"
import type { CoaUploadMode, CoaUploadResult, CoaTemplate } from "@/lib/api/coa"

interface AirlockItem {
  airlock_item_id: string
  file_name?: string | null
  source_reference?: string | null
  status: string
  source_type: string
  mime_type?: string | null
  metadata?: Record<string, unknown> | null
  findings: unknown[]
}

interface Step4Props {
  flowSteps: FlowStripStep[]
  uploadReview: ReviewRow[]
  templatesLoading: boolean
  templatesError: boolean
  templates: CoaTemplate[]
  selectedTemplateId: string
  setSelectedTemplateId: (id: string) => void
  uploadMode: CoaUploadMode
  setUploadMode: (mode: CoaUploadMode) => void
  uploadFile: File | null
  setUploadFile: (f: File | null) => void
  uploadResult: CoaUploadResult | null
  airlockLoading: boolean
  airlockError: boolean
  airlockData: AirlockItem[] | undefined
  onValidate: () => void
  onUpload: () => void
  isValidating: boolean
  isUploading: boolean
  onBack: () => void
  onNext: () => void
  renderQueryMessage: (state: { isLoading: boolean; isError: boolean; error: Error | null }, msg: string) => React.ReactNode
}

export function Step4UploadData({
  flowSteps,
  uploadReview,
  templatesLoading,
  templatesError,
  templates,
  selectedTemplateId,
  setSelectedTemplateId,
  uploadMode,
  setUploadMode,
  uploadFile,
  setUploadFile,
  uploadResult,
  airlockLoading,
  airlockError,
  airlockData,
  onValidate,
  onUpload,
  isValidating,
  isUploading,
  onBack,
  onNext,
  renderQueryMessage,
}: Step4Props) {
  return (
    <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
      <FlowStrip
        title="Upload Flow"
        subtitle="Upload, validate, review the queue, and then let the governed processing continue."
        steps={flowSteps}
      />

      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-foreground">Upload Initial Data</h2>
        <p className="text-sm text-muted-foreground">
          Use the existing intake path to validate your starting chart of accounts and inspect the queue.
        </p>
      </div>

      <section className="rounded-3xl border border-border bg-background/80 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Review before submit</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {uploadReview.map((row) => (
            <div key={row.label} className="rounded-2xl border border-border bg-card px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.label}</p>
              <p className="mt-2 text-sm text-foreground">{row.value}</p>
            </div>
          ))}
        </div>
      </section>

      {templatesLoading || templatesError
        ? renderQueryMessage(
            { isLoading: templatesLoading, isError: templatesError, error: null },
            "No templates are available yet. Start by loading a chart-of-accounts template.",
          )
        : (
          <>
            <CoaUploader
              templates={templates}
              selectedTemplateId={selectedTemplateId}
              onTemplateChange={setSelectedTemplateId}
              mode={uploadMode}
              onModeChange={setUploadMode}
              file={uploadFile}
              onFileChange={setUploadFile}
              onValidate={onValidate}
              onUpload={onUpload}
              validating={isValidating}
              uploading={isUploading}
            />
            <ValidationPanel result={uploadResult} />
          </>
        )
      }

      <section className="rounded-3xl border border-border bg-background/80 p-5">
        <div className="flex items-center gap-2">
          <Upload className="h-4 w-4 text-[hsl(var(--brand-primary))]" />
          <h3 className="text-base font-semibold text-foreground">Airlock Queue</h3>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          This is the current queue state from the backend. Validation issues appear inside each item.
        </p>

        <div className="mt-4 space-y-3">
          {airlockLoading || airlockError || !airlockData?.length
            ? renderQueryMessage(
                { isLoading: airlockLoading, isError: airlockError, error: null },
                "No data has entered the airlock yet. Start by uploading a file.",
              )
            : airlockData.map((item) => (
                <article key={item.airlock_item_id} className="rounded-2xl border border-border bg-card p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {item.file_name ?? item.source_reference ?? item.airlock_item_id}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Status: {item.status} - Source: {item.source_type}
                      </p>
                      {item.metadata?.source === "onboarding" && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          Origin: onboarding
                          {typeof item.metadata.onboarding_step === "string"
                            ? ` (${item.metadata.onboarding_step})`
                            : ""}
                        </p>
                      )}
                    </div>
                    <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                      {item.mime_type ?? "Unknown type"}
                    </span>
                  </div>

                  {item.findings.length > 0 ? (
                    <div className="mt-3 rounded-2xl border border-[hsl(var(--brand-warning)/0.4)] bg-[hsl(var(--brand-warning)/0.12)] p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-foreground">Validation issues</p>
                      <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                        {item.findings.map((finding, idx) => (
                          <li key={`${item.airlock_item_id}-${idx}`}>
                            <StructuredDataView
                              data={finding}
                              emptyMessage="No structured finding details were returned."
                              compact
                            />
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">
                      No validation issues reported for this queue item yet.
                    </p>
                  )}
                </article>
              ))
          }
        </div>
      </section>

      <div className="flex items-center justify-between">
        <Button type="button" variant="outline" onClick={onBack}>← Back</Button>
        <Button type="button" onClick={onNext}>Review Backend Confirmation →</Button>
      </div>
    </section>
  )
}
