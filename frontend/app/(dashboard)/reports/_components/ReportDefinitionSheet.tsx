"use client"

import { Loader2 } from "lucide-react"
import { Sheet } from "@/components/ui/Sheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SortDirection } from "@/lib/types/report-builder"
import {
  type ReportFormState,
  exportFormatOptions,
} from "../_hooks/useReports"

interface ReportDefinitionSheetProps {
  formState: ReportFormState
  groupedMetrics: Array<
    [string, Array<{ engine: string; key: string; label: string }>]
  >
  loadingMetrics: boolean
  metricByKey: Map<string, { key: string; label: string }>
  open: boolean
  savingDefinition: boolean
  sheetError: string | null
  step: number
  title: string
  onAddEntityIds: () => void
  onAddTags: () => void
  onClose: () => void
  onSave: () => void
  onSetForm: (updates: Partial<ReportFormState>) => void
  onSetStep: (step: number | ((previous: number) => number)) => void
  onValidateStep: (step: number) => boolean
}

export function ReportDefinitionSheet({
  formState,
  groupedMetrics,
  loadingMetrics,
  metricByKey,
  open,
  savingDefinition,
  sheetError,
  step,
  title,
  onAddEntityIds,
  onAddTags,
  onClose,
  onSave,
  onSetForm,
  onSetStep,
  onValidateStep,
}: ReportDefinitionSheetProps) {
  return (
    <Sheet
      open={open}
      onClose={savingDefinition ? () => undefined : onClose}
      title={title}
      width="max-w-2xl"
    >
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {[1, 2, 3, 4].map((item) => (
            <span
              key={item}
              className={[
                "rounded-full border px-2 py-1",
                step === item
                  ? "border-[hsl(var(--brand-primary))] text-foreground"
                  : "border-border",
              ].join(" ")}
            >
              Step {item}
            </span>
          ))}
        </div>

        {step === 1 ? (
          <>
            <div className="space-y-1">
              <label className="text-sm text-foreground" htmlFor="report-name">
                Name
              </label>
              <Input
                id="report-name"
                value={formState.name}
                onChange={(event) => onSetForm({ name: event.target.value })}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-foreground" htmlFor="report-description">
                Description
              </label>
              <textarea
                id="report-description"
                className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                value={formState.description}
                onChange={(event) => onSetForm({ description: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <p className="text-sm text-foreground">Export Formats</p>
              <div className="grid gap-2 sm:grid-cols-3">
                {exportFormatOptions.map((format) => (
                  <label
                    key={format}
                    className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm text-muted-foreground"
                  >
                    <input
                      type="checkbox"
                      checked={formState.exportFormats.includes(format)}
                      onChange={(event) =>
                        onSetForm({
                          exportFormats: event.target.checked
                            ? Array.from(new Set([...formState.exportFormats, format]))
                            : formState.exportFormats.filter((item) => item !== format),
                        })
                      }
                    />
                    {format}
                  </label>
                ))}
              </div>
            </div>
          </>
        ) : null}

        {step === 2 ? (
          <>
            {loadingMetrics ? (
              <div className="h-24 animate-pulse rounded-md border border-border bg-muted/20" />
            ) : null}
            <div className="flex flex-wrap gap-2">
              {formState.metricKeys.map((metricKey) => (
                <span
                  key={metricKey}
                  className="inline-flex items-center gap-2 rounded-full border border-border px-2 py-1 text-xs text-muted-foreground"
                >
                  {metricByKey.get(metricKey)?.label ?? metricKey}
                  <button
                    type="button"
                    className="text-foreground"
                    onClick={() =>
                      onSetForm({
                        metricKeys: formState.metricKeys.filter(
                          (item) => item !== metricKey,
                        ),
                        groupBy: formState.groupBy.filter((item) => item !== metricKey),
                        sortField:
                          formState.sortField === metricKey ? "" : formState.sortField,
                      })
                    }
                    aria-label={`Remove ${metricByKey.get(metricKey)?.label ?? metricKey}`}
                  >
                    <span aria-hidden="true">×</span>
                  </button>
                </span>
              ))}
            </div>
            {groupedMetrics.map(([engine, engineMetrics]) => (
              <details
                key={engine}
                className="rounded-md border border-border bg-background/30"
                open
              >
                <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-foreground">
                  {engine}
                </summary>
                <div className="space-y-2 border-t border-border px-3 py-3">
                  {engineMetrics.map((metric) => (
                    <label
                      key={metric.key}
                      className="flex items-center gap-2 text-sm text-muted-foreground"
                    >
                      <input
                        type="checkbox"
                        checked={formState.metricKeys.includes(metric.key)}
                        onChange={(event) =>
                          onSetForm({
                            metricKeys: event.target.checked
                              ? Array.from(
                                  new Set([...formState.metricKeys, metric.key]),
                                )
                              : formState.metricKeys.filter(
                                  (item) => item !== metric.key,
                                ),
                          })
                        }
                      />
                      <span className="text-foreground">{metric.label}</span>
                      <span className="text-xs">({metric.key})</span>
                    </label>
                  ))}
                </div>
              </details>
            ))}
          </>
        ) : null}

        {step === 3 ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="period-start">
                  Period Start
                </label>
                <Input
                  id="period-start"
                  type="date"
                  value={formState.periodStart}
                  onChange={(event) => onSetForm({ periodStart: event.target.value })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="period-end">
                  Period End
                </label>
                <Input
                  id="period-end"
                  type="date"
                  value={formState.periodEnd}
                  onChange={(event) => onSetForm({ periodEnd: event.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm text-foreground">Entity IDs (comma-separated UUIDs)</p>
              <div className="flex gap-2">
                <Input
                  value={formState.entityInput}
                  onChange={(event) => onSetForm({ entityInput: event.target.value })}
                  placeholder="uuid1, uuid2"
                />
                <Button type="button" variant="outline" onClick={onAddEntityIds}>
                  Add
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {formState.entityIds.map((entityId) => (
                  <span
                    key={entityId}
                    className="inline-flex items-center gap-2 rounded-full border border-border px-2 py-1 text-xs text-muted-foreground"
                  >
                    {entityId}
                    <button
                      type="button"
                      className="text-foreground"
                      onClick={() =>
                        onSetForm({
                          entityIds: formState.entityIds.filter(
                            (value) => value !== entityId,
                          ),
                        })
                      }
                      aria-label={`Remove ${entityId}`}
                    >
                      <span aria-hidden="true">×</span>
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="amount-min">
                  Amount Min (decimal string)
                </label>
                <Input
                  id="amount-min"
                  value={formState.amountMin}
                  onChange={(event) => onSetForm({ amountMin: event.target.value })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="amount-max">
                  Amount Max (decimal string)
                </label>
                <Input
                  id="amount-max"
                  value={formState.amountMax}
                  onChange={(event) => onSetForm({ amountMax: event.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm text-foreground">Tags (comma-separated)</p>
              <div className="flex gap-2">
                <Input
                  value={formState.tagsInput}
                  onChange={(event) => onSetForm({ tagsInput: event.target.value })}
                  placeholder="finance, board"
                />
                <Button type="button" variant="outline" onClick={onAddTags}>
                  Add
                </Button>
              </div>
            </div>
          </>
        ) : null}

        {step === 4 ? (
          <>
            <div className="space-y-2">
              <p className="text-sm text-foreground">Group By</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {formState.metricKeys.map((metricKey) => (
                  <label
                    key={metricKey}
                    className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm text-muted-foreground"
                  >
                    <input
                      type="checkbox"
                      checked={formState.groupBy.includes(metricKey)}
                      onChange={(event) =>
                        onSetForm({
                          groupBy: event.target.checked
                            ? Array.from(new Set([...formState.groupBy, metricKey]))
                            : formState.groupBy.filter((item) => item !== metricKey),
                        })
                      }
                    />
                    {metricByKey.get(metricKey)?.label ?? metricKey}
                  </label>
                ))}
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="sort-field">
                  Sort Field
                </label>
                <select
                  id="sort-field"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={formState.sortField}
                  onChange={(event) => onSetForm({ sortField: event.target.value })}
                >
                  <option value="">None</option>
                  {formState.metricKeys.map((metricKey) => (
                    <option key={metricKey} value={metricKey}>
                      {metricByKey.get(metricKey)?.label ?? metricKey}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="sort-direction">
                  Sort Direction
                </label>
                <select
                  id="sort-direction"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={formState.sortDirection}
                  onChange={(event) =>
                    onSetForm({
                      sortDirection:
                        event.target.value === SortDirection.DESC
                          ? SortDirection.DESC
                          : SortDirection.ASC,
                    })
                  }
                >
                  <option value={SortDirection.ASC}>ASC</option>
                  <option value={SortDirection.DESC}>DESC</option>
                </select>
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-foreground" htmlFor="config-text">
                Config (JSON)
              </label>
              <textarea
                id="config-text"
                className="min-h-32 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs text-foreground"
                value={formState.configText}
                onChange={(event) => onSetForm({ configText: event.target.value })}
              />
            </div>
          </>
        ) : null}

        {sheetError ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {sheetError}
          </p>
        ) : null}

        <div className="flex items-center justify-between gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onSetStep((previous) => Math.max(previous - 1, 1))}
            disabled={savingDefinition || step === 1}
          >
            Back
          </Button>
          {step < 4 ? (
            <Button
              type="button"
              onClick={() => {
                if (!onValidateStep(step)) return
                onSetStep((previous) => Math.min(previous + 1, 4))
              }}
              disabled={savingDefinition}
            >
              Next
            </Button>
          ) : (
            <Button type="button" onClick={onSave} disabled={savingDefinition}>
              {savingDefinition ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save"
              )}
            </Button>
          )}
        </div>
      </div>
    </Sheet>
  )
}
