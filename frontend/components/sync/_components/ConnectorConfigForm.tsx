"use client"

import { Link as LinkIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"
import { FileUploadZone } from "@/components/sync/FileUploadZone"
import type { ConnectorDefinition } from "@/lib/config/connectors"
import { ConnectorStatusBadge } from "./ConnectorStatusBadge"

interface ColumnMapping {
  source_column: string
  canonical_field: string
}

interface ConnectorConfigFormProps {
  columnMappings: ColumnMapping[]
  displayName: string
  displayNameError?: string
  fileError: string | null
  isOAuthConnector: boolean
  oauthConnected: boolean
  selectedConnector: ConnectorDefinition | undefined
  selectedFile: File | null
  canonicalFieldOptions: readonly string[]
  onConnectOAuth: () => void
  onDisplayNameChange: (value: string) => void
  onFileSelected: (file: File | null) => void
  onMappingChange: (index: number, canonicalField: string) => void
}

export function ConnectorConfigForm({
  canonicalFieldOptions,
  columnMappings,
  displayName,
  displayNameError,
  fileError,
  isOAuthConnector,
  oauthConnected,
  selectedConnector,
  selectedFile,
  onConnectOAuth,
  onDisplayNameChange,
  onFileSelected,
  onMappingChange,
}: ConnectorConfigFormProps) {
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">Configure connection</h2>
      <FormField id="display-name" label="Display name" error={displayNameError}>
        <Input
          id="display-name"
          value={displayName}
          onChange={(event) => onDisplayNameChange(event.target.value)}
        />
      </FormField>

      {isOAuthConnector ? (
        <div className="rounded-md border border-border p-4">
          <Button type="button" onClick={onConnectOAuth} className="gap-2">
            <LinkIcon className="h-4 w-4" />
            Connect with {selectedConnector?.name ?? "Connector"}
          </Button>
          <div className="mt-2">
            {oauthConnected ? (
              <ConnectorStatusBadge label="Connected successfully" status="success" />
            ) : (
              <p className="text-sm text-muted-foreground">
                Complete OAuth authorization to continue.
              </p>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <FileUploadZone
            error={fileError}
            file={selectedFile}
            onFileSelected={onFileSelected}
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
                      <td className="px-3 py-2 text-muted-foreground">{"->"}</td>
                      <td className="px-3 py-2">
                        <select
                          className="w-full rounded border border-border bg-background px-2 py-1 text-foreground"
                          value={mapping.canonical_field}
                          onChange={(event) =>
                            onMappingChange(index, event.target.value)
                          }
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
  )
}
