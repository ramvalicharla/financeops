"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { z } from "zod"
import { useForm } from "react-hook-form"
import { CheckCircle2, Loader2, RefreshCw } from "lucide-react"
import { ConnectorConfigForm } from "@/components/sync/_components/ConnectorConfigForm"
import { ConnectorGrid } from "@/components/sync/_components/ConnectorGrid"
import { ConnectorStatusBadge } from "@/components/sync/_components/ConnectorStatusBadge"
import { Button } from "@/components/ui/button"
import { useCreateConnection, useTestConnection, useTriggerSync } from "@/hooks/useSync"
import {
  CONNECTORS,
  CONNECTOR_DATASETS,
  CONNECTOR_IDS,
  DATASET_TYPES,
} from "@/lib/config/connectors"
import { cn } from "@/lib/utils"
import type { ConnectorType, DatasetType } from "@/types/sync"

type WizardStep =
  | "connector"
  | "configure"
  | "test"
  | "datasets"
  | "schedule"
  | "confirm"

const stepOrder: WizardStep[] = [
  "connector",
  "configure",
  "test",
  "datasets",
  "schedule",
  "confirm",
]

const scheduleModes = ["manual", "daily", "weekly"] as const
type ScheduleMode = (typeof scheduleModes)[number]

const canonicalFieldOptions = [
  "date",
  "voucher_number",
  "account_code",
  "account_name",
  "counterparty_name",
  "description",
  "amount",
  "tax_amount",
  "currency",
] as const

const formSchema = z.object({
  connector_type: z.enum(CONNECTOR_IDS),
  display_name: z.string().min(2, "Display name is required"),
  datasets: z.array(z.enum(DATASET_TYPES)).min(1, "Select at least one dataset"),
  schedule_mode: z.enum(scheduleModes),
  schedule_time: z.string().optional(),
  schedule_day_of_week: z.string().optional(),
})

type ConnectFormValues = z.infer<typeof formSchema>

interface ConnectSourceFormProps {
  onSuccess?: () => void
}

const parseColumnsFromFile = async (file: File): Promise<string[]> => {
  const extension = file.name.split(".").at(-1)?.toLowerCase()
  if (!extension || extension === "xlsx") {
    return []
  }
  const rawText = await file.text()
  if (!rawText.trim()) {
    return []
  }
  if (extension === "csv") {
    const header = rawText.split(/\r?\n/)[0] ?? ""
    return header
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean)
  }
  if (extension === "json") {
    try {
      const parsed =
        JSON.parse(rawText) as
          | Record<string, unknown>
          | Array<Record<string, unknown>>
      if (Array.isArray(parsed)) {
        return Object.keys(parsed[0] ?? {})
      }
      return Object.keys(parsed)
    } catch {
      return []
    }
  }
  if (extension === "xml") {
    const fields = Array.from(rawText.matchAll(/<([a-zA-Z_][\w.-]*)>/g))
      .map((match) => match[1])
      .filter((value) => !value.startsWith("?"))
    return Array.from(new Set(fields)).slice(0, 25)
  }
  return []
}

