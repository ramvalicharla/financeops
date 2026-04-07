"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { z } from "zod"
import { useForm } from "react-hook-form"
import { CheckCircle2, ExternalLink, Loader2, ShieldCheck } from "lucide-react"
import { ConnectorGrid } from "@/components/sync/_components/ConnectorGrid"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  useActivateConnection,
  useCreateConnection,
  useGetConnection,
  useStartOAuth,
  useTestConnection,
} from "@/hooks/useSync"
import { CONNECTOR_IDS, CONNECTORS } from "@/lib/config/connectors"
import type { ConnectorType, ExternalConnection } from "@/types/sync"

const liveOauthConnectors = new Set<ConnectorType>(["ZOHO", "QUICKBOOKS"])

const backendConnectorMap: Record<ConnectorType, "zoho" | "quickbooks" | null> = {
  ZOHO: "zoho",
  TALLY: null,
  BUSY: null,
  MARG: null,
  MUNIM: null,
  QUICKBOOKS: "quickbooks",
  XERO: null,
  GENERIC_FILE: null,
}

const frontendConnectorMap: Record<string, ConnectorType> = {
  zoho: "ZOHO",
  quickbooks: "QUICKBOOKS",
}

const queryConnectorMap: Record<string, ConnectorType> = {
  zoho: "ZOHO",
  quickbooks: "QUICKBOOKS",
}

const formSchema = z.object({
  connector_type: z.enum(CONNECTOR_IDS),
  display_name: z.string().min(2, "Display name is required"),
  client_id: z.string().optional(),
  client_secret: z.string().optional(),
  organization_id: z.string().optional(),
  realm_id: z.string().optional(),
  use_sandbox: z.boolean(),
})

type ConnectFormValues = z.infer<typeof formSchema>

interface ConnectSourceFormProps {
  onSuccess?: () => void
}

const connectorSupportMessage =
  "This live ERP flow currently supports real Zoho Books and QuickBooks connections. Use Trial Balance upload for file-based activation."

const normalizeQueryConnector = (value: string | null): ConnectorType | null => {
  if (!value) {
    return null
  }
  return queryConnectorMap[value.trim().toLowerCase()] ?? null
}

