"use client"

import { CalendarClock } from "lucide-react"
import { DeliveryFormSheet } from "./_components/DeliveryFormSheet"
import { DeliveryList } from "./_components/DeliveryList"
import { DeliveryLogPanel } from "./_components/DeliveryLogPanel"
import { useDeliveries } from "./_hooks/useDeliveries"
import { Button } from "@/components/ui/button"

export default function ScheduledDeliveryPage() {
  const {
    addRecipient,
    closeSheet,
    definitionNameById,
    deleteScheduleAction,
    error,
    formState,
    loading,
    loadingSources,
    openCreateSheet,
    openEditSheet,
    removeRecipient,
    runningId,
    saveSchedule,
    saving,
    schedules,
    setForm,
    setRecipient,
    sheetError,
    sheetMode,
    sourceOptions,
    toastMessage,
    triggerNow,
  } = useDeliveries()

  return (
    <div className="space-y-6">
      {toastMessage ? (
        <div className="fixed right-4 top-4 z-[60] rounded-md border border-[hsl(var(--brand-success)/0.5)] bg-[hsl(var(--brand-success)/0.2)] px-3 py-2 text-sm text-[hsl(var(--brand-success))]">
          {toastMessage}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Scheduled Delivery</h1>
          <p className="text-sm text-muted-foreground">
            Configure recurring board pack/report deliveries to email or webhook
            recipients.
          </p>
        </div>
        <div className="flex gap-2">
          <DeliveryLogPanel />
          <Button type="button" onClick={openCreateSheet}>
            <CalendarClock className="mr-2 h-4 w-4" />
            New Schedule
          </Button>
        </div>
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <DeliveryList
        definitionNameById={definitionNameById}
        loading={loading}
        runningId={runningId}
        schedules={schedules}
        onDelete={(scheduleId) => {
          void deleteScheduleAction(scheduleId)
        }}
        onEdit={openEditSheet}
        onTrigger={(scheduleId) => {
          void triggerNow(scheduleId)
        }}
      />

      <DeliveryFormSheet
        error={sheetError}
        formState={formState}
        loadingSources={loadingSources}
        open={Boolean(sheetMode)}
        sourceOptions={sourceOptions}
        submitting={saving}
        title={sheetMode === "edit" ? "Edit Schedule" : "Create Schedule"}
        onAddRecipient={addRecipient}
        onChange={setForm}
        onClose={closeSheet}
        onRecipientChange={setRecipient}
        onRemoveRecipient={removeRecipient}
        onSubmit={() => {
          void saveSchedule()
        }}
      />
    </div>
  )
}
