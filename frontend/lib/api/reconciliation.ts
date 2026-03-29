import apiClient from "@/lib/api/client"
import type {
  GLTBReconResult,
  JournalEntry,
  PayrollCostCentre,
  PayrollReconSummary,
} from "@/types/reconciliation"

export const getGLTBResult = async (
  entityId: string,
  period: string,
  runId: string,
): Promise<GLTBReconResult> => {
  const response = await apiClient.get<GLTBReconResult>(
    `/api/v1/reconciliation/gl-tb?entity_id=${encodeURIComponent(entityId)}&period=${encodeURIComponent(period)}&run_id=${encodeURIComponent(runId)}`,
  )
  return response.data
}

export const getGLTBAccountEntries = async (
  entityId: string,
  accountCode: string,
  period: string,
): Promise<JournalEntry[]> => {
  const response = await apiClient.get<JournalEntry[]>(
    `/api/v1/reconciliation/gl-tb/entries?entity_id=${encodeURIComponent(entityId)}&account_code=${encodeURIComponent(accountCode)}&period=${encodeURIComponent(period)}`,
  )
  return response.data
}

export const exportGLTBCSV = async (
  entityId: string,
  period: string,
  runId: string,
): Promise<void> => {
  const response = await apiClient.get<Blob>(
    `/api/v1/reconciliation/gl-tb/export?entity_id=${encodeURIComponent(entityId)}&period=${encodeURIComponent(period)}&run_id=${encodeURIComponent(runId)}`,
    {
      responseType: "blob",
    },
  )
  const fileName = `gltb-reconciliation-${entityId}-${period}.csv`
  const downloadUrl = window.URL.createObjectURL(response.data)
  const link = document.createElement("a")
  link.href = downloadUrl
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(downloadUrl)
}

export const getPayrollRecon = async (
  entityId: string,
  period: string,
  runId: string,
): Promise<PayrollReconSummary> => {
  const response = await apiClient.get<PayrollReconSummary>(
    `/api/v1/reconciliation/payroll?entity_id=${encodeURIComponent(entityId)}&period=${encodeURIComponent(period)}&run_id=${encodeURIComponent(runId)}`,
  )
  return response.data
}

export const getPayrollCostCentreDetail = async (
  entityId: string,
  costCentreId: string,
  period: string,
): Promise<PayrollCostCentre> => {
  const response = await apiClient.get<PayrollCostCentre>(
    `/api/v1/reconciliation/payroll/cost-centre?entity_id=${encodeURIComponent(entityId)}&cost_centre_id=${encodeURIComponent(costCentreId)}&period=${encodeURIComponent(period)}`,
  )
  return response.data
}
