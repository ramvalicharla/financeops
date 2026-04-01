import apiClient from "@/lib/api/client"

export interface JournalLineInput {
  account_code?: string
  tenant_coa_account_id?: string
  debit: string
  credit: string
  memo?: string
}

export interface CreateJournalPayload {
  org_entity_id: string
  journal_date: string
  reference?: string
  narration?: string
  lines: JournalLineInput[]
}

export interface JournalLine {
  line_number: number
  tenant_coa_account_id: string | null
  account_code: string
  account_name: string | null
  debit: string
  credit: string
  memo: string | null
}

export interface JournalRecord {
  id: string
  org_entity_id: string
  journal_number: string
  journal_date: string
  reference: string | null
  narration: string | null
  status: string
  posted_at: string | null
  total_debit: string
  total_credit: string
  currency: string
  lines: JournalLine[]
}

export interface JournalActionResult {
  id: string
  status: "DRAFT" | "REVIEW" | "APPROVED" | "POSTED"
  posted_at: string | null
}

export const createJournal = async (
  payload: CreateJournalPayload,
): Promise<JournalRecord> => {
  const response = await apiClient.post<JournalRecord>(
    "/api/v1/accounting/journals/",
    payload,
  )
  return response.data
}

export const listJournals = async (params?: {
  org_entity_id?: string
  status?: "DRAFT" | "REVIEW" | "APPROVED" | "POSTED"
  limit?: number
  offset?: number
}): Promise<JournalRecord[]> => {
  const search = new URLSearchParams()
  if (params?.org_entity_id) search.set("org_entity_id", params.org_entity_id)
  if (params?.status) search.set("status", params.status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const suffix = search.toString()
  const response = await apiClient.get<JournalRecord[]>(
    `/api/v1/accounting/journals/${suffix ? `?${suffix}` : ""}`,
  )
  return response.data
}

export const getJournal = async (journalId: string): Promise<JournalRecord> => {
  const response = await apiClient.get<JournalRecord>(
    `/api/v1/accounting/journals/${journalId}`,
  )
  return response.data
}

export const approveJournal = async (
  journalId: string,
): Promise<JournalActionResult> => {
  const response = await apiClient.post<JournalActionResult>(
    `/api/v1/accounting/journals/${journalId}/approve`,
    {},
  )
  return response.data
}

export const postJournal = async (
  journalId: string,
): Promise<JournalActionResult> => {
  const response = await apiClient.post<JournalActionResult>(
    `/api/v1/accounting/journals/${journalId}/post`,
    {},
  )
  return response.data
}

export const reverseJournal = async (
  journalId: string,
): Promise<JournalRecord> => {
  const response = await apiClient.post<JournalRecord>(
    `/api/v1/accounting/journals/${journalId}/reverse`,
    {},
  )
  return response.data
}
