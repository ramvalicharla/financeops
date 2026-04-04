"use client"

import { ReportDefinitionSheet } from "./_components/ReportDefinitionSheet"
import { ReportFilters } from "./_components/ReportFilters"
import { ReportList } from "./_components/ReportList"
import { ReportRunDialog } from "./_components/ReportRunDialog"
import { useReports } from "./_hooks/useReports"
import { Button } from "@/components/ui/button"

export default function ReportsPage() {
  const {
    activeTab,
    addEntityIds,
    addTags,
    closeRunDialog,
    closeSheet,
    definitionError,
    definitionNameById,
    definitions,
    deleteDefinitionAction,
    formState,
    groupedMetrics,
    loadingDefinitions,
    loadingMetrics,
    loadingRuns,
    metricByKey,
    openCreateSheet,
    openEditSheet,
    openRunDialog,
    runDefinitionAction,
    runDialogDefinition,
    runError,
    runningDefinitionId,
    runs,
    saveDefinition,
    savingDefinition,
    setActiveTab,
    setForm,
    setStep,
    sheetError,
    sheetMode,
    step,
    validateStep,
  } = useReports()

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Custom Reports</h1>
          <p className="text-sm text-muted-foreground">
            Define reusable metric reports and run them on demand.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => {
            void openCreateSheet()
          }}
        >
          New Report
        </Button>
      </div>

      <ReportFilters activeTab={activeTab} onTabChange={setActiveTab} />

      {activeTab === "runs" ? (
        <ReportList
          mode="runs"
          definitionNameById={definitionNameById}
          error={runError}
          loading={loadingRuns}
          runs={runs}
        />
      ) : (
        <ReportList
          mode="definitions"
          definitions={definitions}
          error={definitionError}
          loading={loadingDefinitions}
          onDelete={deleteDefinitionAction}
          onEdit={(definition) => {
            void openEditSheet(definition)
          }}
          onRun={openRunDialog}
          runningDefinitionId={runningDefinitionId}
        />
      )}

      <ReportDefinitionSheet
        formState={formState}
        groupedMetrics={groupedMetrics}
        loadingMetrics={loadingMetrics}
        metricByKey={metricByKey}
        open={Boolean(sheetMode)}
        savingDefinition={savingDefinition}
        sheetError={sheetError}
        step={step}
        title={sheetMode === "edit" ? "Edit Report" : "Create Report"}
        onAddEntityIds={addEntityIds}
        onAddTags={addTags}
        onClose={closeSheet}
        onSave={() => {
          void saveDefinition()
        }}
        onSetForm={setForm}
        onSetStep={setStep}
        onValidateStep={validateStep}
      />

      <ReportRunDialog
        definition={runDialogDefinition}
        loading={runningDefinitionId === runDialogDefinition?.id}
        onClose={closeRunDialog}
        onConfirm={(definitionId) => {
          void runDefinitionAction(definitionId)
        }}
      />
    </div>
  )
}