export function ConnectSourceForm({ onSuccess }: ConnectSourceFormProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const createConnectionMutation = useCreateConnection()
  const loadConnectionMutation = useGetConnection()
  const startOAuthMutation = useStartOAuth()
  const testConnectionMutation = useTestConnection()
  const activateConnectionMutation = useActivateConnection()

  const searchConnector = normalizeQueryConnector(searchParams?.get("erp") ?? null)
  const callbackConnectionId = searchParams?.get("connection_id") ?? ""
  const oauthState = searchParams?.get("oauth") ?? ""

  const [connection, setConnection] = useState<ExternalConnection | null>(null)
  const [oauthAuthorized, setOauthAuthorized] = useState(false)
  const [stepError, setStepError] = useState<string | null>(null)
  const [stepInfo, setStepInfo] = useState<string | null>(null)

  const {
    watch,
    setValue,
    handleSubmit,
    formState: { errors },
  } = useForm<ConnectFormValues>({
    defaultValues: {
      connector_type: searchConnector ?? "ZOHO",
      display_name: "",
      client_id: "",
      client_secret: "",
      organization_id: "",
      realm_id: "",
      use_sandbox: true,
    },
  })

  const connectorType = watch("connector_type")
  const selectedConnector = CONNECTORS.find((connectorItem) => connectorItem.id === connectorType)
  const supportsLiveOauth = liveOauthConnectors.has(connectorType)

  useEffect(() => {
    if (!watch("display_name")) {
      setValue("display_name", selectedConnector?.name ?? "")
    }
  }, [selectedConnector, setValue, watch])

  useEffect(() => {
    if (!callbackConnectionId) {
      if (oauthState !== "connected") {
        setOauthAuthorized(false)
      }
      return
    }

    let cancelled = false
    void loadConnectionMutation
      .mutateAsync(callbackConnectionId)
      .then((loadedConnection) => {
        if (cancelled) {
          return
        }
        setConnection(loadedConnection)
        setValue(
          "connector_type",
          frontendConnectorMap[String(loadedConnection.connector_type).toLowerCase()] ?? "ZOHO",
        )
        setValue("display_name", loadedConnection.connection_name)
        setOauthAuthorized(oauthState === "connected")
        setStepInfo(
          oauthState === "connected"
            ? "OAuth authorization completed. Run the verification step below to finish connecting this source."
            : null,
        )
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        setStepError(
          error instanceof Error ? error.message : "Failed to load connection details.",
        )
      })

    return () => {
      cancelled = true
    }
  }, [callbackConnectionId, loadConnectionMutation, oauthState, setValue])

  const draftConnectionId = connection?.id ?? null
  const isActiveConnection = connection?.connection_status === "active"

  const ensureLiveConnector = (): boolean => {
    if (supportsLiveOauth) {
      return true
    }
    setStepError(connectorSupportMessage)
    return false
  }

  const buildCreatePayload = (values: ConnectFormValues) => {
    const backendConnector = backendConnectorMap[values.connector_type]
    if (!backendConnector) {
      throw new Error(connectorSupportMessage)
    }

    return {
      connector_type: backendConnector,
      connection_code: `${backendConnector}-${crypto.randomUUID().slice(0, 8)}`,
      connection_name: values.display_name.trim(),
      client_id: values.client_id?.trim() ?? "",
      client_secret: values.client_secret?.trim() ?? "",
      organization_id: values.organization_id?.trim() || undefined,
      realm_id: values.realm_id?.trim() || undefined,
      use_sandbox: values.connector_type === "QUICKBOOKS" ? values.use_sandbox : undefined,
    }
  }

  const createDraftConnection = handleSubmit(async (values) => {
    setStepError(null)
    setStepInfo(null)
    if (!ensureLiveConnector()) {
      return
    }
    const parsed = formSchema.safeParse(values)
    if (!parsed.success) {
      setStepError(parsed.error.issues[0]?.message ?? "Invalid connection details.")
      return
    }

    try {
      const createdConnection = await createConnectionMutation.mutateAsync(
        buildCreatePayload(parsed.data),
      )
      setConnection(createdConnection)
      setOauthAuthorized(false)
      setStepInfo(
        "Draft connection created. Continue with OAuth authorization before testing the source.",
      )
    } catch (error) {
      setStepError(
        error instanceof Error ? error.message : "Unable to create source connection.",
      )
    }
  })

  const beginOAuth = async () => {
    setStepError(null)
    setStepInfo(null)
    if (!ensureLiveConnector()) {
      return
    }
    if (!draftConnectionId) {
      setStepError("Create the connection draft before starting OAuth.")
      return
    }

    try {
      const redirectUri = `${window.location.origin}/sync/connect/callback?connection_id=${encodeURIComponent(draftConnectionId)}`
      const result = await startOAuthMutation.mutateAsync({
        connectionId: draftConnectionId,
        redirectUri,
      })
      window.location.assign(result.authorization_url)
    } catch (error) {
      setStepError(
        error instanceof Error ? error.message : "Unable to start OAuth authorization.",
      )
    }
  }

  const verifyAndActivate = async () => {
    setStepError(null)
    setStepInfo(null)
    if (!draftConnectionId) {
      setStepError("Create and authorize a connection before testing it.")
      return
    }

    try {
      await testConnectionMutation.mutateAsync(draftConnectionId)
      const activeConnection = await activateConnectionMutation.mutateAsync(draftConnectionId)
      setConnection(activeConnection)
      setOauthAuthorized(true)
      setStepInfo("Connection verified and activated successfully.")
      onSuccess?.()
      router.push(`/sync?connection_id=${encodeURIComponent(activeConnection.id)}`)
    } catch (error) {
      setStepError(
        error instanceof Error ? error.message : "Connection verification failed.",
      )
    }
  }

  const formDisabled =
    createConnectionMutation.isPending ||
    startOAuthMutation.isPending ||
    testConnectionMutation.isPending ||
    activateConnectionMutation.isPending

  const currentStatusLabel = isActiveConnection
    ? "Active and verified"
    : oauthAuthorized
      ? "OAuth authorized"
      : draftConnectionId
        ? "Draft created"
        : "Not connected"

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-card p-5">
        <ConnectorGrid
          selectedConnectorId={connectorType}
          onSelect={(connectorId) => {
            setValue("connector_type", connectorId)
            setStepError(null)
            setStepInfo(null)
          }}
        />
      </div>

      <div className="rounded-lg border border-border bg-card p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Connection details</h2>
            <p className="text-sm text-muted-foreground">
              Live ERP authorization is available for Zoho Books and QuickBooks in this flow.
            </p>
          </div>
          <span
            className={
              isActiveConnection
                ? "inline-flex rounded-full bg-[hsl(var(--brand-success)/0.2)] px-2 py-1 text-xs font-medium text-[hsl(var(--brand-success))]"
                : "inline-flex rounded-full bg-muted px-2 py-1 text-xs font-medium text-muted-foreground"
            }
          >
            {currentStatusLabel}
          </span>
        </div>

        {!supportsLiveOauth ? (
          <div className="rounded-md border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
            {connectorSupportMessage}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <FormField
              id="display-name"
              label="Display name"
              error={errors.display_name?.message}
              required
            >
              <Input
                value={watch("display_name")}
                onChange={(event) => setValue("display_name", event.target.value)}
                disabled={formDisabled}
              />
            </FormField>

            <FormField
              id="client-id"
              label="Client ID"
              error={errors.client_id?.message}
              required
            >
              <Input
                value={watch("client_id") ?? ""}
                onChange={(event) => setValue("client_id", event.target.value)}
                disabled={formDisabled}
              />
            </FormField>

            <FormField
              id="client-secret"
              label="Client Secret"
              error={errors.client_secret?.message}
              required
            >
              <Input
                type="password"
                value={watch("client_secret") ?? ""}
                onChange={(event) => setValue("client_secret", event.target.value)}
                disabled={formDisabled}
              />
            </FormField>

            {connectorType === "ZOHO" ? (
              <FormField
                id="organization-id"
                label="Zoho Organization ID"
                hint="Required to test and use Zoho Books connections."
                required
              >
                <Input
                  value={watch("organization_id") ?? ""}
                  onChange={(event) => setValue("organization_id", event.target.value)}
                  disabled={formDisabled}
                />
              </FormField>
            ) : (
              <FormField
                id="realm-id"
                label="QuickBooks Realm ID"
                hint="Optional before OAuth. QuickBooks usually returns this during authorization."
              >
                <Input
                  value={watch("realm_id") ?? ""}
                  onChange={(event) => setValue("realm_id", event.target.value)}
                  disabled={formDisabled}
                />
              </FormField>
            )}

            {connectorType === "QUICKBOOKS" ? (
              <div className="flex items-center gap-2 pt-7">
                <input
                  id="use-sandbox"
                  type="checkbox"
                  checked={watch("use_sandbox")}
                  onChange={(event) => setValue("use_sandbox", event.target.checked)}
                  disabled={formDisabled}
                />
                <label htmlFor="use-sandbox" className="text-sm text-foreground">
                  Use QuickBooks sandbox environment
                </label>
              </div>
            ) : null}
          </div>
        )}

        {stepError ? (
          <div className="mt-4 rounded-md border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] px-4 py-3 text-sm text-[hsl(var(--brand-danger))]">
            {stepError}
          </div>
        ) : null}

        {stepInfo ? (
          <div className="mt-4 rounded-md border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
            {stepInfo}
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-3">
          <Button
            type="button"
            onClick={() => void createDraftConnection()}
            disabled={!supportsLiveOauth || formDisabled || Boolean(draftConnectionId)}
          >
            {createConnectionMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating draft...
              </>
            ) : (
              "Create draft connection"
            )}
          </Button>

          <Button
            type="button"
            variant="outline"
            onClick={() => void beginOAuth()}
            disabled={!draftConnectionId || formDisabled || isActiveConnection}
          >
            {startOAuthMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Starting OAuth...
              </>
            ) : (
              <>
                <ExternalLink className="h-4 w-4" />
                Start OAuth
              </>
            )}
          </Button>

          <Button
            type="button"
            variant="secondary"
            onClick={() => void verifyAndActivate()}
            disabled={!draftConnectionId || !oauthAuthorized || formDisabled || isActiveConnection}
          >
            {testConnectionMutation.isPending || activateConnectionMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Verifying...
              </>
            ) : (
              <>
                <ShieldCheck className="h-4 w-4" />
                Test and activate
              </>
            )}
          </Button>
        </div>

        <div className="mt-5 rounded-md border border-border bg-muted/10 px-4 py-3 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">Connection rules</p>
          <ul className="mt-2 space-y-1">
            <li>Zoho requires Client ID, Client Secret, and Organization ID before it can be tested.</li>
            <li>QuickBooks requires Client ID and Client Secret, then OAuth will return the Realm ID.</li>
            <li>A source is only treated as connected after OAuth succeeds and the backend test passes.</li>
          </ul>
          {isActiveConnection ? (
            <p className="mt-3 inline-flex items-center gap-2 text-[hsl(var(--brand-success))]">
              <CheckCircle2 className="h-4 w-4" />
              This source is active and ready for sync.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
