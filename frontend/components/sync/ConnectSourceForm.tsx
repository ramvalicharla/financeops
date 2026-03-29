"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { z } from "zod"
import { useForm } from "react-hook-form"
import {
  CheckCircle2,
  Database,
  FileUp,
  Link as LinkIcon,
  Loader2,
  RefreshCw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { FileUploadZone } from "@/components/sync/FileUploadZone"
import { useCreateConnection, useTestConnection, useTriggerSync } from "@/hooks/useSync"
import type { ConnectorType, DatasetType } from "@/types/sync"
import { cn } from "@/lib/utils"

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

const connectorCards: Array<{
  connector: ConnectorType
  label: string
  description: string
  oauth: boolean
  icon: typeof Database
}> = [
  {
    connector: "ZOHO",
    label: "Zoho",
    description: "OAuth connector",
    oauth: true,
    icon: LinkIcon,
  },
  {
    connector: "TALLY",
    label: "Tally",
    description: "File/XML import",
    oauth: false,
    icon: FileUp,
  },
  {
    connector: "BUSY",
    label: "Busy",
    description: "File/API key",
    oauth: false,
    icon: FileUp,
  },
  {
    connector: "MARG",
    label: "Marg",
    description: "File import",
    oauth: false,
    icon: FileUp,
  },
  {
    connector: "MUNIM",
    label: "Munim",
    description: "File import",
    oauth: false,
    icon: FileUp,
  },
  {
    connector: "QUICKBOOKS",
    label: "QuickBooks",
    description: "OAuth connector",
    oauth: true,
    icon: LinkIcon,
  },
  {
    connector: "XERO",
    label: "Xero",
    description: "OAuth connector",
    oauth: true,
    icon: LinkIcon,
  },
  {
    connector: "GENERIC_FILE",
    label: "Upload File",
    description: "CSV/JSON/XML/XLSX",
    oauth: false,
    icon: FileUp,
  },
]

const connectorDatasets: Record<ConnectorType, DatasetType[]> = {
  ZOHO: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
    "FIXED_ASSET_REGISTER",
  ],
  TALLY: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "BANK_STATEMENT",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
  ],
  BUSY: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "BANK_STATEMENT",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
  ],
  MARG: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
  ],
  MUNIM: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
  ],
  QUICKBOOKS: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
  ],
  XERO: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
  ],
  GENERIC_FILE: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "PAYROLL_SUMMARY",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
    "FIXED_ASSET_REGISTER",
  ],
}

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
]

const formSchema = z.object({
  connector_type: z.enum([
    "ZOHO",
    "TALLY",
    "BUSY",
    "MARG",
    "MUNIM",
    "QUICKBOOKS",
    "XERO",
    "GENERIC_FILE",
  ]),
  display_name: z.string().min(2, "Display name is required"),
  datasets: z.array(z.enum([
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "PAYROLL_SUMMARY",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
    "FIXED_ASSET_REGISTER",
  ])).min(1, "Select at least one dataset"),
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
      const parsed = JSON.parse(rawText) as Record<string, unknown> | Array<Record<string, unknown>>
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
  const supportedDatasets = connectorDatasets[connectorType]
  const isOAuthConnector = connectorCards.find(
    (card) => card.connector === connectorType,
  )?.oauth

  useEffect(() => {
    const nextDatasets = connectorDatasets[connectorType]
    setValue("datasets", nextDatasets)
    if (!getValues("display_name")) {
      const card = connectorCards.find((item) => item.connector === connectorType)
      setValue("display_name", card?.label ?? "")
    }
    setTestPassed(false)
    setOauthConnected(false)
    setStepError(null)
  }, [connectorType, getValues, setValue])

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
          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Choose connector</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {connectorCards.map((card) => {
                const Icon = card.icon
                const selected = connectorType === card.connector
                return (
                  <button
                    key={card.connector}
                    className={cn(
                      "rounded-lg border p-4 text-left transition",
                      selected
                        ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.1)]"
                        : "border-border hover:border-[hsl(var(--brand-primary)/0.5)]",
                    )}
                    onClick={() => setValue("connector_type", card.connector)}
                    type="button"
                  >
                    <Icon className="mb-2 h-5 w-5 text-foreground" />
                    <p className="font-medium text-foreground">{card.label}</p>
                    <p className="text-xs text-muted-foreground">{card.description}</p>
                  </button>
                )
              })}
            </div>
          </section>
        ) : null}

        {currentStep === "configure" ? (
          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Configure connection</h2>
            <div className="space-y-2">
              <label className="text-sm text-foreground" htmlFor="display-name">
                Display name
              </label>
              <Input
                id="display-name"
                value={watch("display_name")}
                onChange={(event) => setValue("display_name", event.target.value)}
              />
              {errors.display_name ? (
                <p className="text-sm text-destructive">{errors.display_name.message}</p>
              ) : null}
            </div>
            {isOAuthConnector ? (
              <div className="rounded-md border border-border p-4">
                <Button
                  type="button"
                  onClick={() => setOauthConnected(true)}
                  className="gap-2"
                >
                  <LinkIcon className="h-4 w-4" />
                  Connect with {connectorType}
                </Button>
                {oauthConnected ? (
                  <p className="mt-2 text-sm text-[hsl(var(--brand-success))]">
                    Connected successfully.
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Complete OAuth authorization to continue.
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <FileUploadZone
                  error={stepError}
                  file={selectedFile}
                  onFileSelected={(file) => {
                    setSelectedFile(file)
                    setStepError(null)
                  }}
                />
                {columnMappings.length ? (
                  <div className="overflow-x-auto rounded-md border border-border">
                    <table className="w-full min-w-[540px] text-sm">
                      <thead>
                        <tr className="bg-muted/30">
                          <th className="px-3 py-2 text-left font-medium text-foreground">
                            Source Column
                          </th>
                          <th className="px-3 py-2 text-left font-medium text-foreground">
                            Mapping
                          </th>
                          <th className="px-3 py-2 text-left font-medium text-foreground">
                            Canonical Field
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {columnMappings.map((mapping, index) => (
                          <tr key={mapping.source_column} className="border-t border-border">
                            <td className="px-3 py-2 text-muted-foreground">
                              {mapping.source_column}
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">→</td>
                            <td className="px-3 py-2">
                              <select
                                className="w-full rounded border border-border bg-background px-2 py-1 text-foreground"
                                value={mapping.canonical_field}
                                onChange={(event) => {
                                  setColumnMappings((previous) =>
                                    previous.map((value, mapIndex) =>
                                      mapIndex === index
                                        ? {
                                            ...value,
                                            canonical_field: event.target.value,
                                          }
                                        : value,
                                    ),
                                  )
                                }}
                              >
                                {canonicalFieldOptions.map((field) => (
                                  <option key={field} value={field}>
                                    {field}
                                  </option>
                                ))}
                              </select>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            )}
          </section>
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
              <p className="inline-flex items-center gap-2 text-sm text-[hsl(var(--brand-success))]">
                <CheckCircle2 className="h-4 w-4" />
                Connection successful
              </p>
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
                <Input
                  id="schedule-time"
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