export function ConnectSourceForm({ onSuccess }: ConnectSourceFormProps) {
  const router = useRouter()
  const [currentStep, setCurrentStep] = useState<WizardStep>("connector")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [columnMappings, setColumnMappings] = useState<
    Array<{ source_column: string; canonical_field: string }>
  >([])
  const [stepError, setStepError] = useState<string | null>(null)
  const [testPassed, setTestPassed] = useState(false)
  const [oauthConnected, setOauthConnected] = useState(false)
  const createConnectionMutation = useCreateConnection()
  const triggerSyncMutation = useTriggerSync()
  const testConnectionMutation = useTestConnection()

  const {
    watch,
    setValue,
    getValues,
    handleSubmit,
    formState: { errors },
  } = useForm<ConnectFormValues>({
    defaultValues: {
      connector_type: "ZOHO",
      display_name: "",
      datasets: [],
      schedule_mode: "manual",
      schedule_time: "09:00",
      schedule_day_of_week: "monday",
    },
  })

  const connectorType = watch("connector_type")
  const scheduleMode = watch("schedule_mode")
  const selectedDatasets = watch("datasets")
  const selectedConnector = CONNECTORS.find((connector) => connector.id === connectorType)
  const supportedDatasets = [...CONNECTOR_DATASETS[connectorType]] as DatasetType[]
  const isOAuthConnector = selectedConnector?.category === "OAuth"

  useEffect(() => {
    const nextDatasets = [...CONNECTOR_DATASETS[connectorType]] as DatasetType[]
    setValue("datasets", nextDatasets)
    if (!getValues("display_name")) {
      setValue("display_name", selectedConnector?.name ?? "")
    }
    setTestPassed(false)
    setOauthConnected(false)
    setStepError(null)
  }, [connectorType, getValues, selectedConnector, setValue])

  useEffect(() => {
    if (!selectedFile) {
      setColumnMappings([])
      return
    }
    void parseColumnsFromFile(selectedFile).then((columns) => {
      const mappings = columns.map((column) => ({
        source_column: column,
        canonical_field: canonicalFieldOptions[0],
      }))
      setColumnMappings(mappings)
    })
  }, [selectedFile])

  const stepIndex = stepOrder.indexOf(currentStep)

  const canProceed = (): boolean => {
    setStepError(null)
    if (currentStep === "connector") {
      return true
    }
    if (currentStep === "configure") {
      if (isOAuthConnector) {
        if (!oauthConnected) {
          setStepError("OAuth connection must be completed before continuing.")
          return false
        }
      } else if (!selectedFile) {
        setStepError("Upload a file before continuing.")
        return false
      }
      return true
    }
    if (currentStep === "test") {
      if (!testPassed) {
        setStepError("Connection test must pass before continuing.")
        return false
      }
      return true
    }
    if (currentStep === "datasets") {
      if (!selectedDatasets.length) {
        setStepError("Select at least one dataset.")
        return false
      }
      return true
    }
    if (currentStep === "schedule") {
      if (scheduleMode !== "manual" && !watch("schedule_time")) {
        setStepError("Select a schedule time.")
        return false
      }
      if (scheduleMode === "weekly" && !watch("schedule_day_of_week")) {
        setStepError("Select a day of week.")
        return false
      }
      return true
    }
    return true
  }

  const goNext = () => {
    if (!canProceed()) {
      return
    }
    setCurrentStep(stepOrder[Math.min(stepIndex + 1, stepOrder.length - 1)] ?? "confirm")
  }

  const goBack = () => {
    setStepError(null)
    setCurrentStep(stepOrder[Math.max(stepIndex - 1, 0)] ?? "connector")
  }

  const runTestConnection = async () => {
    setStepError(null)
    try {
      const response = await testConnectionMutation.mutateAsync({
        connector_type: connectorType,
        display_name: getValues("display_name"),
        file_name: selectedFile?.name,
      })
      if (response.success) {
        setTestPassed(true)
      } else {
        setTestPassed(false)
        setStepError(response.message ?? "Connection test failed.")
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Connection test failed."
      setTestPassed(false)
      setStepError(message)
    }
  }

  const onSubmit = handleSubmit(async (values) => {
    const parsed = formSchema.safeParse(values)
    if (!parsed.success) {
      setStepError(parsed.error.issues[0]?.message ?? "Invalid form configuration.")
      return
    }
    if (!testPassed) {
      setStepError("Connection test must pass before saving.")
      return
    }

    try {
      const connection = await createConnectionMutation.mutateAsync({
        connector_type: parsed.data.connector_type,
        display_name: parsed.data.display_name,
        datasets: parsed.data.datasets,
        schedule_mode: parsed.data.schedule_mode,
        schedule_time: parsed.data.schedule_time,
        schedule_day_of_week: parsed.data.schedule_day_of_week,
        oauth_connected: oauthConnected,
        mapping: columnMappings,
      })

      await triggerSyncMutation.mutateAsync({
        connectionId: connection.id,
        datasetTypes: parsed.data.datasets,
      })
      onSuccess?.()
      router.push("/sync")
    } catch (error) {
      setStepError(
        error instanceof Error
          ? error.message
          : "Unable to create source connection.",
      )
    }
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {stepOrder.map((step, index) => (
          <span
            key={step}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium uppercase tracking-wide",
              step === currentStep
                ? "bg-[hsl(var(--brand-primary)/0.2)] text-[hsl(var(--brand-primary))]"
                : "bg-muted text-muted-foreground",
            )}
          >
            {index + 1}. {step}
          </span>
        ))}
      </div>

      <div className="rounded-lg border border-border bg-card p-5">
        {currentStep === "connector" ? (
          <ConnectorGrid
            selectedConnectorId={connectorType}
            onSelect={(connectorId) => setValue("connector_type", connectorId)}
          />
        ) : null}

        {currentStep === "configure" ? (
          <ConnectorConfigForm
            canonicalFieldOptions={canonicalFieldOptions}
            columnMappings={columnMappings}
            displayName={watch("display_name")}
            displayNameError={errors.display_name?.message}
            fileError={stepError}
            isOAuthConnector={Boolean(isOAuthConnector)}
            oauthConnected={oauthConnected}
            selectedConnector={selectedConnector}
            selectedFile={selectedFile}
            onConnectOAuth={() => setOauthConnected(true)}
            onDisplayNameChange={(value) => setValue("display_name", value)}
            onFileSelected={(file) => {
              setSelectedFile(file)
              setStepError(null)
            }}
            onMappingChange={(index, canonicalField) => {
              setColumnMappings((previous) =>
                previous.map((value, mapIndex) =>
                  mapIndex === index
                    ? { ...value, canonical_field: canonicalField }
                    : value,
                ),
              )
            }}
          />
        ) : null}

        {currentStep === "test" ? (
          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Test connection</h2>
            <Button
              className="gap-2"
              disabled={testConnectionMutation.isPending}
              onClick={runTestConnection}
              type="button"
            >
              {testConnectionMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Test Connection
            </Button>
            {testPassed ? (
              <div className="inline-flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-[hsl(var(--brand-success))]" />
                <ConnectorStatusBadge label="Connection successful" status="success" />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Run a connection test before continuing.
              </p>
            )}
          </section>
        ) : null}

        {currentStep === "datasets" ? (
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">
                Choose datasets
              </h2>
              <Button
                size="sm"
                type="button"
                variant="outline"
                onClick={() => setValue("datasets", supportedDatasets)}
              >
                Select all
              </Button>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {supportedDatasets.map((dataset) => {
                const checked = selectedDatasets.includes(dataset)
                return (
                  <label
                    key={dataset}
                    className="flex items-center gap-2 rounded border border-border px-3 py-2 text-sm text-foreground"
                  >
                    <input
                      checked={checked}
                      onChange={() => {
                        if (checked) {
                          setValue(
                            "datasets",
                            selectedDatasets.filter((item) => item !== dataset),
                          )
                        } else {
                          setValue("datasets", [...selectedDatasets, dataset])
                        }
                      }}
                      type="checkbox"
                    />
                    {dataset.replaceAll("_", " ")}
                  </label>
                )
              })}
            </div>
          </section>
        ) : null}

        {currentStep === "schedule" ? (
          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Schedule</h2>
            <div className="space-y-2">
              {scheduleModes.map((mode) => (
                <label
                  key={mode}
                  className="flex items-center gap-2 rounded border border-border px-3 py-2 text-sm text-foreground"
                >
                  <input
                    checked={scheduleMode === mode}
                    onChange={() => setValue("schedule_mode", mode)}
                    type="radio"
                  />
                  {mode === "manual"
                    ? "Manual only"
                    : mode === "daily"
                      ? "Daily"
                      : "Weekly"}
                </label>
              ))}
            </div>
            {scheduleMode !== "manual" ? (
              <div className="space-y-2">
                <label className="text-sm text-foreground" htmlFor="schedule-time">
                  Time
                </label>
                <input
                  id="schedule-time"
                  className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground"
                  type="time"
                  value={watch("schedule_time") ?? ""}
                  onChange={(event) => setValue("schedule_time", event.target.value)}
                />
              </div>
            ) : null}
            {scheduleMode === "weekly" ? (
              <div className="space-y-2">
                <label className="text-sm text-foreground" htmlFor="schedule-day">
                  Day of week
                </label>
                <select
                  id="schedule-day"
                  className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground"
                  value={watch("schedule_day_of_week") ?? "monday"}
                  onChange={(event) =>
                    setValue("schedule_day_of_week", event.target.value)
                  }
                >
                  {[
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                  ].map((day) => (
                    <option key={day} value={day}>
                      {day[0]?.toUpperCase()}
                      {day.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </section>
        ) : null}

        {currentStep === "confirm" ? (
          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Confirm</h2>
            <div className="rounded-md border border-border bg-background p-4 text-sm text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">Connector:</span>{" "}
                {connectorType}
              </p>
              <p>
                <span className="font-medium text-foreground">Display name:</span>{" "}
                {watch("display_name")}
              </p>
              <p>
                <span className="font-medium text-foreground">Datasets:</span>{" "}
                {selectedDatasets.map((dataset) => dataset.replaceAll("_", " ")).join(", ")}
              </p>
              <p>
                <span className="font-medium text-foreground">Schedule:</span>{" "}
                {scheduleMode}
                {scheduleMode !== "manual" && watch("schedule_time")
                  ? ` @ ${watch("schedule_time")}`
                  : ""}
                {scheduleMode === "weekly" && watch("schedule_day_of_week")
                  ? ` (${watch("schedule_day_of_week")})`
                  : ""}
              </p>
            </div>
            <Button
              className="gap-2"
              disabled={
                createConnectionMutation.isPending || triggerSyncMutation.isPending
              }
              onClick={() => void onSubmit()}
              type="button"
            >
              {createConnectionMutation.isPending || triggerSyncMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              Save and Sync Now
            </Button>
          </section>
        ) : null}
      </div>

      {stepError ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {stepError}
        </p>
      ) : null}

      <div className="flex items-center justify-between">
        <Button
          disabled={stepIndex === 0}
          onClick={goBack}
          type="button"
          variant="outline"
        >
          Back
        </Button>
        <Button
          disabled={stepIndex === stepOrder.length - 1}
          onClick={goNext}
          type="button"
        >
          Next
        </Button>
      </div>
    </div>
  )
}
