"use client"

import type { CoaTemplate, CoaUploadMode } from "@/lib/api/coa"
import { Button } from "@/components/ui/button"

interface CoaUploaderProps {
  templates: CoaTemplate[]
  selectedTemplateId: string
  onTemplateChange: (value: string) => void
  mode: CoaUploadMode
  onModeChange: (value: CoaUploadMode) => void
  file: File | null
  onFileChange: (file: File | null) => void
  onValidate: () => void
  onUpload: () => void
  validating: boolean
  uploading: boolean
}

export function CoaUploader({
  templates,
  selectedTemplateId,
  onTemplateChange,
  mode,
  onModeChange,
  file,
  onFileChange,
  onValidate,
  onUpload,
  validating,
  uploading,
}: CoaUploaderProps) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground">Upload CoA</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Upload CSV/XLSX up to 5MB. Validate first, then apply.
      </p>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <select
          value={selectedTemplateId}
          onChange={(event) => onTemplateChange(event.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="">Select template</option>
          {templates.map((template) => (
            <option key={template.id} value={template.id}>
              {template.name}
            </option>
          ))}
        </select>

        <select
          value={mode}
          onChange={(event) => onModeChange(event.target.value as CoaUploadMode)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="APPEND">APPEND</option>
          <option value="REPLACE">REPLACE</option>
          <option value="VALIDATE_ONLY">VALIDATE_ONLY</option>
        </select>

        <input
          type="file"
          accept=".csv,.xlsx"
          onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          onClick={onValidate}
          disabled={!file || validating}
        >
          {validating ? "Validating..." : "Validation Preview"}
        </Button>
        <Button
          onClick={onUpload}
          disabled={!file || !selectedTemplateId || uploading}
        >
          {uploading ? "Uploading..." : "Upload"}
        </Button>
        <a
          href="/templates/coa_upload_template.csv"
          className="text-sm text-[hsl(var(--brand-primary))] underline-offset-4 hover:underline"
          download
        >
          Download template
        </a>
      </div>

      {file ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Selected file: {file.name}
        </p>
      ) : null}
    </section>
  )
}
