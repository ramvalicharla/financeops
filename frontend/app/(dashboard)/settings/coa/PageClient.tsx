"use client"

import { toast } from "sonner"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query/keys"
import { Button } from "@/components/ui/button"
import { CoaPreviewTable } from "@/components/settings/CoaPreviewTable"
import { CoaUploader } from "@/components/settings/CoaUploader"
import { ValidationPanel } from "@/components/settings/ValidationPanel"
import {
  applyCoaBatch,
  getCoaTemplates,
  getEffectiveCoaAccounts,
  listCoaUploadBatches,
  type CoaUploadMode,
  type CoaUploadResult,
  uploadCoaFile,
  validateCoaFile,
} from "@/lib/api/coa"

const DEFAULT_MODE: CoaUploadMode = "APPEND"

export default function CoaSettingsPage() {
  const queryClient = useQueryClient()
  const [selectedTemplateId, setSelectedTemplateId] = useState("")
  const [mode, setMode] = useState<CoaUploadMode>(DEFAULT_MODE)
  const [file, setFile] = useState<File | null>(null)
  const [lastUpload, setLastUpload] = useState<CoaUploadResult | null>(null)
  const [validationResult, setValidationResult] = useState<CoaUploadResult | null>(null)
    const [error, setError] = useState<string | null>(null)

  const templatesQuery = useQuery({
    queryKey: queryKeys.coa.templates(),
    queryFn: getCoaTemplates,
  })

  const accountsQuery = useQuery({
    queryKey: queryKeys.coa.effectiveAccounts(selectedTemplateId),
    queryFn: () =>
      getEffectiveCoaAccounts(
        selectedTemplateId ? { template_id: selectedTemplateId } : {},
      ),
  })

  const batchesQuery = useQuery({
    queryKey: queryKeys.coa.uploadBatches(),
    queryFn: () => listCoaUploadBatches(100),
  })

  const validateMutation = useMutation({
    mutationFn: (targetFile: File) => validateCoaFile(targetFile),
    onSuccess: (result) => {
      setValidationResult(result as CoaUploadResult)
      toast.success("Validation completed")
      setError(null)
    },
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Validation failed")
          },
  })

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) {
        throw new Error("Please select a file")
      }
      if (!selectedTemplateId) {
        throw new Error("Please select an industry template")
      }
      return uploadCoaFile({
        file,
        template_id: selectedTemplateId,
        mode,
      })
    },
    onSuccess: (result) => {
      setLastUpload(result)
      setValidationResult(result)
      toast.success("Upload completed")
      setError(null)
      void queryClient.invalidateQueries({ queryKey: queryKeys.coa.uploadBatches() })
    },
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Upload failed")
          },
  })

  const applyMutation = useMutation({
    mutationFn: (batchId: string) => applyCoaBatch(batchId),
    onSuccess: () => {
      toast.success("CoA batch applied successfully")
      setError(null)
      void queryClient.invalidateQueries({ queryKey: queryKeys.coa.effectiveAccountsAll() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.coa.uploadBatches() })
    },
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Apply failed")
          },
  })

  const latestBatchId = useMemo(() => {
    if (lastUpload?.batch_id) {
      return lastUpload.batch_id
    }
    return ""
  }, [lastUpload])

  return (
    <div className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-foreground">CoA Upload & Management</h1>
        <p className="text-sm text-muted-foreground">
          Manage global/admin templates and tenant-specific CoA overrides.
        </p>
      </header>

            {error ? <p className="text-sm text-rose-400">{error}</p> : null}

      <CoaUploader
        templates={templatesQuery.data ?? []}
        selectedTemplateId={selectedTemplateId}
        onTemplateChange={setSelectedTemplateId}
        mode={mode}
        onModeChange={setMode}
        file={file}
        onFileChange={setFile}
        onValidate={() => {
          if (file) {
            validateMutation.mutate(file)
          }
        }}
        onUpload={() => uploadMutation.mutate()}
        validating={validateMutation.isPending}
        uploading={uploadMutation.isPending}
      />

      <ValidationPanel result={validationResult} />

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground">Apply Uploaded CoA</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Applies staged rows to production tables with version tracking.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <code className="rounded bg-background px-2 py-1 text-xs text-muted-foreground">
            {latestBatchId || "No uploaded batch selected"}
          </code>
          <Button
            onClick={() => latestBatchId && applyMutation.mutate(latestBatchId)}
            disabled={!latestBatchId || applyMutation.isPending}
          >
            {applyMutation.isPending ? "Applying..." : "Apply"}
          </Button>
        </div>
      </section>

      <CoaPreviewTable
        accounts={accountsQuery.data ?? []}
        batches={batchesQuery.data ?? []}
      />
    </div>
  )
}
