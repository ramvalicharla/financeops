"use client"

import { BoardPackEditSheet } from "./_components/BoardPackEditSheet"
import { BoardPackFilters } from "./_components/BoardPackFilters"
import { BoardPackList } from "./_components/BoardPackList"
import { BoardPackRunDialog } from "./_components/BoardPackRunDialog"
import { useBoardPack } from "./_hooks/useBoardPack"
import { ConfirmDialog } from "@/components/ui"
import { Button } from "@/components/ui/button"

export default function BoardPackPage() {
  const {
    activeDefinitions,
    activeTab,
    addEntityId,
    closeEditSheet,
    closeGenerateDialog,
    confirmLoading,
    confirmState,
    definitionError,
    definitionNameById,
    definitions,
    dismissConfirm,
    editState,
    generateDefinitionId,
    generateError,
    generateOpen,
    generatePeriodEnd,
    generatePeriodStart,
    generateSubmitting,
    handleDeleteDefinition,
    handleGenerate,
    handleSaveEdit,
    loadingDefinitions,
    loadingRuns,
    openEditSheet,
    openGenerateDialog,
    runError,
    runs,
    setActiveTab,
    setEditValue,
    setGenerateDefinitionId,
    setGeneratePeriodEnd,
    setGeneratePeriodStart,
    toggleSectionType,
    removeEntityId,
  } = useBoardPack()

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Board Packs</h1>
          <p className="text-sm text-muted-foreground">
            Generate and review period board-pack outputs.
          </p>
        </div>
        <Button type="button" onClick={() => openGenerateDialog()}>
          New Pack
        </Button>
      </div>

      <BoardPackFilters activeTab={activeTab} onTabChange={setActiveTab} />

      {activeTab === "runs" ? (
        <BoardPackList
          mode="runs"
          definitionNameById={definitionNameById}
          error={runError}
          loading={loadingRuns}
          runs={runs}
        />
      ) : (
        <BoardPackList
          mode="definitions"
          definitions={definitions}
          error={definitionError}
          loading={loadingDefinitions}
          onDelete={handleDeleteDefinition}
          onEdit={openEditSheet}
          onGenerate={openGenerateDialog}
        />
      )}

      <BoardPackRunDialog
        activeDefinitions={activeDefinitions}
        definitionId={generateDefinitionId}
        error={generateError}
        open={generateOpen}
        periodEnd={generatePeriodEnd}
        periodStart={generatePeriodStart}
        submitting={generateSubmitting}
        onClose={closeGenerateDialog}
        onDefinitionChange={setGenerateDefinitionId}
        onGenerate={() => {
          void handleGenerate()
        }}
        onPeriodEndChange={setGeneratePeriodEnd}
        onPeriodStartChange={setGeneratePeriodStart}
      />

      <BoardPackEditSheet
        editState={editState}
        onAddEntityId={addEntityId}
        onClose={closeEditSheet}
        onRemoveEntityId={removeEntityId}
        onSave={() => {
          void handleSaveEdit()
        }}
        onSetValue={setEditValue}
        onToggleSectionType={toggleSectionType}
      />

      {confirmState ? (
        <ConfirmDialog
          open={confirmState.open}
          title={confirmState.title}
          description={confirmState.description}
          variant={confirmState.variant}
          confirmLabel="Delete"
          isLoading={confirmLoading}
          onConfirm={confirmState.onConfirm}
          onCancel={dismissConfirm}
        />
      ) : null}
    </div>
  )
}
