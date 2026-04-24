"use client"

import { Suspense, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { CoaUploader } from "@/components/settings/CoaUploader"
import { ValidationPanel } from "@/components/settings/ValidationPanel"
import {
  applyCoaBatch,
  getCoaTemplates,
  listCoaUploadBatches,
  skipCoaSetup,
  uploadCoaFile,
  validateCoaFile,
  type CoaUploadMode,
  type CoaUploadResult,
} from "@/lib/api/coa"
import { getOrgSetupSummary } from "@/lib/api/orgSetup"
import { queryKeys } from "@/lib/query/keys"
import { toast } from "sonner"

const DEFAULT_MODE: CoaUploadMode = "APPEND"

function SetupCoaPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
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

  const batchesQuery = useQuery({
    queryKey: queryKeys.coa.uploadBatches(),
    queryFn: () => listCoaUploadBatches(50),
  })

  const summaryQuery = useQuery({
    queryKey: queryKeys.orgSetup.summary(),
    queryFn: getOrgSetupSummary,
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
    onSuccess: async () => {
      toast.success("CoA batch applied successfully")
      setError(null)
      await queryClient.invalidateQueries({ queryKey: queryKeys.orgSetup.summary() })
      await queryClient.invalidateQueries({ queryKey: queryKeys.coa.uploadBatches() })
    },
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Apply failed")
          },
  })

  const skipMutation = useMutation({
    mutationFn: skipCoaSetup,
    onSuccess: async () => {
      setError(null)
            await queryClient.invalidateQueries({ queryKey: queryKeys.orgSetup.summary() })
      router.push(nextPath)
    },
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Unable to skip CoA setup right now")
          },
  })

  const latestBatchId = useMemo(() => {
    if (lastUpload?.batch_id) {
      return lastUpload.batch_id
    }
    return batchesQuery.data?.[0]?.id ?? ""
  }, [batchesQuery.data, lastUpload?.batch_id])

  const coaAccountCount = summaryQuery.data?.coa_account_count ?? 0
  const coaStatus = summaryQuery.data?.coa_status ?? "pending"
  const nextPath = useMemo(() => {
    const next = searchParams?.get("next")
    if (next && next.startsWith("/")) {
      return next
    }
    return "/org-setup"
  }, [searchParams])

  return (
    <div className="space-y-6 p-2">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-foreground">Upload Chart of Accounts</h1>
        <p className="text-sm text-muted-foreground">
          Uploading CoA is optional during onboarding.
        </p>
        <p className="text-sm text-muted-foreground">
          You can upload later or connect your ERP.
        </p>
        <p className="text-sm text-muted-foreground">
          Current CoA status: <span className="font-semibold capitalize text-foreground">{coaStatus.replace("_", " ")}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          Current CoA account count: <span className="font-semibold text-foreground">{coaAccountCount}</span>
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
          Applies staged rows to production tables.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <code className="rounded bg-background px-2 py-1 text-xs text-muted-foreground">
            {latestBatchId || "No uploaded batch selected"}
          </code>
          <Button
            type="button"
            onClick={() => latestBatchId && applyMutation.mutate(latestBatchId)}
            disabled={!latestBatchId || applyMutation.isPending}
          >
            {applyMutation.isPending ? "Applying..." : "Apply"}
          </Button>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="default"
          onClick={() => {
            router.push(nextPath)
          }}
        >
          Back to Onboarding
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => skipMutation.mutate()}
          disabled={skipMutation.isPending}
        >
          {skipMutation.isPending ? "Skipping..." : "Skip for now"}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            void summaryQuery.refetch()
          }}
          disabled={summaryQuery.isFetching}
        >
          {summaryQuery.isFetching ? "Checking..." : "Retry Step5"}
        </Button>
      </div>
    </div>
  )
}

export default function SetupCoaPage() {
  return (
    <Suspense fallback={<div className="p-2 text-sm text-muted-foreground">Loading CoA setup...</div>}>
      <SetupCoaPageContent />
    </Suspense>
  )
}
